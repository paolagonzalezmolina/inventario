"""
conector_aws.py
───────────────────────────────────────────────────────────────────────────────
Lee datos reales de AWS usando boto3.
Reemplaza datos_ejemplo.py cuando MODO_DEMO = False en app.py

REQUISITOS PREVIOS:
  1. aws configure --profile inventario 
  2. MODO_DEMO = False en app.py

PARA AGREGAR MÁS CUENTAS:
  Duplica las funciones con sufijo _cuenta_b, _cuenta_c, etc.
  y usa profile_name="inventario_b" etc.
───────────────────────────────────────────────────────────────────────────────
"""

import boto3
import pandas as pd
import streamlit as st
from datetime import datetime, timezone
from botocore.exceptions import ClientError, NoCredentialsError

# ─── TTL caché: 5 minutos — cambia según necesidad ────────────────────────────
CACHE_TTL = 300

# ─── Configuración ────────────────────────────────────────────────────────────
PERFIL    = "inventario"      # perfil principal
REGION    = "us-east-1"       # región principal

# Mapa de perfiles disponibles — agregar más cuentas aquí
# ✅ ACTUALIZADO: 4 cuentas AWS
PERFILES = {
    "afex-des":   {"perfil": "inventario",   "region": "us-east-1", "regiones": ["us-east-1"]},
    "afex-prod": {"perfil": "inventario-b", "region": "us-east-1", "regiones": ["us-east-1", "us-east-2"]},
    "afex-peru": {"perfil": "inventario-c", "region": "us-east-1", "regiones": ["us-east-1"]},
    "afex-digital": {"perfil": "inventario-d", "region": "us-east-1", "regiones": ["us-east-1"]},
}

REGIONES_NOMBRES = {
    "us-east-1": "us-east-1 Virginia",
    "us-east-2": "us-east-2 Ohio",
    "us-west-1": "us-west-1 California",
    "us-west-2": "us-west-2 Oregon",
    "sa-east-1": "sa-east-1 São Paulo",
}

def _session(perfil=None):
    """Crea sesión boto3 con el perfil indicado (o el principal por defecto)."""
    p = perfil or PERFIL
    cfg = PERFILES.get(p, {"perfil": p, "region": REGION})
    try:
        return boto3.Session(profile_name=cfg["perfil"], region_name=cfg["region"])
    except Exception as e:
        raise ConnectionError(f"No se pudo conectar con el perfil '{p}': {e}")

def _cliente(servicio, region=None, perfil=None):
    cfg = PERFILES.get(perfil or PERFIL, {"region": REGION})
    return _session(perfil).client(servicio, region_name=region or cfg["region"])

def _region(perfil=None):
    return PERFILES.get(perfil or PERFIL, {"region": REGION})["region"]

def _regiones(perfil=None):
    """Retorna lista de regiones configuradas para un perfil."""
    return PERFILES.get(perfil or PERFIL, {"regiones": [REGION]}).get("regiones", [REGION])

# ─── EC2 ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_ec2_df():
    try:
        ec2 = _cliente("ec2")
        response = ec2.describe_instances()
        filas = []
        for reserva in response["Reservations"]:
            for inst in reserva["Instances"]:
                nombre = next(
                    (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"),
                    inst["InstanceId"]
                )
                filas.append({
                    "id":                  inst["InstanceId"],
                    "nombre":              nombre,
                    "tipo":                inst["InstanceType"],
                    "estado":              inst["State"]["Name"],
                    "region":              REGION,
                    "ip_privada":          inst.get("PrivateIpAddress", "—"),
                    "ip_publica":          inst.get("PublicIpAddress", "—"),
                    "vpc":                 inst.get("VpcId", "—"),
                    "version_ami":         inst.get("ImageId", "—"),
                    "ultima_actualizacion": inst.get("LaunchTime", "").strftime("%Y-%m-%d")
                                           if inst.get("LaunchTime") else "—",
                })
        return pd.DataFrame(filas) if filas else pd.DataFrame(
            columns=["id","nombre","tipo","estado","region","ip_privada","ip_publica","vpc","version_ami","ultima_actualizacion"]
        )
    except NoCredentialsError:
        raise ConnectionError("No se encontraron credenciales AWS. Ejecuta: aws configure --profile inventario")
    except ClientError as e:
        raise ConnectionError(f"Error AWS EC2: {e.response['Error']['Message']}")

# ─── RDS ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_rds_df():
    try:
        rds = _cliente("rds")
        response = rds.describe_db_instances()
        filas = []
        for db in response["DBInstances"]:
            filas.append({
                "id":                  db["DBInstanceIdentifier"],
                "nombre":              db["DBInstanceIdentifier"],
                "motor":               db["Engine"],
                "version":             db["EngineVersion"],
                "estado":              db["DBInstanceStatus"],
                "tipo":                db["DBInstanceClass"],
                "region":              REGION,
                "vpc":                 db.get("DBSubnetGroup", {}).get("VpcId", "—"),
                "multi_az":            db.get("MultiAZ", False),
                "almacenamiento_gb":   db.get("AllocatedStorage", 0),
                "ultima_actualizacion": db.get("InstanceCreateTime", "").strftime("%Y-%m-%d")
                                        if db.get("InstanceCreateTime") else "—",
            })
        return pd.DataFrame(filas) if filas else pd.DataFrame(
            columns=["id","nombre","motor","version","estado","tipo","region","vpc","multi_az","almacenamiento_gb","ultima_actualizacion"]
        )
    except ClientError as e:
        raise ConnectionError(f"Error AWS RDS: {e.response['Error']['Message']}")

# ─── LAMBDA ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_lambda_df():
    try:
        lam = _cliente("lambda")
        funciones = []
        paginator = lam.get_paginator("list_functions")
        for page in paginator.paginate():
            funciones.extend(page["Functions"])

        cw = _cliente("cloudwatch")
        filas = []
        for f in funciones:
            nombre = f["FunctionName"]
            arn = f["FunctionArn"]
            invoc, errores = _lambda_metricas(cw, nombre)
            
            try:
                tags_response = lam.list_tags(Resource=arn)
                tags = tags_response.get('Tags', {})
                tags_str = ', '.join([f"{k}={v}" for k, v in tags.items()]) if tags else "Sin tags"
                tiene_tags = len(tags) > 0
            except Exception as e:
                tags_str = "Error al obtener tags"
                tiene_tags = False
            
            filas.append({
                "nombre":              nombre,
                "runtime":             f.get("Runtime", "—"),
                "estado":              f.get("State", "Active"),
                "region":              REGION,
                "memoria_mb":          f.get("MemorySize", 0),
                "timeout_s":           f.get("Timeout", 0),
                "invocaciones_dia":    invoc,
                "errores_dia":         errores,
                "ultima_actualizacion": f.get("LastModified", "")[:10] if f.get("LastModified") else "—",
                "tags":                tags_str,
                "tiene_tags":          tiene_tags,
            })
        return pd.DataFrame(filas) if filas else pd.DataFrame(
            columns=["nombre","runtime","estado","region","memoria_mb","timeout_s","invocaciones_dia","errores_dia","ultima_actualizacion","tags","tiene_tags"]
        )
    except ClientError as e:
        raise ConnectionError(f"Error AWS Lambda: {e.response['Error']['Message']}")

def _lambda_metricas(cw, nombre):
    """Obtiene invocaciones y errores del último día desde CloudWatch."""
    try:
        from datetime import timedelta
        ahora  = datetime.now(timezone.utc)
        inicio = ahora - timedelta(days=1)
        dims   = [{"Name": "FunctionName", "Value": nombre}]

        def _stat(metrica):
            r = cw.get_metric_statistics(
                Namespace="AWS/Lambda", MetricName=metrica,
                Dimensions=dims, StartTime=inicio, EndTime=ahora,
                Period=86400, Statistics=["Sum"]
            )
            pts = r.get("Datapoints", [])
            return int(pts[0]["Sum"]) if pts else 0

        return _stat("Invocations"), _stat("Errors")
    except Exception:
        return 0, 0

# ─── VPC ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_vpc_df():
    try:
        ec2 = _cliente("ec2")
        vpcs = ec2.describe_vpcs()["Vpcs"]
        subnets = ec2.describe_subnets()["Subnets"]
        igws    = ec2.describe_internet_gateways()["InternetGateways"]

        igw_vpcs = set()
        for igw in igws:
            for att in igw.get("Attachments", []):
                igw_vpcs.add(att.get("VpcId"))

        filas = []
        for vpc in vpcs:
            nombre = next(
                (t["Value"] for t in vpc.get("Tags", []) if t["Key"] == "Name"),
                vpc["VpcId"]
            )
            n_subnets = sum(1 for s in subnets if s["VpcId"] == vpc["VpcId"])
            filas.append({
                "id":               vpc["VpcId"],
                "nombre":           nombre,
                "cidr":             vpc["CidrBlock"],
                "region":           REGION,
                "subnets":          n_subnets,
                "estado":           vpc["State"],
                "internet_gateway": vpc["VpcId"] in igw_vpcs,
            })
        return pd.DataFrame(filas) if filas else pd.DataFrame(
            columns=["id","nombre","cidr","region","subnets","estado","internet_gateway"]
        )
    except ClientError as e:
        raise ConnectionError(f"Error AWS VPC: {e.response['Error']['Message']}")

# ─── API GATEWAY ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_api_df():
    try:
        apigw = _cliente("apigateway")
        apis  = apigw.get_rest_apis().get("items", [])

        # API Gateway v2 (HTTP/WebSocket)
        try:
            apigw2 = _cliente("apigatewayv2")
            apis_v2 = apigw2.get_apis().get("Items", [])
        except Exception:
            apis_v2 = []

        cw = _cliente("cloudwatch")
        filas = []

        for api in apis:
            llamadas, latencia = _api_metricas(cw, api["id"], api["name"])
            filas.append({
                "id":       api["id"],
                "nombre":   api["name"],
                "tipo":     "REST",
                "estado":   "ACTIVE",
                "region":   REGION,
                "endpoint": f"https://{api['id']}.execute-api.{REGION}.amazonaws.com",
                "llamadas_dia": llamadas,
                "latencia_ms":  latencia,
                "version":  api.get("version", "—"),
            })

        for api in apis_v2:
            filas.append({
                "id":       api["ApiId"],
                "nombre":   api["Name"],
                "tipo":     api.get("ProtocolType", "HTTP"),
                "estado":   "ACTIVE",
                "region":   REGION,
                "endpoint": api.get("ApiEndpoint", "—"),
                "llamadas_dia": 0,
                "latencia_ms":  0,
                "version":  "—",
            })

        return pd.DataFrame(filas) if filas else pd.DataFrame(
            columns=["id","nombre","tipo","estado","region","endpoint","llamadas_dia","latencia_ms","version"]
        )
    except ClientError as e:
        raise ConnectionError(f"Error AWS API Gateway: {e.response['Error']['Message']}")

def _api_metricas(cw, api_id, api_nombre):
    """Obtiene llamadas y latencia promedio del último día."""
    try:
        from datetime import timedelta
        ahora  = datetime.now(timezone.utc)
        inicio = ahora - timedelta(days=1)
        dims   = [{"Name": "ApiName", "Value": api_nombre}]

        r_count = cw.get_metric_statistics(
            Namespace="AWS/ApiGateway", MetricName="Count",
            Dimensions=dims, StartTime=inicio, EndTime=ahora,
            Period=86400, Statistics=["Sum"]
        )
        r_lat = cw.get_metric_statistics(
            Namespace="AWS/ApiGateway", MetricName="Latency",
            Dimensions=dims, StartTime=inicio, EndTime=ahora,
            Period=86400, Statistics=["Average"]
        )
        llamadas = int(r_count["Datapoints"][0]["Sum"])     if r_count["Datapoints"] else 0
        latencia = int(r_lat["Datapoints"][0]["Average"])   if r_lat["Datapoints"]   else 0
        return llamadas, latencia
    except Exception:
        return 0, 0

# ─── ALERTAS ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_alertas():
    """Lee alarmas de CloudWatch en estado ALARM."""
    try:
        cw = _cliente("cloudwatch")
        response = cw.describe_alarms(StateValue="ALARM")
        alertas = []
        for a in response["MetricAlarms"]:
            alertas.append({
                "severidad":  "CRÍTICA" if a.get("AlarmDescription", "").lower().find("critical") >= 0 else "AVISO",
                "componente": a["AlarmName"],
                "mensaje":    a.get("AlarmDescription", a["StateReason"])[:80],
                "tiempo":     a["StateUpdatedTimestamp"].strftime("Hace %Hh %Mm")
                              if a.get("StateUpdatedTimestamp") else "—",
            })
        return alertas if alertas else []
    except ClientError as e:
        return [{"severidad": "INFO", "componente": "CloudWatch",
                 "mensaje": f"No se pudieron cargar alarmas: {e.response['Error']['Message']}",
                 "tiempo": "ahora"}]

# ─── RELACIONES (descubrimiento básico) ───────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_relaciones():
    """
    Retorna lista de relaciones conocidas.
    Por ahora manual — cuando actives AWS Config se puede automatizar.
    """
    return [
        ("REST API v2",       "auth-validator",    "Valida tokens JWT"),
        ("REST API v2",       "payment-processor", "Procesa pagos"),
        ("Auth API",          "auth-validator",    "Autenticación"),
    ]

# ─── RESUMEN ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_resumen():
    try:
        df_ec2    = get_ec2_df()
        df_rds    = get_rds_df()
        df_lambda = get_lambda_df()
        df_api    = get_api_df()
        df_aurora = get_aurora_df()
        df_dynamo = get_dynamodb_df()
        df_vpc    = get_vpc_df()
        df_subnet = get_subnets_df()
        df_s3     = get_s3_df()
        alertas   = get_alertas()
        return {
            "ec2_total":        len(df_ec2),
            "ec2_running":      len(df_ec2[df_ec2["estado"] == "running"]) if not df_ec2.empty else 0,
            "rds_total":        len(df_rds),
            "aurora_total":     len(df_aurora),
            "dynamo_total":     len(df_dynamo),
            "bd_total":         len(df_rds) + len(df_aurora) + len(df_dynamo),
            "lambda_total":     len(df_lambda),
            "lambda_activas":   len(df_lambda[df_lambda["estado"] == "Active"]) if not df_lambda.empty else 0,
            "vpc_total":        len(df_vpc),
            "subnet_total":     len(df_subnet),
            "s3_total":         len(df_s3),
            "api_total":        len(df_api),
            "api_activas":      len(df_api[df_api["estado"] == "ACTIVE"]) if not df_api.empty else 0,
            "alertas_criticas": sum(1 for a in alertas if a["severidad"] == "CRÍTICA"),
            "alertas_aviso":    sum(1 for a in alertas if a["severidad"] == "AVISO"),
        }
    except Exception as e:
        return {
            "ec2_total": 0, "ec2_running": 0, "rds_total": 0,
            "aurora_total": 0, "dynamo_total": 0, "bd_total": 0,
            "lambda_total": 0, "lambda_activas": 0,
            "vpc_total": 0, "subnet_total": 0, "s3_total": 0,
            "api_total": 0, "api_activas": 0,
            "alertas_criticas": 1, "alertas_aviso": 0,
            "_error": str(e)
        }

# ─── IAM USUARIOS ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_iam_users_df():
    """Lee usuarios IAM: nombre, estado, MFA, políticas, último acceso."""
    try:
        iam = _session().client("iam")
        paginator = iam.get_paginator("list_users")
        usuarios = []
        for page in paginator.paginate():
            for u in page["Users"]:
                nombre = u["UserName"]

                # Estado MFA
                mfa_devices = iam.list_mfa_devices(UserName=nombre).get("MFADevices", [])
                tiene_mfa   = len(mfa_devices) > 0

                # Estado login (si tiene perfil de login = usuario persona)
                try:
                    login = iam.get_login_profile(UserName=nombre)
                    es_persona = True
                    pwd_reset  = login["LoginProfile"].get("PasswordResetRequired", False)
                except iam.exceptions.NoSuchEntityException:
                    es_persona   = False
                    pwd_reset    = False

                # Último acceso
                try:
                    ultimo = u.get("PasswordLastUsed")
                    if ultimo:
                        dias = (datetime.now(timezone.utc) - ultimo).days
                        ultimo_str = f"Hace {dias} días"
                    else:
                        ultimo_str = "Nunca"
                except Exception:
                    ultimo_str = "—"

                # Políticas adjuntas directamente
                politicas_dir = iam.list_attached_user_policies(UserName=nombre).get("AttachedPolicies", [])
                nombres_pol   = [p["PolicyName"] for p in politicas_dir]

                # Políticas via grupos
                grupos = iam.list_groups_for_user(UserName=nombre).get("Groups", [])
                for g in grupos:
                    pols_grupo = iam.list_attached_group_policies(GroupName=g["GroupName"]).get("AttachedPolicies", [])
                    for pg in pols_grupo:
                        if pg["PolicyName"] not in nombres_pol:
                            nombres_pol.append(f"{pg['PolicyName']} (via {g['GroupName']})")

                # Access Keys
                keys = iam.list_access_keys(UserName=nombre).get("AccessKeyMetadata", [])
                keys_activos = sum(1 for k in keys if k["Status"] == "Active")

                # Determinar si es bloqueado (sin login profile y sin keys activos)
                bloqueado = not es_persona and keys_activos == 0

                usuarios.append({
                    "nombre":        nombre,
                    "tipo":          "Persona" if es_persona else "Servicio",
                    "estado":        "🔴 Bloqueado" if bloqueado else "🟢 Activo",
                    "mfa":           "✅ Activo" if tiene_mfa else "⚠️ Sin MFA",
                    "politicas":     ", ".join(nombres_pol) if nombres_pol else "Sin políticas",
                    "n_politicas":   len(politicas_dir),
                    "ultimo_acceso": ultimo_str,
                    "pwd_rotacion":  "Requiere reset" if pwd_reset else "OK",
                    "access_keys":   keys_activos,
                    "arn":           u["Arn"],
                })

        return pd.DataFrame(usuarios) if usuarios else pd.DataFrame(columns=[
            "nombre","tipo","estado","mfa","politicas","n_politicas",
            "ultimo_acceso","pwd_rotacion","access_keys","arn"
        ])

    except ClientError as e:
        raise ConnectionError(f"Error AWS IAM: {e.response['Error']['Message']}")

# ─── IDENTIDAD DE CUENTA ──────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_identity():
    """Retorna información de la cuenta y usuario actual."""
    try:
        sts = _session().client("sts")
        r   = sts.get_caller_identity()
        # Intentar obtener alias de cuenta
        try:
            iam     = _session().client("iam")
            aliases = iam.list_account_aliases().get("AccountAliases", [])
            alias   = aliases[0] if aliases else ""
        except Exception:
            alias = ""
        return {
            "account_id":   r["Account"],
            "account_name": alias,
            "arn":          r["Arn"],
            "user_id":      r["UserId"],
            "region":       REGION,
        }
    except Exception as e:
        return {
            "account_id": "—", "account_name": "—",
            "arn": "—", "user_id": "—", "region": REGION,
        }

# ─── AURORA ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_aurora_df():
    """Lee clusters Aurora desde RDS."""
    try:
        rds    = _cliente("rds")
        clusters = rds.describe_db_clusters().get("DBClusters", [])
        filas  = []
        for c in clusters:
            filas.append({
                "id":               c["DBClusterIdentifier"],
                "nombre":           c["DBClusterIdentifier"],
                "motor":            c["Engine"],
                "version":          c.get("EngineVersion", "—"),
                "estado":           c["Status"],
                "tipo":             "cluster",
                "tipo_bd":          "Aurora",
                "region":           REGION,
                "az":               c.get("AvailabilityZones", ["—"])[0],
                "vpc":              c.get("VpcSecurityGroups", [{}])[0].get("VpcId", "—"),
                "multi_az":         len(c.get("AvailabilityZones", [])) > 1,
                "almacenamiento_gb": c.get("AllocatedStorage", 0),
                "miembros":         len(c.get("DBClusterMembers", [])),
                "endpoint":         c.get("Endpoint", "—"),
                "ultima_actualizacion": c.get("ClusterCreateTime", "").strftime("%Y-%m-%d")
                                        if c.get("ClusterCreateTime") else "—",
            })
        return pd.DataFrame(filas) if filas else pd.DataFrame(columns=[
            "id","nombre","motor","version","estado","tipo","tipo_bd","region",
            "az","vpc","multi_az","almacenamiento_gb","miembros","endpoint","ultima_actualizacion"
        ])
    except Exception:
        return pd.DataFrame(columns=[
            "id","nombre","motor","version","estado","tipo","tipo_bd","region",
            "az","vpc","multi_az","almacenamiento_gb","miembros","endpoint","ultima_actualizacion"
        ])

# ─── DYNAMODB ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_dynamodb_df():
    """Lee tablas DynamoDB."""
    try:
        ddb      = _cliente("dynamodb")
        tablas   = ddb.list_tables().get("TableNames", [])
        filas    = []
        for nombre in tablas:
            try:
                t = ddb.describe_table(TableName=nombre)["Table"]
                filas.append({
                    "id":               t["TableId"] if "TableId" in t else nombre,
                    "nombre":           nombre,
                    "motor":            "DynamoDB",
                    "version":          "—",
                    "estado":           t["TableStatus"],
                    "tipo":             "tabla",
                    "tipo_bd":          "DynamoDB",
                    "region":           REGION,
                    "items":            t.get("ItemCount", 0),
                    "tamaño_bytes":     t.get("TableSizeBytes", 0),
                    "rcu":              t.get("ProvisionedThroughput", {}).get("ReadCapacityUnits", 0),
                    "wcu":              t.get("ProvisionedThroughput", {}).get("WriteCapacityUnits", 0),
                    "gsi_count":        len(t.get("GlobalSecondaryIndexes", [])),
                    "ultima_actualizacion": t.get("CreationDateTime", "").strftime("%Y-%m-%d")
                                            if t.get("CreationDateTime") else "—",
                })
            except Exception:
                pass
        return pd.DataFrame(filas) if filas else pd.DataFrame(columns=[
            "id","nombre","motor","version","estado","tipo","tipo_bd","region",
            "items","tamaño_bytes","rcu","wcu","gsi_count","ultima_actualizacion"
        ])
    except Exception:
        return pd.DataFrame(columns=[
            "id","nombre","motor","version","estado","tipo","tipo_bd","region",
            "items","tamaño_bytes","rcu","wcu","gsi_count","ultima_actualizacion"
        ])

# ─── SUBNETS ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_subnets_df():
    """Lee subnets de todas las VPCs."""
    try:
        ec2     = _cliente("ec2")
        subnets = ec2.describe_subnets()["Subnets"]
        filas   = []
        for s in subnets:
            nombre = next(
                (t["Value"] for t in s.get("Tags", []) if t["Key"] == "Name"),
                s["SubnetId"]
            )
            filas.append({
                "id":               s["SubnetId"],
                "nombre":           nombre,
                "vpc_id":           s["VpcId"],
                "cidr":             s["CidrBlock"],
                "az":               s["AvailabilityZone"],
                "ips_disponibles":  s["AvailableIpAddressCount"],
                "publica":          s.get("MapPublicIpOnLaunch", False),
                "estado":           s["State"],
            })
        return pd.DataFrame(filas) if filas else pd.DataFrame(columns=[
            "id","nombre","vpc_id","cidr","az","ips_disponibles","publica","estado"
        ])
    except Exception:
        return pd.DataFrame(columns=[
            "id","nombre","vpc_id","cidr","az","ips_disponibles","publica","estado"
        ])

# ─── AVAILABILITY ZONES ───────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_azs_df():
    """Lee Availability Zones disponibles."""
    try:
        ec2  = _cliente("ec2")
        azs  = ec2.describe_availability_zones()["AvailabilityZones"]
        filas = []
        for az in azs:
            filas.append({
                "nombre":  az["ZoneName"],
                "zone_id": az["ZoneId"],
                "tipo":    az.get("ZoneType", "availability-zone"),
                "estado":  az["State"],
                "region":  az["RegionName"],
                "grupo":   az.get("GroupName", "—"),
            })
        return pd.DataFrame(filas) if filas else pd.DataFrame(columns=[
            "nombre","zone_id","tipo","estado","region","grupo"
        ])
    except Exception:
        return pd.DataFrame(columns=["nombre","zone_id","tipo","estado","region","grupo"])

# ─── S3 ───────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_s3_df():
    """Lee buckets S3."""
    try:
        s3      = _session().client("s3")
        buckets = s3.list_buckets().get("Buckets", [])
        filas   = []
        for b in buckets:
            try:
                loc = s3.get_bucket_location(Bucket=b["Name"])
                region = loc["LocationConstraint"] or "us-east-1"
            except Exception:
                region = "—"
            filas.append({
                "nombre":  b["Name"],
                "region":  region,
                "creado":  b["CreationDate"].strftime("%Y-%m-%d") if b.get("CreationDate") else "—",
            })
        return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["nombre","region","creado"])
    except Exception:
        return pd.DataFrame(columns=["nombre","region","creado"])


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES MULTI-PERFIL — consultan una cuenta específica
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=CACHE_TTL)
def get_resumen_perfil(perfil: str) -> dict:
    """Resumen completo para un perfil/cuenta específico."""
    try:
        region = _region(perfil)
        ec2    = _cliente("ec2",      perfil=perfil)
        rds    = _cliente("rds",      perfil=perfil)
        lam    = _cliente("lambda",   perfil=perfil)
        s3     = _session(perfil).client("s3")
        ddb    = _cliente("dynamodb", perfil=perfil)

        # EC2
        reservas  = ec2.describe_instances()["Reservations"]
        ec2_total = sum(len(r["Instances"]) for r in reservas)
        ec2_run   = sum(1 for r in reservas for i in r["Instances"] if i["State"]["Name"]=="running")

        # RDS
        rds_list  = rds.describe_db_instances().get("DBInstances", [])

        # Aurora
        try:
            aurora = rds.describe_db_clusters().get("DBClusters", [])
        except Exception:
            aurora = []

        # Lambda
        lam_list = []
        pag = lam.get_paginator("list_functions")
        for page in pag.paginate():
            lam_list.extend(page["Functions"])

        # S3
        s3_list = s3.list_buckets().get("Buckets", [])

        # DynamoDB
        ddb_list = ddb.list_tables().get("TableNames", [])

        # VPC / Subnets
        vpcs    = ec2.describe_vpcs()["Vpcs"]
        subnets = ec2.describe_subnets()["Subnets"]

        return {
            "perfil":       perfil,
            "region":       region,
            "ec2_total":    ec2_total,
            "ec2_running":  ec2_run,
            "rds_total":    len(rds_list),
            "aurora_total": len(aurora),
            "bd_total":     len(rds_list) + len(aurora) + len(ddb_list),
            "lambda_total": len(lam_list),
            "s3_total":     len(s3_list),
            "dynamo_total": len(ddb_list),
            "vpc_total":    len(vpcs),
            "subnet_total": len(subnets),
        }
    except Exception as e:
        return {
            "perfil": perfil, "region": _region(perfil),
            "ec2_total":0,"ec2_running":0,"rds_total":0,"aurora_total":0,
            "bd_total":0,"lambda_total":0,"s3_total":0,"dynamo_total":0,
            "vpc_total":0,"subnet_total":0,
            "_error": str(e)
        }

@st.cache_data(ttl=CACHE_TTL)
def get_identity_perfil(perfil: str) -> dict:
    """Identidad de una cuenta específica."""
    try:
        sts = _session(perfil).client("sts")
        r   = sts.get_caller_identity()
        try:
            iam     = _session(perfil).client("iam")
            aliases = iam.list_account_aliases().get("AccountAliases", [])
            alias   = aliases[0] if aliases else ""
        except Exception:
            alias = ""
        return {
            "account_id":   r["Account"],
            "account_name": alias or perfil,
            "arn":          r["Arn"],
            "region":       _region(perfil),
            "perfil":       perfil,
        }
    except Exception as e:
        return {
            "account_id": "—", "account_name": perfil,
            "arn": "—", "region": _region(perfil),
            "perfil": perfil, "_error": str(e)
        }

# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES POR PERFIL — cada una consulta una cuenta específica
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=CACHE_TTL)
def get_ec2_perfil(perfil: str):
    try:
        ec2 = _cliente("ec2", perfil=perfil)
        region = _region(perfil)
        filas = []
        for reserva in ec2.describe_instances()["Reservations"]:
            for inst in reserva["Instances"]:
                nombre = next((t["Value"] for t in inst.get("Tags",[]) if t["Key"]=="Name"), inst["InstanceId"])
                filas.append({
                    "id": inst["InstanceId"], "nombre": nombre,
                    "tipo": inst["InstanceType"],
                    "estado": inst["State"]["Name"],
                    "region": region,
                    "ip_privada": inst.get("PrivateIpAddress","—"),
                    "vpc": inst.get("VpcId","—"),
                    "version_ami": inst.get("ImageId","—"),
                    "ultima_actualizacion": inst["LaunchTime"].strftime("%Y-%m-%d") if inst.get("LaunchTime") else "—",
                })
        return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["id","nombre","tipo","estado","region","ip_privada","vpc","version_ami","ultima_actualizacion"])
    except Exception:
        return pd.DataFrame(columns=["id","nombre","tipo","estado","region","ip_privada","vpc","version_ami","ultima_actualizacion"])

@st.cache_data(ttl=CACHE_TTL)
def get_rds_perfil(perfil: str):
    try:
        rds = _cliente("rds", perfil=perfil)
        region = _region(perfil)
        filas = []
        for db in rds.describe_db_instances().get("DBInstances",[]):
            filas.append({
                "id": db["DBInstanceIdentifier"], "nombre": db["DBInstanceIdentifier"],
                "motor": db["Engine"], "version": db["EngineVersion"],
                "estado": db["DBInstanceStatus"], "tipo": db["DBInstanceClass"],
                "region": region,
                "multi_az": db.get("MultiAZ", False),
                "almacenamiento_gb": db.get("AllocatedStorage", 0),
                "ultima_actualizacion": db["InstanceCreateTime"].strftime("%Y-%m-%d") if db.get("InstanceCreateTime") else "—",
            })
        return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["id","nombre","motor","version","estado","tipo","region","multi_az","almacenamiento_gb","ultima_actualizacion"])
    except Exception:
        return pd.DataFrame(columns=["id","nombre","motor","version","estado","tipo","region","multi_az","almacenamiento_gb","ultima_actualizacion"])

@st.cache_data(ttl=CACHE_TTL)
def get_lambda_perfil(perfil: str):
    try:
        lam = _cliente("lambda", perfil=perfil)
        region = _region(perfil)
        funciones = []
        for page in lam.get_paginator("list_functions").paginate():
            funciones.extend(page["Functions"])
        filas = []
        for f in funciones:
            filas.append({
                "nombre": f["FunctionName"],
                "runtime": f.get("Runtime","—"),
                "estado": f.get("State","Active"),
                "region": region,
                "memoria_mb": f.get("MemorySize",0),
                "timeout_s": f.get("Timeout",0),
                "invocaciones_dia": 0,
                "errores_dia": 0,
                "ultima_actualizacion": f.get("LastModified","")[:10] if f.get("LastModified") else "—",
            })
        return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["nombre","runtime","estado","region","memoria_mb","timeout_s","invocaciones_dia","errores_dia","ultima_actualizacion"])
    except Exception:
        return pd.DataFrame(columns=["nombre","runtime","estado","region","memoria_mb","timeout_s","invocaciones_dia","errores_dia","ultima_actualizacion"])

@st.cache_data(ttl=CACHE_TTL)
def get_vpc_perfil(perfil: str):
    try:
        ec2 = _cliente("ec2", perfil=perfil)
        region = _region(perfil)
        vpcs    = ec2.describe_vpcs()["Vpcs"]
        subnets = ec2.describe_subnets()["Subnets"]
        igws    = ec2.describe_internet_gateways()["InternetGateways"]
        igw_vpcs = {att.get("VpcId") for igw in igws for att in igw.get("Attachments",[])}
        filas = []
        for vpc in vpcs:
            nombre = next((t["Value"] for t in vpc.get("Tags",[]) if t["Key"]=="Name"), vpc["VpcId"])
            filas.append({
                "id": vpc["VpcId"], "nombre": nombre,
                "cidr": vpc["CidrBlock"], "region": region,
                "subnets": sum(1 for s in subnets if s["VpcId"]==vpc["VpcId"]),
                "estado": vpc["State"],
                "internet_gateway": vpc["VpcId"] in igw_vpcs,
            })
        return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["id","nombre","cidr","region","subnets","estado","internet_gateway"])
    except Exception:
        return pd.DataFrame(columns=["id","nombre","cidr","region","subnets","estado","internet_gateway"])

@st.cache_data(ttl=CACHE_TTL)
def get_s3_perfil(perfil: str):
    try:
        s3 = _session(perfil).client("s3")
        filas = []
        for b in s3.list_buckets().get("Buckets",[]):
            try:
                loc = s3.get_bucket_location(Bucket=b["Name"])
                region = loc["LocationConstraint"] or "us-east-1"
            except Exception:
                region = "—"
            filas.append({
                "nombre": b["Name"], "region": region,
                "creado": b["CreationDate"].strftime("%Y-%m-%d") if b.get("CreationDate") else "—",
            })
        return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["nombre","region","creado"])
    except Exception:
        return pd.DataFrame(columns=["nombre","region","creado"])

@st.cache_data(ttl=CACHE_TTL)
def get_dynamodb_perfil(perfil: str):
    try:
        ddb = _cliente("dynamodb", perfil=perfil)
        region = _region(perfil)
        tablas = ddb.list_tables().get("TableNames",[])
        filas = []
        for nombre in tablas:
            try:
                t = ddb.describe_table(TableName=nombre)["Table"]
                filas.append({
                    "nombre": nombre, "estado": t["TableStatus"],
                    "tipo": t.get("BillingModeSummary",{}).get("BillingMode","PROVISIONED"),
                    "items": t.get("ItemCount",0),
                    "rcu": t.get("ProvisionedThroughput",{}).get("ReadCapacityUnits",0),
                    "wcu": t.get("ProvisionedThroughput",{}).get("WriteCapacityUnits",0),
                    "region": region,
                })
            except Exception:
                pass
        return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["nombre","estado","tipo","items","rcu","wcu","region"])
    except Exception:
        return pd.DataFrame(columns=["nombre","estado","tipo","items","rcu","wcu","region"])

# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES MULTI-REGIÓN — consultan varias regiones de un mismo perfil
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=CACHE_TTL)
def get_resumen_region(perfil: str, region: str) -> dict:
    """Resumen de recursos en una región específica de un perfil."""
    try:
        ec2 = _session(perfil).client("ec2",      region_name=region)
        rds = _session(perfil).client("rds",      region_name=region)
        lam = _session(perfil).client("lambda",   region_name=region)
        ddb = _session(perfil).client("dynamodb", region_name=region)

        # EC2
        reservas  = ec2.describe_instances()["Reservations"]
        ec2_total = sum(len(r["Instances"]) for r in reservas)
        ec2_run   = sum(1 for r in reservas for i in r["Instances"] if i["State"]["Name"] == "running")

        # RDS
        rds_list = rds.describe_db_instances().get("DBInstances", [])

        # Aurora
        try:
            aurora = rds.describe_db_clusters().get("DBClusters", [])
        except Exception:
            aurora = []

        # Lambda
        lam_list = []
        for page in lam.get_paginator("list_functions").paginate():
            lam_list.extend(page["Functions"])

        # DynamoDB
        ddb_list = ddb.list_tables().get("TableNames", [])

        # VPC / Subnets
        vpcs    = ec2.describe_vpcs()["Vpcs"]
        subnets = ec2.describe_subnets()["Subnets"]

        return {
            "perfil":       perfil,
            "region":       region,
            "region_nombre": REGIONES_NOMBRES.get(region, region),
            "ec2_total":    ec2_total,
            "ec2_running":  ec2_run,
            "rds_total":    len(rds_list),
            "aurora_total": len(aurora),
            "lambda_total": len(lam_list),
            "dynamo_total": len(ddb_list),
            "vpc_total":    len(vpcs),
            "subnet_total": len(subnets),
            "bd_total":     len(rds_list) + len(aurora) + len(ddb_list),
        }
    except Exception as e:
        return {
            "perfil": perfil, "region": region,
            "region_nombre": REGIONES_NOMBRES.get(region, region),
            "ec2_total": 0, "ec2_running": 0, "rds_total": 0,
            "aurora_total": 0, "lambda_total": 0, "dynamo_total": 0,
            "vpc_total": 0, "subnet_total": 0, "bd_total": 0,
            "_error": str(e)
        }

@st.cache_data(ttl=CACHE_TTL)
def get_comparacion_regiones(perfil: str) -> list:
    """Retorna lista de resúmenes por región para un perfil."""
    regiones = _regiones(perfil)
    return [get_resumen_region(perfil, r) for r in regiones]

# ─── IAM USUARIOS POR PERFIL ──────────────────────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def get_iam_users_perfil(perfil: str):
    """Lee usuarios IAM de un perfil específico."""
    try:
        iam = _session(perfil).client("iam")
        paginator = iam.get_paginator("list_users")
        usuarios = []
        for page in paginator.paginate():
            for u in page["Users"]:
                nombre = u["UserName"]
                mfa_devices  = iam.list_mfa_devices(UserName=nombre).get("MFADevices", [])
                tiene_mfa    = len(mfa_devices) > 0
                try:
                    login      = iam.get_login_profile(UserName=nombre)
                    es_persona = True
                    pwd_reset  = login["LoginProfile"].get("PasswordResetRequired", False)
                except Exception:
                    es_persona = False
                    pwd_reset  = False
                ultimo = u.get("PasswordLastUsed")
                if ultimo:
                    dias = (datetime.now(timezone.utc) - ultimo).days
                    ultimo_str = f"Hace {dias} días"
                else:
                    ultimo_str = "Nunca"
                politicas_dir = iam.list_attached_user_policies(UserName=nombre).get("AttachedPolicies", [])
                nombres_pol   = [p["PolicyName"] for p in politicas_dir]
                grupos = iam.list_groups_for_user(UserName=nombre).get("Groups", [])
                for g in grupos:
                    for pg in iam.list_attached_group_policies(GroupName=g["GroupName"]).get("AttachedPolicies", []):
                        if pg["PolicyName"] not in nombres_pol:
                            nombres_pol.append(f"{pg['PolicyName']} (via {g['GroupName']})")
                keys = iam.list_access_keys(UserName=nombre).get("AccessKeyMetadata", [])
                keys_activos = sum(1 for k in keys if k["Status"] == "Active")
                bloqueado = not es_persona and keys_activos == 0
                usuarios.append({
                    "nombre":        nombre,
                    "tipo":          "Persona" if es_persona else "Servicio",
                    "estado":        "🔴 Bloqueado" if bloqueado else "🟢 Activo",
                    "mfa":           "✅ Activo" if tiene_mfa else "⚠️ Sin MFA",
                    "politicas":     ", ".join(nombres_pol) if nombres_pol else "Sin políticas",
                    "n_politicas":   len(politicas_dir),
                    "ultimo_acceso": ultimo_str,
                    "pwd_rotacion":  "Requiere reset" if pwd_reset else "OK",
                    "access_keys":   keys_activos,
                    "arn":           u["Arn"],
                })
        return pd.DataFrame(usuarios) if usuarios else pd.DataFrame(columns=[
            "nombre","tipo","estado","mfa","politicas","n_politicas",
            "ultimo_acceso","pwd_rotacion","access_keys","arn"
        ])
    except Exception as e:
        raise ConnectionError(f"Error IAM perfil {perfil}: {e}")

# ─── Carga de df por tipo y región específica ─────────────────────────────────
@st.cache_data(ttl=CACHE_TTL)
def _df_region(perfil: str, region: str, tipo: str):
    """Carga un DataFrame de un tipo de recurso en una región específica."""
    ses = _session(perfil)
    try:
        if tipo == "ec2":
            ec2   = ses.client("ec2", region_name=region)
            filas = []
            for reserva in ec2.describe_instances()["Reservations"]:
                for inst in reserva["Instances"]:
                    nombre = next((t["Value"] for t in inst.get("Tags",[]) if t["Key"]=="Name"), inst["InstanceId"])
                    filas.append({
                        "nombre":    nombre,
                        "tipo":      inst["InstanceType"],
                        "estado":    inst["State"]["Name"],
                        "ip_privada":inst.get("PrivateIpAddress","—"),
                        "vpc":       inst.get("VpcId","—"),
                        "region":    region,
                    })
            return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["nombre","tipo","estado","ip_privada","vpc","region"])

        elif tipo == "vpc":
            ec2     = ses.client("ec2", region_name=region)
            vpcs    = ec2.describe_vpcs()["Vpcs"]
            subnets = ec2.describe_subnets()["Subnets"]
            igws    = ec2.describe_internet_gateways()["InternetGateways"]
            igw_vpcs = {att.get("VpcId") for igw in igws for att in igw.get("Attachments",[])}
            filas = []
            for vpc in vpcs:
                nombre = next((t["Value"] for t in vpc.get("Tags",[]) if t["Key"]=="Name"), vpc["VpcId"])
                filas.append({
                    "nombre":           nombre,
                    "cidr":             vpc["CidrBlock"],
                    "subnets":          sum(1 for s in subnets if s["VpcId"]==vpc["VpcId"]),
                    "estado":           vpc["State"],
                    "internet_gateway": vpc["VpcId"] in igw_vpcs,
                    "region":           region,
                })
            return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["nombre","cidr","subnets","estado","internet_gateway","region"])

        elif tipo == "rds":
            rds  = ses.client("rds", region_name=region)
            filas = []
            for db in rds.describe_db_instances().get("DBInstances",[]):
                filas.append({
                    "nombre":  db["DBInstanceIdentifier"],
                    "motor":   db["Engine"],
                    "version": db["EngineVersion"],
                    "estado":  db["DBInstanceStatus"],
                    "tipo":    db["DBInstanceClass"],
                    "region":  region,
                })
            return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["nombre","motor","version","estado","tipo","region"])

        elif tipo == "lambda":
            lam  = ses.client("lambda", region_name=region)
            filas = []
            for page in lam.get_paginator("list_functions").paginate():
                for f in page["Functions"]:
                    filas.append({
                        "nombre":     f["FunctionName"],
                        "runtime":    f.get("Runtime","—"),
                        "estado":     f.get("State","Active"),
                        "memoria_mb": f.get("MemorySize",0),
                        "region":     region,
                    })
            return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["nombre","runtime","estado","memoria_mb","region"])

        elif tipo == "dynamo":
            ddb   = ses.client("dynamodb", region_name=region)
            tablas = ddb.list_tables().get("TableNames",[])
            filas  = []
            for nombre in tablas:
                try:
                    t = ddb.describe_table(TableName=nombre)["Table"]
                    filas.append({
                        "nombre": nombre,
                        "estado": t["TableStatus"],
                        "items":  t.get("ItemCount",0),
                        "region": region,
                    })
                except Exception:
                    filas.append({"nombre": nombre, "estado": "—", "items": 0, "region": region})
            return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["nombre","estado","items","region"])

    except Exception as e:
        return pd.DataFrame([{"error": str(e)}])
