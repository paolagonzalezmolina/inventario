"""
conector_aws.py - Conector AWS refactorizado

Funciones para conectar con AWS y descargar componentes.
El cache es manejado por download_engine.py y app.py.
"""

import json
import logging
from datetime import datetime, timezone

import boto3
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PERFILES = {
    "afex-des": {"perfil": "inventario", "region": "us-east-1", "regiones": ["us-east-1", "us-east-2"]},
    "afex-prod": {"perfil": "inventario-b", "region": "us-east-1", "regiones": ["us-east-1", "us-east-2"]},
    "afex-peru": {"perfil": "inventario-c", "region": "us-east-1", "regiones": ["us-east-1", "us-east-2"]},
    "afex-digital": {"perfil": "inventario-d", "region": "us-east-1", "regiones": ["us-east-1", "us-east-2"]},
}

AUDIT_CREATE_EVENTS = {
    "ec2": {"RunInstances"},
    "rds": {"CreateDBInstance"},
    "vpc": {"CreateVpc"},
    "s3": {"CreateBucket"},
    "iam_users": {"CreateUser"},
    "lambda": {"CreateFunction20150331"},
    "api_gateway": {"CreateRestApi", "ImportRestApi"},
    "api_gateway_routes": {"CreateRestApi", "ImportRestApi", "CreateApi"},
    "cloudformation": {"CreateStack"},
    "ssm": {"PutParameter"},
    "kms": {"CreateKey"},
    "dynamodb": {"CreateTable"},
    "sqs": {"CreateQueue"},
    "vpc_outbound_ips": {"CreateNatGateway", "AllocateAddress", "CreateInternetGateway"},
}


def _safe_to_iso(value):
    """Normaliza fechas a ISO string simple para mostrar en tablas."""
    if value in (None, "", "N/A"):
        return None

    try:
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime().isoformat()
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None
            if normalized.endswith("Z"):
                normalized = normalized.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized).isoformat()
            except ValueError:
                return value
        if hasattr(value, "isoformat"):
            return value.isoformat()
    except Exception:
        return str(value)

    return str(value)


def _format_cloudtrail_username(event):
    """Extrae el usuario/rol mas util desde un evento CloudTrail."""
    username = event.get("Username")
    if username:
        return username

    payload = event.get("CloudTrailEvent")
    if not payload:
        return None

    try:
        event_detail = json.loads(payload)
    except Exception:
        return None

    user_identity = event_detail.get("userIdentity", {}) or {}
    candidates = [
        user_identity.get("userName"),
        user_identity.get("principalId"),
        user_identity.get("arn"),
        event_detail.get("username"),
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return None


def _get_lookup_values(resource_type, row):
    """Retorna posibles identificadores para buscar auditoria en CloudTrail."""
    value_map = {
        "ec2": [row.get("id"), row.get("nombre")],
        "rds": [row.get("id"), row.get("nombre")],
        "vpc": [row.get("id"), row.get("nombre")],
        "s3": [row.get("nombre")],
        "iam_users": [row.get("username")],
        "lambda": [row.get("nombre")],
        "api_gateway": [row.get("id"), row.get("nombre")],
        "api_gateway_routes": [
            row.get("api_id"),
            row.get("api_nombre"),
            row.get("lambda_function"),
            row.get("route_key"),
            row.get("ruta"),
        ],
        "cloudformation": [row.get("id"), row.get("nombre")],
        "ssm": [row.get("nombre")],
        "kms": [row.get("arn"), row.get("key_id"), row.get("alias")],
        "dynamodb": [row.get("nombre")],
        "sqs": [row.get("url"), row.get("nombre")],
        "vpc_outbound_ips": [row.get("resource_id"), row.get("allocation_id"), row.get("name")],
    }
    seen = []
    for value in value_map.get(resource_type, []):
        if value and str(value).strip() and value not in seen:
            seen.append(value)
    return seen


def _get_native_audit_values(resource_type, row):
    """Extrae fechas nativas cuando AWS ya las expone en la API del servicio."""
    native_created = None
    native_updated = None

    if resource_type == "ec2":
        native_created = row.get("launchTime")
    elif resource_type == "rds":
        native_created = row.get("creationTime")
    elif resource_type == "s3":
        native_created = row.get("creacion")
    elif resource_type == "iam_users":
        native_created = row.get("creacion")
    elif resource_type == "lambda":
        native_created = row.get("creacion")
        native_updated = row.get("ultima_modificacion")
    elif resource_type == "api_gateway":
        native_created = row.get("creacion")
    elif resource_type == "api_gateway_routes":
        native_created = row.get("creacion_api")
    elif resource_type == "cloudformation":
        native_created = row.get("creacion")
        native_updated = row.get("ultima_actualizacion")
    elif resource_type == "ssm":
        native_updated = row.get("ultima_modificacion")
    elif resource_type == "kms":
        native_created = row.get("creacion")
    elif resource_type == "dynamodb":
        native_created = row.get("creacion")
    elif resource_type == "sqs":
        native_created = row.get("creacion")
        native_updated = row.get("ultima_modificacion")
    elif resource_type == "vpc_outbound_ips":
        native_created = row.get("creacion")
        native_updated = row.get("ultima_modificacion")

    return _safe_to_iso(native_created), _safe_to_iso(native_updated)


def _lookup_cloudtrail_audit(profile_name, region, resource_type, lookup_values):
    """Busca creador y ultima actividad del recurso desde CloudTrail."""
    if not lookup_values:
        return {}

    client = _get_client(profile_name, "cloudtrail", region)
    if not client:
        return {}

    create_events = AUDIT_CREATE_EVENTS.get(resource_type, set())
    collected_events = []

    for value in lookup_values:
        try:
            response = client.lookup_events(
                LookupAttributes=[
                    {"AttributeKey": "ResourceName", "AttributeValue": str(value)}
                ],
                MaxResults=50,
            )
            collected_events.extend(response.get("Events", []))
        except Exception as exc:
            logger.warning(
                f"No se pudo consultar CloudTrail para {resource_type}/{value} en {region}: {exc}"
            )

    if not collected_events:
        return {}

    deduped = {}
    for event in collected_events:
        event_id = event.get("EventId")
        if event_id and event_id not in deduped:
            deduped[event_id] = event

    ordered = sorted(
        deduped.values(),
        key=lambda item: item.get("EventTime") or datetime.min.replace(tzinfo=timezone.utc),
    )
    create_event = next(
        (event for event in ordered if event.get("EventName") in create_events),
        ordered[0],
    )
    last_event = ordered[-1]

    return {
        "usuario_creador": _format_cloudtrail_username(create_event),
        "fecha_creacion": _safe_to_iso(create_event.get("EventTime")),
        "fecha_ultima_modificacion": _safe_to_iso(last_event.get("EventTime")),
    }


def add_audit_metadata(perfil, region, resource_type, data):
    """Agrega usuario creador y fechas de auditoria a un DataFrame para despliegue."""
    if data is None or not isinstance(data, pd.DataFrame) or data.empty:
        return data

    enriched = data.copy()
    lookup_cache = {}
    audit_rows = []

    for _, row in enriched.iterrows():
        row_dict = row.to_dict()
        lookup_values = tuple(_get_lookup_values(resource_type, row_dict))
        native_created, native_updated = _get_native_audit_values(resource_type, row_dict)

        if lookup_values not in lookup_cache:
            lookup_cache[lookup_values] = _lookup_cloudtrail_audit(
                perfil,
                region,
                resource_type,
                list(lookup_values),
            )

        audit_info = lookup_cache.get(lookup_values, {})
        audit_rows.append(
            {
                "usuario_creador": audit_info.get("usuario_creador") or "No disponible",
                "fecha_creacion": native_created or audit_info.get("fecha_creacion"),
                "fecha_ultima_modificacion": native_updated or audit_info.get("fecha_ultima_modificacion"),
            }
        )

    audit_df = pd.DataFrame(audit_rows, index=enriched.index)
    for column in audit_df.columns:
        enriched[column] = audit_df[column]

    return enriched


def _get_session(profile_name):
    """Crea una sesion de boto3 con perfil especifico."""
    try:
        return boto3.Session(profile_name=profile_name)
    except Exception as exc:
        logger.error(f"Error creando sesion para {profile_name}: {exc}")
        return None


def _get_client(profile_name, service, region):
    """Crea un cliente boto3 para un servicio."""
    try:
        session = _get_session(profile_name)
        if not session:
            return None
        return session.client(service, region_name=region)
    except Exception as exc:
        logger.error(f"Error creando cliente {service} en {region}: {exc}")
        return None


def _ensure_list(value):
    """Normaliza strings/listas a una lista simple."""
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    return [value]


def _compact_join(values, separator="; "):
    """Une valores unicos preservando el orden."""
    unique_values = []
    for value in _ensure_list(values):
        if value in (None, ""):
            continue
        value_str = str(value)
        if value_str not in unique_values:
            unique_values.append(value_str)
    return separator.join(unique_values)


def _extract_role_name(role_arn):
    """Retorna el RoleName a partir de un ARN IAM."""
    if not role_arn:
        return ""
    return str(role_arn).rsplit("/", 1)[-1]


def _extract_lambda_name_from_arn(lambda_arn):
    """Retorna el nombre de Lambda desde su ARN."""
    if not lambda_arn or ":function:" not in str(lambda_arn):
        return ""
    suffix = str(lambda_arn).split(":function:", 1)[1]
    return suffix.split(":", 1)[0]


def _extract_lambda_arn_from_integration_uri(uri):
    """Extrae el ARN Lambda desde la URI de integracion de API Gateway."""
    if not uri:
        return ""

    uri_text = str(uri)
    if ":lambda:path/" in uri_text and "/functions/" in uri_text and "/invocations" in uri_text:
        return uri_text.split("/functions/", 1)[1].split("/invocations", 1)[0]
    if ":function:" in uri_text:
        return uri_text
    return ""


def _build_lambda_inventory(profile_name, region):
    """Obtiene la lista bruta de funciones Lambda."""
    client = _get_client(profile_name, "lambda", region)
    if not client:
        return []

    paginator = client.get_paginator("list_functions")
    functions = []
    for page in paginator.paginate():
        functions.extend(page.get("Functions", []))
    return functions


def _append_policy_permissions(policy_document, action_values, resource_values, summary_values, source):
    """Aplana statements Allow para resumir permisos efectivos."""
    statements = policy_document.get("Statement", []) if isinstance(policy_document, dict) else []
    for statement in _ensure_list(statements):
        if not isinstance(statement, dict) or statement.get("Effect") != "Allow":
            continue

        actions = [str(item) for item in _ensure_list(statement.get("Action")) if item]
        resources = [str(item) for item in _ensure_list(statement.get("Resource")) if item]

        for action in actions:
            if action not in action_values:
                action_values.append(action)
        for resource in resources:
            if resource not in resource_values:
                resource_values.append(resource)

        action_text = ", ".join(actions) if actions else "Sin acciones"
        resource_text = ", ".join(resources) if resources else "Sin recursos"
        summary = f"{source}: {action_text} -> {resource_text}"
        if summary not in summary_values:
            summary_values.append(summary)


def _get_lambda_role_permissions(profile_name, role_arn, permission_cache):
    """Obtiene permisos del rol de ejecucion asociado a Lambda."""
    role_name = _extract_role_name(role_arn)
    if not role_name:
        return {
            "lambda_execution_role_name": "",
            "lambda_access_actions": "",
            "lambda_access_resources": "",
            "lambda_access_summary": "",
        }

    if role_name in permission_cache:
        return permission_cache[role_name]

    iam_client = _get_client(profile_name, "iam", "us-east-1")
    action_values = []
    resource_values = []
    summary_values = []

    if iam_client:
        try:
            inline_paginator = iam_client.get_paginator("list_role_policies")
            for page in inline_paginator.paginate(RoleName=role_name):
                for policy_name in page.get("PolicyNames", []):
                    document = iam_client.get_role_policy(
                        RoleName=role_name,
                        PolicyName=policy_name,
                    ).get("PolicyDocument", {})
                    _append_policy_permissions(
                        document,
                        action_values,
                        resource_values,
                        summary_values,
                        f"inline:{policy_name}",
                    )
        except Exception as exc:
            logger.warning(f"No se pudieron leer politicas inline de {role_name}: {exc}")

        try:
            attached_paginator = iam_client.get_paginator("list_attached_role_policies")
            for page in attached_paginator.paginate(RoleName=role_name):
                for policy in page.get("AttachedPolicies", []):
                    policy_arn = policy.get("PolicyArn")
                    policy_meta = iam_client.get_policy(PolicyArn=policy_arn).get("Policy", {})
                    version_id = policy_meta.get("DefaultVersionId")
                    if not version_id:
                        continue
                    document = iam_client.get_policy_version(
                        PolicyArn=policy_arn,
                        VersionId=version_id,
                    ).get("PolicyVersion", {}).get("Document", {})
                    _append_policy_permissions(
                        document,
                        action_values,
                        resource_values,
                        summary_values,
                        f"attached:{policy.get('PolicyName', policy_arn)}",
                    )
        except Exception as exc:
            logger.warning(f"No se pudieron leer politicas adjuntas de {role_name}: {exc}")

    permission_info = {
        "lambda_execution_role_name": role_name,
        "lambda_access_actions": _compact_join(action_values),
        "lambda_access_resources": _compact_join(resource_values),
        "lambda_access_summary": _compact_join(summary_values, separator=" | "),
    }
    permission_cache[role_name] = permission_info
    return permission_info


def _build_lambda_catalog(profile_name, region):
    """Construye catalogo enriquecido de Lambdas para reutilizar en varias vistas."""
    permission_cache = {}
    rows = []
    catalog = {}

    for func in _build_lambda_inventory(profile_name, region):
        vpc_config = func.get("VpcConfig") or {}
        role_arn = func.get("Role", "")
        permission_info = _get_lambda_role_permissions(profile_name, role_arn, permission_cache)

        row = {
            "nombre": func.get("FunctionName"),
            "arn": func.get("FunctionArn"),
            "handler": func.get("Handler", "N/A"),
            "runtime": func.get("Runtime", "N/A"),
            "memoria_mb": func.get("MemorySize", 0),
            "timeout_s": func.get("Timeout", 0),
            "estado": func.get("State", "Active"),
            "estado_ultima_actualizacion": func.get("LastUpdateStatus", "N/A"),
            "region": region,
            "vpc": vpc_config.get("VpcId", ""),
            "subnets": _compact_join(vpc_config.get("SubnetIds")),
            "security_groups": _compact_join(vpc_config.get("SecurityGroupIds")),
            "execution_role_arn": role_arn,
            "execution_role_name": permission_info.get("lambda_execution_role_name", ""),
            "access_actions": permission_info.get("lambda_access_actions", ""),
            "access_resources": permission_info.get("lambda_access_resources", ""),
            "access_summary": permission_info.get("lambda_access_summary", ""),
            "creacion": func.get("CreatedDate"),
            "ultima_modificacion": func.get("LastModified"),
        }
        rows.append(row)

        function_name = row.get("nombre")
        function_arn = row.get("arn")
        if function_name:
            catalog[function_name] = row
        if function_arn:
            catalog[function_arn] = row
            arn_parts = function_arn.split(":")
            if len(arn_parts) >= 7:
                catalog[":".join(arn_parts[:7])] = row

    return rows, catalog


def _paginate_apigateway_v2(client, operation_name, result_key, **kwargs):
    """Pagina operaciones de API Gateway v2 sin depender de paginators."""
    items = []
    next_token = None
    while True:
        payload = dict(kwargs)
        if next_token:
            payload["NextToken"] = next_token
        response = getattr(client, operation_name)(**payload)
        items.extend(response.get(result_key, []))
        next_token = response.get("NextToken")
        if not next_token:
            break
    return items


def get_available_regions(profile_name):
    """Obtiene regiones disponibles para una cuenta."""
    try:
        session = _get_session(profile_name)
        if not session:
            return ["us-east-1"]

        ec2 = session.client("ec2", region_name="us-east-1")
        response = ec2.describe_regions()
        regions = [region["RegionName"] for region in response.get("Regions", [])]
        logger.info(f"Regiones encontradas para {profile_name}: {len(regions)}")
        return regions or ["us-east-1"]
    except Exception as exc:
        logger.warning(f"No se pudieron obtener regiones, usando default: {exc}")
        return ["us-east-1"]


def get_ec2_df(perfil, region):
    """Obtiene instancias EC2."""
    try:
        ec2 = _get_client(perfil, "ec2", region)
        if not ec2:
            return pd.DataFrame()

        response = ec2.describe_instances()
        instances = []
        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                nombre = instance["InstanceId"]
                for tag in instance.get("Tags", []):
                    if tag.get("Key") == "Name":
                        nombre = tag.get("Value") or nombre
                        break

                instances.append({
                    "id": instance.get("InstanceId"),
                    "nombre": nombre,
                    "tipo": instance.get("InstanceType"),
                    "estado": instance.get("State", {}).get("Name"),
                    "region": region,
                    "vpc": instance.get("VpcId", "N/A"),
                    "subnet": instance.get("SubnetId", "N/A"),
                    "ip_privada": instance.get("PrivateIpAddress", "N/A"),
                    "ip_publica": instance.get("PublicIpAddress", "N/A"),
                    "key_name": instance.get("KeyName", "N/A"),
                    "launchTime": instance.get("LaunchTime"),
                    "monitoringState": instance.get("Monitoring", {}).get("State", "N/A"),
                })

        df = pd.DataFrame(instances)
        logger.info(f"EC2: {len(df)} instancias en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo EC2 para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_rds_df(perfil, region):
    """Obtiene bases de datos RDS."""
    try:
        rds = _get_client(perfil, "rds", region)
        if not rds:
            return pd.DataFrame()

        response = rds.describe_db_instances()
        databases = []
        for db in response.get("DBInstances", []):
            databases.append({
                "id": db.get("DBInstanceIdentifier"),
                "nombre": db.get("DBInstanceIdentifier"),
                "motor": db.get("Engine"),
                "version": db.get("EngineVersion", "N/A"),
                "estado": db.get("DBInstanceStatus"),
                "tipo": db.get("DBInstanceClass"),
                "almacenamiento_gb": db.get("AllocatedStorage", 0),
                "region": region,
                "vpc": db.get("DBSubnetGroup", {}).get("VpcId", "N/A"),
                "multi_az": db.get("MultiAZ", False),
                "creationTime": db.get("InstanceCreateTime"),
            })

        df = pd.DataFrame(databases)
        logger.info(f"RDS: {len(df)} bases de datos en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo RDS para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_vpc_df(perfil, region):
    """Obtiene VPCs."""
    try:
        ec2 = _get_client(perfil, "ec2", region)
        if not ec2:
            return pd.DataFrame()

        response = ec2.describe_vpcs()
        rows = []
        for vpc in response.get("Vpcs", []):
            nombre = vpc.get("VpcId")
            for tag in vpc.get("Tags", []):
                if tag.get("Key") == "Name":
                    nombre = tag.get("Value") or nombre
                    break

            subnets = ec2.describe_subnets(
                Filters=[{"Name": "vpc-id", "Values": [vpc.get("VpcId")]}]
            ).get("Subnets", [])

            rows.append({
                "id": vpc.get("VpcId"),
                "nombre": nombre,
                "cidr": vpc.get("CidrBlock"),
                "estado": vpc.get("State"),
                "region": region,
                "subnets": len(subnets),
                "default": vpc.get("IsDefault"),
            })

        df = pd.DataFrame(rows)
        logger.info(f"VPC: {len(df)} redes en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo VPC para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_s3_df(perfil):
    """Obtiene buckets S3."""
    try:
        s3 = _get_client(perfil, "s3", "us-east-1")
        if not s3:
            return pd.DataFrame()

        response = s3.list_buckets()
        buckets = []
        for bucket in response.get("Buckets", []):
            try:
                location_response = s3.get_bucket_location(Bucket=bucket["Name"])
                region = location_response.get("LocationConstraint") or "us-east-1"
            except Exception:
                region = "unknown"

            buckets.append({
                "nombre": bucket.get("Name"),
                "creacion": bucket.get("CreationDate"),
                "region": region,
            })

        df = pd.DataFrame(buckets)
        logger.info(f"S3: {len(df)} buckets")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo S3 para {perfil}: {exc}")
        return pd.DataFrame()


def get_iam_users_df(perfil):
    """Obtiene usuarios IAM."""
    try:
        iam = _get_client(perfil, "iam", "us-east-1")
        if not iam:
            return pd.DataFrame()

        response = iam.list_users()
        users = []
        for user in response.get("Users", []):
            username = user.get("UserName")

            try:
                mfa_devices = iam.list_mfa_devices(UserName=username).get("MFADevices", [])
            except Exception:
                mfa_devices = []

            try:
                access_keys = iam.list_access_keys(UserName=username).get("AccessKeyMetadata", [])
            except Exception:
                access_keys = []

            users.append({
                "username": username,
                "arn": user.get("Arn"),
                "mfa_enabled": len(mfa_devices) > 0,
                "access_keys": len(access_keys),
                "creacion": user.get("CreateDate"),
            })

        df = pd.DataFrame(users)
        logger.info(f"IAM Users: {len(df)} usuarios")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo IAM Users para {perfil}: {exc}")
        return pd.DataFrame()


def get_lambda_df(perfil, region):
    """Obtiene funciones Lambda."""
    try:
        rows, _ = _build_lambda_catalog(perfil, region)
        df = pd.DataFrame(rows)
        logger.info(f"Lambda: {len(df)} funciones en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo Lambda para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_api_gateway_df(perfil, region):
    """Obtiene APIs de API Gateway con un resumen de integraciones Lambda."""
    try:
        base_rows = []

        rest_client = _get_client(perfil, "apigateway", region)
        if rest_client:
            paginator = rest_client.get_paginator("get_rest_apis")
            for page in paginator.paginate():
                for api in page.get("items", []):
                    base_rows.append({
                        "id": api.get("id"),
                        "nombre": api.get("name"),
                        "tipo": "REST",
                        "estado": "ACTIVE",
                        "region": region,
                        "creacion": api.get("createdDate"),
                    })

        v2_client = _get_client(perfil, "apigatewayv2", region)
        if v2_client:
            for api in _paginate_apigateway_v2(v2_client, "get_apis", "Items"):
                base_rows.append({
                    "id": api.get("ApiId"),
                    "nombre": api.get("Name"),
                    "tipo": api.get("ProtocolType", "HTTP"),
                    "estado": "ACTIVE",
                    "region": region,
                    "creacion": api.get("CreatedDate"),
                })

        route_df = get_api_gateway_routes_df(perfil, region)
        if route_df.empty:
            df = pd.DataFrame(base_rows)
            logger.info(f"API Gateway: {len(df)} APIs en {region}")
            return df

        rows = {}
        for item in base_rows:
            rows[item["id"]] = dict(item)

        group_columns = ["api_id", "api_nombre", "api_tipo", "api_estado", "region", "creacion_api"]
        for group_key, api_routes in route_df.groupby(group_columns, dropna=False):
            api_id, api_name, api_type, api_status, api_region, created_at = group_key
            lambda_functions = [
                value for value in api_routes.get("lambda_function", pd.Series(dtype=str)).fillna("").astype(str).unique()
                if value
            ]
            rows[api_id] = {
                "id": api_id,
                "nombre": api_name,
                "tipo": api_type,
                "estado": api_status,
                "region": api_region,
                "creacion": created_at,
                "rutas": len(api_routes),
                "integraciones_lambda": int((api_routes.get("lambda_function", pd.Series(dtype=str)).fillna("").astype(str) != "").sum()),
                "lambdas": _compact_join(lambda_functions),
            }

        df = pd.DataFrame(rows.values())
        logger.info(f"API Gateway: {len(df)} APIs en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo API Gateway para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_api_gateway_routes_df(perfil, region):
    """Obtiene el detalle API -> ruta/metodo -> Lambda -> permisos/VPC."""
    try:
        lambda_rows, lambda_catalog = _build_lambda_catalog(perfil, region)
        del lambda_rows

        rows = []

        rest_client = _get_client(perfil, "apigateway", region)
        if rest_client:
            paginator = rest_client.get_paginator("get_rest_apis")
            for page in paginator.paginate():
                for api in page.get("items", []):
                    api_id = api.get("id")
                    resource_paginator = rest_client.get_paginator("get_resources")
                    for resource_page in resource_paginator.paginate(restApiId=api_id, embed=["methods"]):
                        for resource in resource_page.get("items", []):
                            resource_path = resource.get("path", "/")
                            for http_method in (resource.get("resourceMethods") or {}).keys():
                                method_detail = rest_client.get_method(
                                    restApiId=api_id,
                                    resourceId=resource.get("id"),
                                    httpMethod=http_method,
                                )
                                integration = method_detail.get("methodIntegration", {}) or {}
                                lambda_arn = _extract_lambda_arn_from_integration_uri(integration.get("uri", ""))
                                lambda_name = _extract_lambda_name_from_arn(lambda_arn)
                                lambda_info = (
                                    lambda_catalog.get(lambda_arn)
                                    or lambda_catalog.get(lambda_name)
                                    or {}
                                )

                                rows.append({
                                    "api_id": api_id,
                                    "api_nombre": api.get("name"),
                                    "api_tipo": "REST",
                                    "api_estado": "ACTIVE",
                                    "region": region,
                                    "creacion_api": api.get("createdDate"),
                                    "route_key": f"{http_method} {resource_path}",
                                    "metodo_http": http_method,
                                    "ruta": resource_path,
                                    "integration_type": integration.get("type", "N/A"),
                                    "integration_uri": integration.get("uri", ""),
                                    "lambda_function": lambda_info.get("nombre", lambda_name),
                                    "lambda_arn": lambda_info.get("arn", lambda_arn),
                                    "lambda_handler": lambda_info.get("handler", ""),
                                    "lambda_runtime": lambda_info.get("runtime", ""),
                                    "lambda_vpc": lambda_info.get("vpc", ""),
                                    "lambda_subnets": lambda_info.get("subnets", ""),
                                    "lambda_security_groups": lambda_info.get("security_groups", ""),
                                    "lambda_execution_role": lambda_info.get("execution_role_name", ""),
                                    "lambda_access_actions": lambda_info.get("access_actions", ""),
                                    "lambda_access_resources": lambda_info.get("access_resources", ""),
                                    "lambda_access_summary": lambda_info.get("access_summary", ""),
                                })

        v2_client = _get_client(perfil, "apigatewayv2", region)
        if v2_client:
            apis = _paginate_apigateway_v2(v2_client, "get_apis", "Items")
            for api in apis:
                api_id = api.get("ApiId")
                integrations = _paginate_apigateway_v2(v2_client, "get_integrations", "Items", ApiId=api_id)
                integration_map = {
                    item.get("IntegrationId"): item
                    for item in integrations
                    if item.get("IntegrationId")
                }
                routes = _paginate_apigateway_v2(v2_client, "get_routes", "Items", ApiId=api_id)
                for route in routes:
                    target = route.get("Target", "")
                    integration_id = target.split("/", 1)[1] if target.startswith("integrations/") else ""
                    integration = integration_map.get(integration_id, {})
                    lambda_arn = _extract_lambda_arn_from_integration_uri(integration.get("IntegrationUri", ""))
                    lambda_name = _extract_lambda_name_from_arn(lambda_arn)
                    lambda_info = (
                        lambda_catalog.get(lambda_arn)
                        or lambda_catalog.get(lambda_name)
                        or {}
                    )

                    rows.append({
                        "api_id": api_id,
                        "api_nombre": api.get("Name"),
                        "api_tipo": api.get("ProtocolType", "HTTP"),
                        "api_estado": "ACTIVE",
                        "region": region,
                        "creacion_api": api.get("CreatedDate"),
                        "route_key": route.get("RouteKey", ""),
                        "metodo_http": route.get("RouteKey", "").split(" ", 1)[0] if " " in str(route.get("RouteKey", "")) else route.get("RouteKey", ""),
                        "ruta": route.get("RouteKey", "").split(" ", 1)[1] if " " in str(route.get("RouteKey", "")) else route.get("RouteKey", ""),
                        "integration_type": integration.get("IntegrationType", "N/A"),
                        "integration_uri": integration.get("IntegrationUri", ""),
                        "lambda_function": lambda_info.get("nombre", lambda_name),
                        "lambda_arn": lambda_info.get("arn", lambda_arn),
                        "lambda_handler": lambda_info.get("handler", ""),
                        "lambda_runtime": lambda_info.get("runtime", ""),
                        "lambda_vpc": lambda_info.get("vpc", ""),
                        "lambda_subnets": lambda_info.get("subnets", ""),
                        "lambda_security_groups": lambda_info.get("security_groups", ""),
                        "lambda_execution_role": lambda_info.get("execution_role_name", ""),
                        "lambda_access_actions": lambda_info.get("access_actions", ""),
                        "lambda_access_resources": lambda_info.get("access_resources", ""),
                        "lambda_access_summary": lambda_info.get("access_summary", ""),
                    })

        df = pd.DataFrame(rows)
        logger.info(f"API Gateway Routes: {len(df)} integraciones en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo integraciones API Gateway para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_cloudformation_df(perfil, region):
    """Obtiene stacks de CloudFormation."""
    try:
        client = _get_client(perfil, "cloudformation", region)
        if not client:
            return pd.DataFrame()

        rows = []
        paginator = client.get_paginator("describe_stacks")
        for page in paginator.paginate():
            for stack in page.get("Stacks", []):
                rows.append({
                    "id": stack.get("StackId"),
                    "nombre": stack.get("StackName"),
                    "estado": stack.get("StackStatus"),
                    "region": region,
                    "creacion": stack.get("CreationTime"),
                    "ultima_actualizacion": stack.get("LastUpdatedTime"),
                })

        df = pd.DataFrame(rows)
        logger.info(f"CloudFormation: {len(df)} stacks en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo CloudFormation para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_ssm_df(perfil, region):
    """Obtiene parametros SSM."""
    try:
        client = _get_client(perfil, "ssm", region)
        if not client:
            return pd.DataFrame()

        rows = []
        paginator = client.get_paginator("describe_parameters")
        for page in paginator.paginate():
            for param in page.get("Parameters", []):
                rows.append({
                    "nombre": param.get("Name"),
                    "tipo": param.get("Type"),
                    "tier": param.get("Tier"),
                    "version": param.get("Version"),
                    "region": region,
                    "ultima_modificacion": param.get("LastModifiedDate"),
                    "data_type": param.get("DataType"),
                })

        df = pd.DataFrame(rows)
        logger.info(f"SSM: {len(df)} parametros en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo SSM para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_kms_df(perfil, region):
    """Obtiene claves KMS."""
    try:
        client = _get_client(perfil, "kms", region)
        if not client:
            return pd.DataFrame()

        alias_map = {}
        alias_paginator = client.get_paginator("list_aliases")
        for page in alias_paginator.paginate():
            for alias in page.get("Aliases", []):
                key_id = alias.get("TargetKeyId")
                alias_name = alias.get("AliasName")
                if key_id and alias_name:
                    alias_map.setdefault(key_id, []).append(alias_name)

        rows = []
        paginator = client.get_paginator("list_keys")
        for page in paginator.paginate():
            for key in page.get("Keys", []):
                key_id = key.get("KeyId")
                metadata = client.describe_key(KeyId=key_id).get("KeyMetadata", {})
                rows.append({
                    "key_id": key_id,
                    "arn": metadata.get("Arn"),
                    "descripcion": metadata.get("Description"),
                    "estado": metadata.get("KeyState"),
                    "manager": metadata.get("KeyManager"),
                    "origen": metadata.get("Origin"),
                    "es_simetrica": metadata.get("CustomerMasterKeySpec") == "SYMMETRIC_DEFAULT",
                    "alias": ", ".join(alias_map.get(key_id, [])),
                    "region": region,
                    "creacion": metadata.get("CreationDate"),
                })

        df = pd.DataFrame(rows)
        logger.info(f"KMS: {len(df)} claves en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo KMS para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_dynamodb_df(perfil, region):
    """Obtiene tablas DynamoDB."""
    try:
        client = _get_client(perfil, "dynamodb", region)
        if not client:
            return pd.DataFrame()

        table_names = []
        paginator = client.get_paginator("list_tables")
        for page in paginator.paginate():
            table_names.extend(page.get("TableNames", []))

        rows = []
        for table_name in table_names:
            table = client.describe_table(TableName=table_name).get("Table", {})
            billing_mode = table.get("BillingModeSummary", {}).get("BillingMode") or "PROVISIONED"
            throughput = table.get("ProvisionedThroughput", {})
            rows.append({
                "nombre": table.get("TableName"),
                "estado": table.get("TableStatus"),
                "billing_mode": billing_mode,
                "lectura": throughput.get("ReadCapacityUnits"),
                "escritura": throughput.get("WriteCapacityUnits"),
                "items": table.get("ItemCount"),
                "tamano_bytes": table.get("TableSizeBytes"),
                "region": region,
                "creacion": table.get("CreationDateTime"),
            })

        df = pd.DataFrame(rows)
        logger.info(f"DynamoDB: {len(df)} tablas en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo DynamoDB para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_sqs_df(perfil, region):
    """Obtiene colas SQS."""
    try:
        client = _get_client(perfil, "sqs", region)
        if not client:
            return pd.DataFrame()

        queue_urls = []
        paginator = client.get_paginator("list_queues")
        for page in paginator.paginate():
            queue_urls.extend(page.get("QueueUrls", []))

        rows = []
        for queue_url in queue_urls:
            attrs = client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=["All"],
            ).get("Attributes", {})
            rows.append({
                "nombre": queue_url.rstrip("/").split("/")[-1],
                "url": queue_url,
                "fifo": attrs.get("FifoQueue", "false") == "true",
                "mensajes_visibles": int(attrs.get("ApproximateNumberOfMessages", 0)),
                "mensajes_en_vuelo": int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)),
                "mensajes_diferidos": int(attrs.get("ApproximateNumberOfMessagesDelayed", 0)),
                "kms_key_id": attrs.get("KmsMasterKeyId", ""),
                "region": region,
                "creacion": (
                    datetime.fromtimestamp(int(attrs["CreatedTimestamp"]), tz=timezone.utc)
                    if attrs.get("CreatedTimestamp")
                    else None
                ),
                "ultima_modificacion": (
                    datetime.fromtimestamp(int(attrs["LastModifiedTimestamp"]), tz=timezone.utc)
                    if attrs.get("LastModifiedTimestamp")
                    else None
                ),
            })

        df = pd.DataFrame(rows)
        logger.info(f"SQS: {len(df)} colas en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo SQS para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_vpc_outbound_ips_df(perfil, region):
    """Obtiene NAT Gateways, EIPs e Internet Gateways por region."""
    try:
        ec2 = _get_client(perfil, "ec2", region)
        if not ec2:
            return pd.DataFrame()

        rows = []

        try:
            paginator = ec2.get_paginator("describe_nat_gateways")
            for page in paginator.paginate():
                for nat in page.get("NatGateways", []):
                    tags = {tag["Key"]: tag["Value"] for tag in nat.get("Tags", []) or []}
                    addresses = nat.get("NatGatewayAddresses", []) or []
                    if not addresses:
                        rows.append({
                            "type": "NAT Gateway",
                            "resource_id": nat.get("NatGatewayId"),
                            "name": tags.get("Name", ""),
                            "vpc_id": nat.get("VpcId"),
                            "subnet_id": nat.get("SubnetId"),
                            "public_ip": "",
                            "private_ip": "",
                            "allocation_id": "",
                            "network_interface_id": "",
                            "state": nat.get("State"),
                            "connectivity_type": nat.get("ConnectivityType", "public"),
                            "region": region,
                            "creacion": nat.get("CreateTime"),
                            "ultima_modificacion": nat.get("DeleteTime"),
                        })
                    for addr in addresses:
                        rows.append({
                            "type": "NAT Gateway",
                            "resource_id": nat.get("NatGatewayId"),
                            "name": tags.get("Name", ""),
                            "vpc_id": nat.get("VpcId"),
                            "subnet_id": nat.get("SubnetId"),
                            "public_ip": addr.get("PublicIp") or "",
                            "private_ip": addr.get("PrivateIp") or "",
                            "allocation_id": addr.get("AllocationId") or "",
                            "network_interface_id": addr.get("NetworkInterfaceId") or "",
                            "state": nat.get("State"),
                            "connectivity_type": nat.get("ConnectivityType", "public"),
                            "region": region,
                            "creacion": nat.get("CreateTime"),
                            "ultima_modificacion": nat.get("DeleteTime"),
                        })
        except Exception as exc:
            logger.warning(f"describe_nat_gateways en {region} fallo: {exc}")

        nat_allocations = {row["allocation_id"] for row in rows if row.get("allocation_id")}

        try:
            for addr in ec2.describe_addresses().get("Addresses", []):
                allocation_id = addr.get("AllocationId") or ""
                if allocation_id and allocation_id in nat_allocations:
                    continue
                tags = {tag["Key"]: tag["Value"] for tag in addr.get("Tags", []) or []}
                rows.append({
                    "type": "Elastic IP",
                    "resource_id": allocation_id or addr.get("PublicIp"),
                    "name": tags.get("Name", ""),
                    "vpc_id": "",
                    "subnet_id": "",
                    "public_ip": addr.get("PublicIp") or "",
                    "private_ip": addr.get("PrivateIpAddress") or "",
                    "allocation_id": allocation_id,
                    "network_interface_id": addr.get("NetworkInterfaceId") or "",
                    "state": "associated" if addr.get("AssociationId") else "available",
                    "connectivity_type": "public",
                    "region": region,
                    "creacion": None,
                    "ultima_modificacion": None,
                })
        except Exception as exc:
            logger.warning(f"describe_addresses en {region} fallo: {exc}")

        try:
            for igw in ec2.describe_internet_gateways().get("InternetGateways", []):
                tags = {tag["Key"]: tag["Value"] for tag in igw.get("Tags", []) or []}
                attachments = igw.get("Attachments", []) or []
                if not attachments:
                    rows.append({
                        "type": "Internet Gateway",
                        "resource_id": igw.get("InternetGatewayId"),
                        "name": tags.get("Name", ""),
                        "vpc_id": "",
                        "subnet_id": "",
                        "public_ip": "N/A (IP publica por instancia)",
                        "private_ip": "",
                        "allocation_id": "",
                        "network_interface_id": "",
                        "state": "detached",
                        "connectivity_type": "public",
                        "region": region,
                        "creacion": None,
                        "ultima_modificacion": None,
                    })
                for att in attachments:
                    rows.append({
                        "type": "Internet Gateway",
                        "resource_id": igw.get("InternetGatewayId"),
                        "name": tags.get("Name", ""),
                        "vpc_id": att.get("VpcId"),
                        "subnet_id": "",
                        "public_ip": "N/A (IP publica por instancia)",
                        "private_ip": "",
                        "allocation_id": "",
                        "network_interface_id": "",
                        "state": att.get("State", "unknown"),
                        "connectivity_type": "public",
                        "region": region,
                        "creacion": None,
                        "ultima_modificacion": None,
                    })
        except Exception as exc:
            logger.warning(f"describe_internet_gateways en {region} fallo: {exc}")

        return pd.DataFrame(rows)
    except Exception as exc:
        logger.error(f"Error obteniendo VPC outbound IPs para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_resumen_por_cuenta(cache_manager):
    """Obtiene un resumen agregado por cuenta usando el cache."""
    resumen = {}

    for account_name, config in PERFILES.items():
        regiones = config.get("regiones") or ["us-east-1"]
        region_global = regiones[0]
        resumen[account_name] = {
            "ec2": 0,
            "rds": 0,
            "vpc": 0,
            "s3": 0,
            "iam_users": 0,
        }

        for region in regiones:
            ec2_data, _, _ = cache_manager.get(account_name, region, "ec2")
            rds_data, _, _ = cache_manager.get(account_name, region, "rds")
            vpc_data, _, _ = cache_manager.get(account_name, region, "vpc")

            if isinstance(ec2_data, pd.DataFrame):
                resumen[account_name]["ec2"] += len(ec2_data)
            if isinstance(rds_data, pd.DataFrame):
                resumen[account_name]["rds"] += len(rds_data)
            if isinstance(vpc_data, pd.DataFrame):
                resumen[account_name]["vpc"] += len(vpc_data)

        s3_data, _, _ = cache_manager.get(account_name, region_global, "s3")
        iam_data, _, _ = cache_manager.get(account_name, region_global, "iam_users")

        if isinstance(s3_data, pd.DataFrame):
            resumen[account_name]["s3"] = len(s3_data)
        if isinstance(iam_data, pd.DataFrame):
            resumen[account_name]["iam_users"] = len(iam_data)

    return resumen
