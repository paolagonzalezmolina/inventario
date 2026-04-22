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
        client = _get_client(perfil, "lambda", region)
        if not client:
            return pd.DataFrame()

        paginator = client.get_paginator("list_functions")
        rows = []
        for page in paginator.paginate():
            for func in page.get("Functions", []):
                rows.append({
                    "nombre": func.get("FunctionName"),
                    "runtime": func.get("Runtime", "N/A"),
                    "memoria_mb": func.get("MemorySize", 0),
                    "timeout_s": func.get("Timeout", 0),
                    "estado": "Active",
                    "region": region,
                    "creacion": func.get("CreatedDate"),
                    "ultima_modificacion": func.get("LastModified"),
                })

        df = pd.DataFrame(rows)
        logger.info(f"Lambda: {len(df)} funciones en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo Lambda para {perfil}/{region}: {exc}")
        return pd.DataFrame()


def get_api_gateway_df(perfil, region):
    """Obtiene APIs REST de API Gateway."""
    try:
        client = _get_client(perfil, "apigateway", region)
        if not client:
            return pd.DataFrame()

        rows = []
        paginator = client.get_paginator("get_rest_apis")
        for page in paginator.paginate():
            for api in page.get("items", []):
                rows.append({
                    "id": api.get("id"),
                    "nombre": api.get("name"),
                    "tipo": "REST",
                    "estado": "ACTIVE",
                    "region": region,
                    "creacion": api.get("createdDate"),
                })

        df = pd.DataFrame(rows)
        logger.info(f"API Gateway: {len(df)} APIs en {region}")
        return df
    except Exception as exc:
        logger.error(f"Error obteniendo API Gateway para {perfil}/{region}: {exc}")
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
