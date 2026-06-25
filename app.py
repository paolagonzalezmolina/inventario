"""
app.py - Dashboard principal Streamlit

Inventario AWS multi-cuenta en tiempo real.
"""

import logging
import re
import html as html_lib
from io import BytesIO
from datetime import date, datetime, timedelta
from pathlib import Path

import boto3
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from pandas.api.types import is_numeric_dtype

from cache_manager import cache_manager
from conector_aws import PERFILES
from download_engine import (
    download_all_parallel,
    download_scope,
    get_cache_status,
    initialize_download_engine,
)
from export_to_excel import export_to_excel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="AWS Inventory",
    page_icon="cloud",
    layout="wide",
    initial_sidebar_state="expanded",
)

GLOBAL_SERVICES = {"s3", "iam_users"}
ALL_ACCOUNTS_OPTION = "__all_accounts__"
ALL_REGIONS_OPTION = "__all_regions__"
PRIORITY_REGIONS = ["us-east-1", "us-east-2"]
ACCOUNT_DISPLAY_ORDER = ["afex-prod", "afex-digital", "afex-peru", "afex-des"]
MANDATORY_TAGS = ["Name", "Environment", "Owner", "CostCenter", "Application"]
LAMBDA_RUNTIME_UPGRADE_RECOMMENDATIONS = {
    "nodejs10.x": "nodejs24.x",
    "nodejs12.x": "nodejs24.x",
    "nodejs14.x": "nodejs24.x",
    "nodejs16.x": "nodejs24.x",
    "nodejs18.x": "nodejs24.x",
    "nodejs20.x": "nodejs24.x",
    "python2.7": "python3.14",
    "python3.6": "python3.14",
    "python3.7": "python3.14",
    "python3.8": "python3.14",
    "python3.9": "python3.14",
    "ruby2.7": "ruby3.4",
    "ruby3.2": "ruby3.4",
    "java8": "java21",
    "dotnetcore2.1": "dotnet8",
    "dotnetcore3.1": "dotnet8",
}
LAMBDA_RUNTIME_UPGRADE_ACTION = (
    "Validar compatibilidad, actualizar dependencias/layers, probar y desplegar con alias/canary."
)
LAMBDA_RUNTIME_EVIDENCE = (
    "Pruebas exitosas, alias/canary aplicado, monitoreo sin errores y runtime actualizado."
)
EXPORT_DIR = Path("exports")
VULNERABILITY_COLUMNS = [
    "Cuenta",
    "AWS Account Id",
    "Region",
    "Servicio",
    "Tipo de recurso",
    "Recurso",
    "Producto key",
    "Producto",
    "Origen producto",
    "Confianza producto",
    "Titulo",
    "Riesgo",
    "Severidad",
    "Prioridad",
    "Estado",
    "Tipo hallazgo",
    "Responsable sugerido",
    "Apoyo",
    "Prioridad interna",
    "Estado remediacion",
    "Evidencia cierre",
    "Riesgo aceptado",
    "Comentario responsable",
    "Fuente hallazgo",
    "Fecha extraccion",
    "Finding Type",
    "Vulnerability Id",
    "Fix disponible",
    "Exploit disponible",
    "Edad dias",
    "Version actual",
    "Version objetivo",
    "Paquete afectado",
    "Version instalada",
    "Version corregida",
    "Package manager",
    "File path",
    "Lambda layers",
    "Lambda package type",
    "Lambda last updated at",
    "Lambda last invoked at",
    "Lambda invocations 30d",
    "Lambda idle days",
    "Lambda usage status",
    "Inspector score",
    "NVD CVSS3 score",
    "Vendor severity",
    "EPSS score",
    "Ultima explotacion",
    "Accion recomendada",
    "Remediacion AWS/Inspector",
    "Evidencia requerida",
    "Finding ARN",
    "First seen",
    "Last seen",
    "Last updated",
    "Vendor",
    "Vendor advisory",
    "Reference URLs",
    "Resource tags",
]
VULNERABILITY_MAIN_COLUMNS = [
    "Cuenta",
    "Region",
    "Servicio",
    "Recurso",
    "Producto",
    "Tipo hallazgo",
    "Titulo",
    "Severidad",
    "Prioridad interna",
    "Estado",
    "Responsable sugerido",
    "Apoyo",
    "Estado remediacion",
    "Fix disponible",
    "Exploit disponible",
    "Version actual",
    "Version objetivo",
    "Accion recomendada",
    "Evidencia requerida",
    "Edad dias",
]
VULNERABILITY_BACKLOG_COLUMNS = [
    "Cuenta",
    "Region",
    "Servicio",
    "Recurso",
    "Producto",
    "Tipo hallazgo",
    "Prioridad interna",
    "Severidad",
    "Responsable sugerido",
    "Apoyo",
    "Estado remediacion",
    "Accion recomendada",
    "Version actual",
    "Version objetivo",
    "Fix disponible",
    "Exploit disponible",
    "Evidencia requerida",
    "Evidencia cierre",
    "Riesgo aceptado",
    "Comentario responsable",
    "Fuente hallazgo",
]
VULNERABILITY_TECHNICAL_COLUMNS = [
    "Cuenta",
    "AWS Account Id",
    "Region",
    "Servicio",
    "Tipo de recurso",
    "Recurso",
    "Producto",
    "Origen producto",
    "Confianza producto",
    "Finding Type",
    "Vulnerability Id",
    "Paquete afectado",
    "Version instalada",
    "Version corregida",
    "Package manager",
    "File path",
    "Lambda layers",
    "Lambda package type",
    "Lambda last updated at",
    "Lambda last invoked at",
    "Lambda invocations 30d",
    "Lambda idle days",
    "Lambda usage status",
    "Inspector score",
    "NVD CVSS3 score",
    "Vendor severity",
    "EPSS score",
    "Ultima explotacion",
    "Remediacion AWS/Inspector",
    "Finding ARN",
    "First seen",
    "Last seen",
    "Last updated",
    "Vendor",
    "Vendor advisory",
    "Reference URLs",
    "Resource tags",
]

ANALYTICS_SERVICE_LABELS = [
    ("ec2", "EC2", False),
    ("rds", "RDS", False),
    ("vpc", "VPC", False),
    ("vpc_outbound_ips", "NAT/IPs salida", False),
    ("lambda", "Lambda", False),
    ("api_gateway", "API Gateway", False),
    ("api_gateway_routes", "API Gateway -> Lambda", False),
    ("cloudformation", "CloudFormation", False),
    ("ssm", "SSM", False),
    ("kms", "KMS", False),
    ("dynamodb", "DynamoDB", False),
    ("sqs", "SQS", False),
    ("s3", "S3", True),
    ("iam_users", "IAM Users", True),
]

TAG_COLUMN_CANDIDATES = ["tags", "Tags", "tag_set", "TagSet"]
PRODUCT_TAG_KEYS = ["Application", "Product", "Service", "Project", "Sistema", "App"]
PRODUCT_NAME_STOPWORDS = {
    "afex",
    "prod",
    "prd",
    "cert",
    "qa",
    "dev",
    "des",
    "test",
    "uat",
    "api",
    "lambda",
    "function",
    "functions",
    "table",
    "queue",
    "bucket",
    "db",
    "database",
    "rds",
    "dynamodb",
    "sqs",
    "s3",
    "vpc",
    "subnet",
    "role",
    "iam",
    "log",
    "logs",
    "cloudwatch",
    "cloudformation",
    "stack",
    "service",
    "services",
    "app",
    "us",
    "east",
    "west",
    "sa",
}

REGION_DISPLAY_NAMES = {
    "us-east-1": "Virginia",
    "us-east-2": "Ohio",
    "us-west-1": "California",
    "us-west-2": "Oregon",
    "sa-east-1": "Sao Paulo",
    "ca-central-1": "Canada",
    "eu-west-1": "Ireland",
    "eu-west-2": "London",
    "eu-west-3": "Paris",
    "eu-central-1": "Frankfurt",
    "eu-north-1": "Stockholm",
    "ap-south-1": "Mumbai",
    "ap-southeast-1": "Singapore",
    "ap-southeast-2": "Sydney",
    "ap-northeast-1": "Tokyo",
    "ap-northeast-2": "Seoul",
    "ap-northeast-3": "Osaka",
}

SERVICE_LABELS = [
    ("ec2", "EC2"),
    ("rds", "RDS"),
    ("vpc", "VPC"),
    ("vpc_outbound_ips", "NAT/IPs salida"),
    ("s3", "S3"),
    ("iam_users", "IAM"),
    ("lambda", "Lambda"),
    ("api_gateway", "API GW"),
    ("cloudformation", "CloudFormation"),
    ("ssm", "SSM"),
    ("kms", "KMS"),
    ("dynamodb", "DynamoDB"),
    ("sqs", "SQS"),
]

RESOURCE_OPTIONS = {
    "EC2 (Servidores)": "ec2",
    "RDS (Bases de datos)": "rds",
    "VPC (Redes)": "vpc",
    "NAT Gateways (IPs salida)": "vpc_outbound_ips",
    "S3 (Buckets)": "s3",
    "IAM Users": "iam_users",
    "Lambda (Funciones)": "lambda",
    "API Gateway": "api_gateway",
    "API Gateway -> Lambda": "api_gateway_routes",
    "CloudFormation": "cloudformation",
    "SSM (Parametros)": "ssm",
    "KMS (Claves)": "kms",
    "DynamoDB (Tablas)": "dynamodb",
    "SQS (Colas)": "sqs",
}

ALL_SERVICES_OPTION = "__all_services__"
DOWNLOAD_RESOURCE_OPTIONS = {
    "Todos los servicios": ALL_SERVICES_OPTION,
    **RESOURCE_OPTIONS,
}
DOWNLOAD_REFRESH_MODES = {
    "Faltantes o vencidos": "stale",
    "Forzar comparacion": "force",
    "Solo faltantes": "missing",
}

REGIONAL_COMPARISON_TARGET = {
    "account": "afex-prod",
    "left_region": "us-east-1",
    "left_label": "PROD / Virginia",
    "right_region": "us-east-2",
    "right_label": "CERT / Ohio",
}

REGIONAL_COMPARISON_SERVICES = [
    {
        "key": "ec2",
        "label": "EC2",
        "name_columns": ["nombre"],
        "config_columns": ["tipo", "estado", "vpc", "subnet"],
    },
    {
        "key": "rds",
        "label": "RDS",
        "name_columns": ["nombre"],
        "config_columns": ["motor", "version", "tipo", "estado", "multi_az"],
    },
    {
        "key": "vpc",
        "label": "VPC",
        "name_columns": ["nombre"],
        "config_columns": ["cidr", "estado", "subnets", "default"],
    },
    {
        "key": "vpc_outbound_ips",
        "label": "NAT/IPs salida",
        "name_columns": ["name", "resource_id"],
        "config_columns": ["type", "state", "public_ip", "vpc_id", "subnet_id"],
    },
    {
        "key": "lambda",
        "label": "Lambda",
        "name_columns": ["nombre"],
        "config_columns": ["handler", "runtime", "timeout_s", "vpc", "subnets", "estado"],
    },
    {
        "key": "api_gateway",
        "label": "API Gateway",
        "name_columns": ["nombre"],
        "config_columns": ["tipo", "estado", "rutas", "integraciones_lambda", "lambdas"],
    },
    {
        "key": "cloudformation",
        "label": "CloudFormation",
        "name_columns": ["nombre"],
        "config_columns": ["estado"],
    },
    {
        "key": "ssm",
        "label": "SSM",
        "name_columns": ["nombre"],
        "config_columns": ["tipo", "tier", "version", "data_type"],
    },
    {
        "key": "kms",
        "label": "KMS",
        "name_columns": ["alias", "arn", "key_id"],
        "config_columns": ["estado", "manager", "origen", "es_simetrica"],
    },
    {
        "key": "dynamodb",
        "label": "DynamoDB",
        "name_columns": ["nombre"],
        "config_columns": ["estado", "billing_mode", "lectura", "escritura"],
    },
    {
        "key": "sqs",
        "label": "SQS",
        "name_columns": ["nombre"],
        "config_columns": ["fifo", "kms_key_id"],
    },
]


def get_account_regions(account_name):
    """Retorna las regiones descubiertas para una cuenta con fallback seguro."""
    discovery = cache_manager.load_discovery() or {}
    for account in discovery.get("accounts", []):
        if account.get("name") == account_name:
            regions = account.get("regions") or []
            if regions:
                return regions
    return PERFILES.get(account_name, {}).get("regiones") or ["us-east-1"]


def get_account_display_label(account_name):
    """Retorna etiqueta legible para el selector de cuenta."""
    if account_name == ALL_ACCOUNTS_OPTION:
        return "Todas las cuentas"
    return account_name


def get_selected_account_names(account_name):
    """Expande la opcion global a la lista real de cuentas."""
    if account_name == ALL_ACCOUNTS_OPTION:
        return list(PERFILES.keys())
    return [account_name]


def _safe_export_slug(value):
    """Convierte nombres de cuenta/vista en slugs seguros para archivos."""
    text = str(value or "export").strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    return text.strip("_") or "export"


def build_excel_export_path(export_scope):
    """Crea una ruta unica para evitar bloqueos de archivos Excel abiertos."""
    EXPORT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return EXPORT_DIR / f"{_safe_export_slug(export_scope)}_{timestamp}.xlsx"


def get_global_region(account_name):
    """Retorna la region base donde se guardan servicios globales."""
    return PERFILES.get(account_name, {}).get("region") or "us-east-1"


def get_region_display_label(region_code):
    """Retorna el codigo de region con un nombre legible."""
    region_name = REGION_DISPLAY_NAMES.get(region_code)
    if region_name:
        return f"{region_code} ({region_name})"
    return region_code


def get_scope_display_label(region_code):
    """Retorna una etiqueta amigable para el alcance seleccionado."""
    if region_code == ALL_REGIONS_OPTION:
        return "Todas las regiones"
    return get_region_display_label(region_code)


def get_prioritized_regions(account_name):
    """Ordena regiones priorizando Virginia/Ohio y luego el resto alfabeticamente."""
    if account_name == ALL_ACCOUNTS_OPTION:
        regions = []
        for real_account in get_selected_account_names(account_name):
            regions.extend(get_account_regions(real_account))
        regions = list(dict.fromkeys(regions))
        prioritized = [region for region in PRIORITY_REGIONS if region in regions]
        remaining = sorted(region for region in regions if region not in prioritized)
        return prioritized + remaining

    regions = list(dict.fromkeys(get_account_regions(account_name)))
    prioritized = [region for region in PRIORITY_REGIONS if region in regions]
    remaining = sorted(region for region in regions if region not in prioritized)
    return prioritized + remaining


def get_region_selector_options(account_name):
    """Retorna opciones del selector con una vista consolidada al inicio."""
    return [ALL_REGIONS_OPTION] + get_prioritized_regions(account_name)


def get_download_regions(selected_region):
    """Convierte el selector de region en filtro para el motor de descarga."""
    if selected_region == ALL_REGIONS_OPTION:
        return None
    return [selected_region]


def get_download_resources(selected_service):
    """Convierte el selector de servicio en filtro para el motor de descarga."""
    if selected_service == ALL_SERVICES_OPTION:
        return None
    return [selected_service]


def show_download_result(result):
    """Muestra el resultado consolidado de una descarga."""
    if result.get("status") == "failed":
        st.error(f"Error: {result.get('error', 'Error desconocido')}")
        return

    completed = result.get("completed", 0)
    failed = result.get("failed", 0)
    partial = result.get("partial", 0)
    summary = result.get("changes_summary", {})
    summary_text = (
        f"{completed} completadas, {partial} parciales, {failed} fallidas | "
        f"{summary.get('new', 0)} nuevas, "
        f"{summary.get('updated', 0)} actualizadas, "
        f"{summary.get('unchanged', 0)} sin cambios, "
        f"{summary.get('skipped', 0)} omitidas"
    )

    if failed == 0 and partial == 0:
        st.success(summary_text)
    else:
        st.warning(summary_text)

    download_errors = []
    for detail in result.get("details", []):
        for error in detail.get("errors", []):
            download_errors.append(f"{detail['account']} / {detail['region']} -> {error}")

    if download_errors:
        st.caption("Errores detectados durante la descarga")
        st.code("\n".join(download_errors[:50]), language=None)


def get_service_region(account_name, selected_region, service_key):
    """Resuelve la region correcta para el servicio solicitado."""
    if service_key in GLOBAL_SERVICES:
        return get_global_region(account_name)
    return selected_region


def load_cached_count(account_name, region, service_key):
    """Obtiene la cantidad de filas cacheadas y su estado."""
    data, is_fresh, exists = cache_manager.get(account_name, region, service_key)
    count = len(data) if exists and isinstance(data, pd.DataFrame) else 0
    return count, is_fresh, exists


def load_cached_dataframe(account_name, region, service_key):
    """Retorna un DataFrame cacheado con metadatos de estado."""
    data, is_fresh, exists = cache_manager.get(account_name, region, service_key)
    if exists and isinstance(data, pd.DataFrame):
        return data.copy(), is_fresh, exists
    return pd.DataFrame(), is_fresh, exists


def summarize_cache_state(states):
    """Resume el estado de frescura de una coleccion de caches."""
    existing_states = [is_fresh for is_fresh, exists in states if exists]
    if not existing_states:
        return "Sin datos"
    if all(existing_states):
        return "Fresco"
    if any(existing_states):
        return "Mixto"
    return "Viejo"


def make_dataframe_concat_safe(df):
    """Normaliza tipos conflictivos para consolidar DataFrames de multiples regiones."""
    if df is None or df.empty:
        return df

    safe_df = df.copy()
    for column in safe_df.columns:
        series = safe_df[column]
        try:
            if getattr(series.dtype, "tz", None) is not None:
                safe_df[column] = series.astype(str)
            elif pd.api.types.is_datetime64_any_dtype(series):
                safe_df[column] = series.astype(str)
        except Exception:
            safe_df[column] = series.astype(str)

    return safe_df


def load_account_service_dataframe(account_name, service_key, selected_region):
    """Carga un servicio para una cuenta en una region puntual o consolidado."""
    if account_name == ALL_ACCOUNTS_OPTION:
        frames = []
        statuses = []
        exists_any = False
        for real_account in get_selected_account_names(account_name):
            account_df, account_status, account_exists = load_account_service_dataframe(
                real_account,
                service_key,
                selected_region,
            )
            statuses.append(account_status)
            exists_any = exists_any or account_exists
            if isinstance(account_df, pd.DataFrame) and not account_df.empty:
                frames.append(account_df)

        if not frames:
            return pd.DataFrame(), "Sin datos" if not exists_any else "Viejo", exists_any

        combined = pd.concat(frames, ignore_index=True)
        if all(status == "Fresco" for status in statuses if status != "Sin datos"):
            return combined, "Fresco", True
        if any(status == "Fresco" for status in statuses):
            return combined, "Mixto", True
        return combined, "Viejo", True

    if service_key in GLOBAL_SERVICES:
        global_region = get_global_region(account_name)
        data, is_fresh, exists = load_cached_dataframe(account_name, global_region, service_key)
        if exists and not data.empty:
            data = make_dataframe_concat_safe(data)
            if "cuenta" not in data.columns:
                data["cuenta"] = account_name
            if "region" not in data.columns:
                data["region"] = global_region
        return data, summarize_cache_state([(is_fresh, exists)]), exists

    if selected_region != ALL_REGIONS_OPTION:
        data, is_fresh, exists = load_cached_dataframe(account_name, selected_region, service_key)
        if exists and not data.empty:
            data = make_dataframe_concat_safe(data)
            if "cuenta" not in data.columns:
                data["cuenta"] = account_name
            if "region" not in data.columns:
                data["region"] = selected_region
        return data, summarize_cache_state([(is_fresh, exists)]), exists

    frames = []
    states = []
    for region in get_prioritized_regions(account_name):
        region_df, is_fresh, exists = load_cached_dataframe(account_name, region, service_key)
        states.append((is_fresh, exists))
        if exists and isinstance(region_df, pd.DataFrame) and not region_df.empty:
            region_df = make_dataframe_concat_safe(region_df)
            region_df["cuenta"] = account_name
            region_df["region"] = region
            frames.append(region_df)

    if not frames:
        return pd.DataFrame(), summarize_cache_state(states), any(exists for _, exists in states)

    combined = pd.concat(frames, ignore_index=True)
    return combined, summarize_cache_state(states), True


def build_account_region_summary(account_name):
    """Construye una tabla resumen de conteos por region para una cuenta."""
    regional_service_columns = [
        ("ec2", "EC2"),
        ("rds", "RDS"),
        ("vpc", "VPC"),
        ("lambda", "Lambda"),
        ("api_gateway", "API"),
        ("ssm", "SSM"),
        ("kms", "KMS"),
        ("dynamodb", "DynamoDB"),
        ("sqs", "SQS"),
        ("vpc_outbound_ips", "NAT/IPs"),
        ("cloudformation", "CloudFormation"),
    ]
    rows = []

    for region in get_prioritized_regions(account_name):
        row = {
            "Cuenta": account_name,
            "Region": get_region_display_label(region),
            "Total recursos": 0,
        }
        freshness_states = []

        for service_key, label in regional_service_columns:
            count, is_fresh, exists = load_cached_count(account_name, region, service_key)
            row[label] = count
            row["Total recursos"] += count
            freshness_states.append((is_fresh, exists))

        row["Estado cache"] = summarize_cache_state(freshness_states)
        rows.append(row)

    return pd.DataFrame(rows)


def render_metric_cards(metric_items, columns_count=5):
    """Renderiza tarjetas metricas en filas, usando el orden recibido."""
    cols = st.columns(columns_count)
    for idx, (display_name, count, status) in enumerate(metric_items):
        with cols[idx % columns_count]:
            if status:
                st.metric(display_name, count, delta=status)
            else:
                st.metric(display_name, count)


def build_summary_table_html(df):
    """Renderiza una tabla HTML con columnas numericas centradas."""
    if df is None or df.empty:
        return ""

    left_columns = {"Cuenta", "Region"}
    html_lines = ['<div class="summary-table-wrapper">', '<table class="summary-table">', "<thead>", "<tr>"]

    for column in df.columns:
        html_lines.append(f"<th>{column}</th>")

    html_lines.extend(["</tr>", "</thead>", "<tbody>"])

    for _, row in df.iterrows():
        html_lines.append("<tr>")
        for column in df.columns:
            value = row[column]
            classes = []
            if column not in left_columns:
                try:
                    numeric_value = float(value)
                    if numeric_value != 0:
                        classes.append("nonzero-cell")
                except (TypeError, ValueError):
                    pass

            class_attr = f' class="{" ".join(classes)}"' if classes else ""
            html_lines.append(f"<td{class_attr}>{value}</td>")
        html_lines.append("</tr>")

    html_lines.extend(["</tbody>", "</table>", "</div>"])
    return "".join(html_lines)


def normalize_component_name(value):
    """Genera una clave base para comparar componentes espejo entre regiones."""
    if value is None:
        return ""

    normalized = str(value).strip().lower()
    if not normalized:
        return ""

    normalized = normalized.replace("us-east-1", " ").replace("us-east-2", " ")
    normalized = normalized.replace("virginia", " ").replace("ohio", " ")
    normalized = re.sub(r"(^|[-_/.\s])(prod|cert)(?=$|[-_/.\s])", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def get_first_available_value(row, columns):
    """Obtiene el primer valor util de una lista de columnas candidatas."""
    for column in columns:
        if column not in row.index:
            continue
        value = row.get(column)
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text and text.lower() not in {"n/a", "none", "nan"}:
            return text
    return ""


def build_config_summary(row, columns):
    """Resume la configuracion principal de un recurso para comparacion rapida."""
    details = []
    for column in columns:
        if column not in row.index:
            continue
        value = row.get(column)
        if pd.isna(value):
            continue
        text = str(value).strip()
        if not text or text.lower() in {"n/a", "none", "nan"}:
            continue
        details.append(f"{column}={text}")
    return " | ".join(details) if details else "Sin detalle principal"


def prepare_regional_records(df, service_meta):
    """Convierte un DataFrame a registros listos para matching entre regiones."""
    records = {}
    duplicates = 0

    if df is None or df.empty:
        return records, duplicates

    name_columns = service_meta.get("name_columns", [])
    config_columns = service_meta.get("config_columns", [])

    for _, row in df.iterrows():
        display_name = get_first_available_value(row, name_columns)
        normalized_name = normalize_component_name(display_name)
        if normalized_name:
            comparison_key = normalized_name
        else:
            fallback_candidates = [
                row.get("id"),
                row.get("resource_id"),
                row.get("arn"),
                row.get("url"),
                row.get("key_id"),
            ]
            comparison_key = next(
                (
                    str(value).strip().lower()
                    for value in fallback_candidates
                    if value is not None and str(value).strip()
                ),
                "",
            )

        if not comparison_key:
            continue

        if comparison_key in records:
            duplicates += 1
            continue

        records[comparison_key] = {
            "nombre_mostrado": display_name or comparison_key,
            "config_principal": build_config_summary(row, config_columns),
        }

    return records, duplicates


def compare_regional_service(account_name, left_region, right_region, service_meta):
    """Compara un servicio entre dos regiones usando solo cache local."""
    service_key = service_meta["key"]
    left_df, left_fresh, left_exists = load_cached_dataframe(account_name, left_region, service_key)
    right_df, right_fresh, right_exists = load_cached_dataframe(account_name, right_region, service_key)

    left_records, left_duplicates = prepare_regional_records(left_df, service_meta)
    right_records, right_duplicates = prepare_regional_records(right_df, service_meta)

    all_keys = sorted(set(left_records.keys()) | set(right_records.keys()))
    rows = []
    only_left = 0
    only_right = 0
    shared_equal = 0
    shared_different = 0

    for key in all_keys:
        left_record = left_records.get(key)
        right_record = right_records.get(key)

        if left_record and right_record:
            same_config = left_record["config_principal"] == right_record["config_principal"]
            status = "En ambas - coincide" if same_config else "En ambas - config distinta"
            if same_config:
                shared_equal += 1
            else:
                shared_different += 1
            display_name = left_record["nombre_mostrado"] or right_record["nombre_mostrado"]
        elif left_record:
            status = f"Solo {REGIONAL_COMPARISON_TARGET['left_label']}"
            only_left += 1
            display_name = left_record["nombre_mostrado"]
        else:
            status = f"Solo {REGIONAL_COMPARISON_TARGET['right_label']}"
            only_right += 1
            display_name = right_record["nombre_mostrado"]

        rows.append(
            {
                "Componente Base": key,
                "Nombre Detectado": display_name,
                "Estado": status,
                REGIONAL_COMPARISON_TARGET["left_label"]: (
                    left_record["config_principal"] if left_record else "No existe"
                ),
                REGIONAL_COMPARISON_TARGET["right_label"]: (
                    right_record["config_principal"] if right_record else "No existe"
                ),
            }
        )

    results_df = pd.DataFrame(rows)
    if not results_df.empty:
        results_df = results_df.sort_values(
            by=["Estado", "Nombre Detectado", "Componente Base"],
            kind="stable",
        ).reset_index(drop=True)

    return {
        "service_key": service_key,
        "label": service_meta["label"],
        "left_exists": left_exists,
        "right_exists": right_exists,
        "left_fresh": left_fresh,
        "right_fresh": right_fresh,
        "left_count": len(left_df),
        "right_count": len(right_df),
        "only_left": only_left,
        "only_right": only_right,
        "shared_equal": shared_equal,
        "shared_different": shared_different,
        "left_duplicates": left_duplicates,
        "right_duplicates": right_duplicates,
        "results_df": results_df,
    }


def get_global_services_snapshot(account_name):
    """Resume los servicios globales de la cuenta para mostrarlos aparte."""
    global_region = get_global_region(account_name)
    rows = []
    for service_key, label in [("s3", "S3"), ("iam_users", "IAM Users")]:
        data, is_fresh, exists = load_cached_dataframe(account_name, global_region, service_key)
        rows.append(
            {
                "Servicio Global": label,
                "Region base": global_region,
                "Cantidad": len(data) if exists else 0,
                "Estado cache": "Fresco" if is_fresh else "Viejo" if exists else "Sin datos",
                "Nota": "No participa en la comparacion espejo entre regiones",
            }
        )
    return pd.DataFrame(rows)


def sanitize_dataframe_for_display(df):
    """Normaliza valores que suelen romper el renderizado de Streamlit."""
    if df is None or df.empty:
        return df

    sanitized = df.copy()

    for column in sanitized.columns:
        try:
            if pd.api.types.is_datetime64_any_dtype(sanitized[column]):
                if hasattr(sanitized[column].dtype, "tz") and sanitized[column].dtype.tz is not None:
                    sanitized[column] = sanitized[column].dt.tz_convert("UTC").dt.tz_localize(None)
        except Exception:
            try:
                sanitized[column] = sanitized[column].astype(str)
            except Exception:
                pass

    sanitized.columns = [str(column) for column in sanitized.columns]
    return sanitized


def ensure_monitoring_alert_columns(df):
    """Asegura columnas de alertas en tablas de infraestructura."""
    if df is None or df.empty:
        return df
    enriched = df.copy()
    defaults = {
        "alertas_configuradas": "Pendiente de descarga",
        "alertas_count": "",
        "alertas_email_configurado": "Pendiente de descarga",
        "alertas_nombres": "",
        "alertas_metricas": "",
        "alertas_acciones": "",
        "alertas_emails": "",
    }
    for column, default_value in defaults.items():
        if column not in enriched.columns:
            enriched[column] = default_value
    return enriched


def ensure_lambda_usage_columns(df):
    """Asegura columnas de ultimo uso Lambda aunque el cache sea anterior."""
    if df is None or df.empty:
        return df
    enriched = df.copy()
    defaults = {
        "ultima_invocacion": "",
        "invocaciones_30d": "",
        "dias_desde_ultima_invocacion": "",
        "estado_uso": "Pendiente de descarga",
        "ventana_uso_dias": "",
    }
    for column, default_value in defaults.items():
        if column not in enriched.columns:
            enriched[column] = default_value
    return enriched


def order_lambda_columns(df):
    """Mueve las columnas de uso Lambda cerca del identificador principal."""
    if df is None or df.empty:
        return df
    ordered_df = df.copy()
    if "runtime" in ordered_df.columns:
        ordered_df["runtime_objetivo"] = ordered_df["runtime"].astype(str).str.lower().map(
            LAMBDA_RUNTIME_UPGRADE_RECOMMENDATIONS
        ).fillna("")
    preferred_columns = [
        "nombre",
        "arn",
        "region",
        "runtime",
        "runtime_objetivo",
        "estado",
        "ultima_invocacion",
        "invocaciones_30d",
        "dias_desde_ultima_invocacion",
        "estado_uso",
        "ventana_uso_dias",
        "ultima_modificacion",
        "fecha_ultima_modificacion",
        "creacion",
        "fecha_creacion",
    ]
    ordered_columns = [column for column in preferred_columns if column in ordered_df.columns]
    ordered_columns += [column for column in ordered_df.columns if column not in ordered_columns]
    return ordered_df[ordered_columns]


def format_bytes_human(value):
    """Convierte bytes a una lectura compacta en KB/MB/GB/TB."""
    if pd.isna(value):
        return ""
    try:
        size = float(value)
    except (TypeError, ValueError):
        return ""
    if size < 0:
        return ""

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{size:.0f} {units[unit_index]}"
    return f"{size:.2f} {units[unit_index]}"


def add_dynamodb_readable_size(df):
    """Agrega tamano legible junto a tamano_bytes para DynamoDB."""
    if df is None or df.empty or "tamano_bytes" not in df.columns:
        return df
    enriched = df.copy()
    enriched["tamano_legible"] = enriched["tamano_bytes"].apply(format_bytes_human)
    ordered_columns = []
    for column in enriched.columns:
        if column == "tamano_legible":
            continue
        ordered_columns.append(column)
        if column == "tamano_bytes":
            ordered_columns.append("tamano_legible")
    return enriched[[column for column in ordered_columns if column in enriched.columns]]


def format_integer_thousands_es(value):
    """Formatea enteros con separador de miles latino."""
    if pd.isna(value):
        return ""
    try:
        return f"{float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return value


def ensure_iam_access_columns(df):
    """Asegura y ordena columnas de ultimo acceso IAM."""
    if df is None or df.empty:
        return df
    enriched = df.copy()
    defaults = {
        "ultimo_acceso_cuenta": "Pendiente de descarga",
        "ultimo_acceso_consola": "",
        "ultimo_uso_access_key": "",
    }
    for column, default_value in defaults.items():
        if column not in enriched.columns:
            enriched[column] = default_value

    preferred_columns = [
        "username",
        "arn",
        "ultimo_acceso_cuenta",
        "ultimo_acceso_consola",
        "ultimo_uso_access_key",
        "mfa_enabled",
        "access_keys",
        "creacion",
        "usuario_creador",
        "fecha_creacion",
        "fecha_ultima_modificacion",
    ]
    ordered_columns = [column for column in preferred_columns if column in enriched.columns]
    ordered_columns += [column for column in enriched.columns if column not in ordered_columns]
    return enriched[ordered_columns]


LAMBDA_USAGE_CLASSIFICATION_ORDER = ["sin invocacion", "2025", "Ene - Abr", "May", "Jun"]
LAMBDA_USAGE_CLASSIFICATION_COLORS = {
    "sin invocacion": "#f4cccc",
    "2025": "#f4cccc",
    "Ene - Abr": "#fce5cd",
    "May": "#d9ead3",
    "Jun": "#d9ead3",
}
LAMBDA_USAGE_CLASSIFICATION_DETAILS = {
    "Jun": "Uso reciente, priorizar actualizacion",
    "May": "Uso reciente moderado",
    "Ene - Abr": "Baja actividad, revisar necesidad",
    "2025": "Candidato a eliminar",
    "sin invocacion": "Candidato a eliminar",
}


def _split_region_code_and_name(region_value):
    """Separa una region renderizada como codigo y nombre corto."""
    region_text = str(region_value or "").strip()
    if not region_text:
        return "", ""
    if "(" in region_text and region_text.endswith(")"):
        code, name = region_text.rsplit("(", 1)
        return code.strip(), name.rstrip(")").strip()
    return region_text, REGION_DISPLAY_NAMES.get(region_text, "")


def classify_lambda_usage(last_invoked_at, usage_status):
    """Clasifica uso Lambda en los tramos operativos usados para priorizar."""
    status_text = str(usage_status or "").strip().lower()
    last_invoked_text = str(last_invoked_at or "").strip()
    if (
        not last_invoked_text
        or last_invoked_text.lower() in {"none", "nan", "nat"}
        or "sin invocaciones" in status_text
    ):
        return "sin invocacion"

    last_invoked = pd.to_datetime(last_invoked_text, errors="coerce", utc=True)
    if pd.isna(last_invoked):
        return "sin invocacion"

    year = int(last_invoked.year)
    month = int(last_invoked.month)
    if year <= 2025:
        return "2025"
    if year == 2026 and month <= 4:
        return "Ene - Abr"
    if year == 2026 and month == 5:
        return "May"
    if year == 2026 and month == 6:
        return "Jun"
    return f"{year}-{month:02d}"


def prepare_vulnerability_technical_display(df):
    """Ordena y enriquece la tabla tecnica para lectura operativa tipo Excel."""
    if df is None or df.empty:
        return df

    prepared = df.copy()
    if "Region" in prepared.columns:
        region_parts = prepared["Region"].apply(_split_region_code_and_name)
        prepared["Region2"] = region_parts.apply(lambda value: value[1])
        prepared["Region"] = region_parts.apply(lambda value: value[0])

    prepared["Clasificacion uso Lambda"] = ""
    prepared["Detalle clasificacion Lambda"] = ""
    lambda_mask = prepared["Servicio"].astype(str).eq("Lambda") if "Servicio" in prepared.columns else False
    if isinstance(lambda_mask, pd.Series) and lambda_mask.any():
        prepared.loc[lambda_mask, "Clasificacion uso Lambda"] = prepared.loc[lambda_mask].apply(
            lambda row: classify_lambda_usage(
                row.get("Lambda last invoked at"),
                row.get("Lambda usage status"),
            ),
            axis=1,
        )
        prepared.loc[lambda_mask, "Detalle clasificacion Lambda"] = prepared.loc[
            lambda_mask,
            "Clasificacion uso Lambda",
        ].map(LAMBDA_USAGE_CLASSIFICATION_DETAILS).fillna("Revisar manualmente")

    preferred_columns = [
        "Clasificacion uso Lambda",
        "Detalle clasificacion Lambda",
        "Lambda invocations 30d",
        "Cuenta",
        "Region2",
        "Region",
        "Servicio",
        "Tipo de recurso",
        "Recurso",
        "Tipo hallazgo",
        "Finding Type",
        "Version actual",
        "Version objetivo",
        "Lambda last updated at",
        "Lambda last invoked at",
        "Lambda idle days",
        "Lambda usage status",
        "Producto",
        "Origen producto",
        "Confianza producto",
    ]
    ordered_columns = [column for column in preferred_columns if column in prepared.columns]
    ordered_columns += [column for column in VULNERABILITY_TECHNICAL_COLUMNS if column in prepared.columns and column not in ordered_columns]
    return prepared[ordered_columns]


def add_lambda_usage_classification_for_export(df):
    """Agrega clasificacion Lambda a exports manteniendo el resto de columnas."""
    if df is None or df.empty:
        return df

    exported = df.copy()
    exported["Clasificacion uso Lambda"] = ""
    exported["Detalle clasificacion Lambda"] = ""

    lambda_mask = exported["Servicio"].astype(str).eq("Lambda") if "Servicio" in exported.columns else False
    if isinstance(lambda_mask, pd.Series) and lambda_mask.any():
        exported.loc[lambda_mask, "Clasificacion uso Lambda"] = exported.loc[lambda_mask].apply(
            lambda row: classify_lambda_usage(
                row.get("Lambda last invoked at"),
                row.get("Lambda usage status"),
            ),
            axis=1,
        )
        exported.loc[lambda_mask, "Detalle clasificacion Lambda"] = exported.loc[
            lambda_mask,
            "Clasificacion uso Lambda",
        ].map(LAMBDA_USAGE_CLASSIFICATION_DETAILS).fillna("Revisar manualmente")

    leading_columns = ["Clasificacion uso Lambda", "Detalle clasificacion Lambda"]
    ordered_columns = leading_columns + [column for column in exported.columns if column not in leading_columns]
    return exported[ordered_columns]


def style_lambda_usage_classification(df):
    """Aplica color suave a filas Lambda segun clasificacion de uso."""
    if df is None or df.empty or "Clasificacion uso Lambda" not in df.columns:
        return df

    def format_integer_es(value):
        if pd.isna(value):
            return ""
        try:
            return f"{float(value):,.0f}".replace(",", ".")
        except (TypeError, ValueError):
            return value

    def style_row(row):
        classification = str(row.get("Clasificacion uso Lambda") or "")
        color = LAMBDA_USAGE_CLASSIFICATION_COLORS.get(classification)
        if not color:
            return [""] * len(row)
        return [
            f"background-color: {color}" if column in {
                "Clasificacion uso Lambda",
                "Detalle clasificacion Lambda",
                "Lambda last invoked at",
                "Lambda invocations 30d",
                "Lambda idle days",
                "Lambda usage status",
            } else ""
            for column in row.index
        ]

    styled = df.style.apply(style_row, axis=1)
    if "Lambda invocations 30d" in df.columns:
        styled = styled.format({"Lambda invocations 30d": format_integer_es})
    return styled


def _selected_regions_for_scope(account_name, selected_region):
    """Retorna las regiones concretas cubiertas por el selector actual."""
    if selected_region == ALL_REGIONS_OPTION:
        return get_prioritized_regions(account_name)
    return [selected_region]


def _service_regions_for_scope(account_name, selected_region, service_key):
    """Retorna regiones donde buscar un servicio, respetando global/regional."""
    if service_key in GLOBAL_SERVICES:
        return [get_global_region(account_name)]
    return _selected_regions_for_scope(account_name, selected_region)


def _load_service_scope_rows(account_name, selected_region, service_key, display_name):
    """Carga filas cacheadas de un servicio y agrega metadatos de cuenta/region."""
    rows = []
    for real_account in get_selected_account_names(account_name):
        for region in _service_regions_for_scope(real_account, selected_region, service_key):
            data, is_fresh, exists = load_cached_dataframe(real_account, region, service_key)
            if not (exists and isinstance(data, pd.DataFrame) and not data.empty):
                continue
            service_df = make_dataframe_concat_safe(data)
            service_df["cuenta"] = real_account
            if "region" not in service_df.columns:
                service_df["region"] = region
            service_df["servicio"] = display_name
            service_df["cache_fresco"] = is_fresh
            rows.append(service_df)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def build_coverage_dataframe(account_name, selected_region):
    """Construye matriz de cobertura de cache por servicio y region."""
    rows = []
    for service_key, display_name, is_global in ANALYTICS_SERVICE_LABELS:
        for region in _service_regions_for_scope(account_name, selected_region, service_key):
            data, is_fresh, exists = load_cached_dataframe(account_name, region, service_key)
            row_count = len(data) if exists and isinstance(data, pd.DataFrame) else 0
            if exists and row_count > 0:
                status = "Descargado"
            elif exists:
                status = "Descargado sin recursos"
            else:
                status = "Falta descargar"
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": region,
                    "Servicio": display_name,
                    "Tipo": "Global" if is_global else "Regional",
                    "Estado": status,
                    "Registros": row_count,
                    "Cache": "Fresco" if is_fresh else "Viejo" if exists else "Sin datos",
                }
            )
    return pd.DataFrame(rows)


def _normalize_tags(value):
    """Convierte tags AWS comunes a dict simple."""
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return {str(key): str(val) for key, val in value.items()}
    if isinstance(value, list):
        normalized = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            key = item.get("Key") or item.get("key")
            val = item.get("Value") or item.get("value") or ""
            if key:
                normalized[str(key)] = str(val)
        return normalized
    return {}


def _extract_row_tags(row):
    """Extrae tags desde columnas conocidas o columnas tag:<nombre>."""
    tags = {}
    for column in TAG_COLUMN_CANDIDATES:
        if column in row.index:
            tags.update(_normalize_tags(row.get(column)))
    for column in row.index:
        column_text = str(column)
        if column_text.lower().startswith("tag:"):
            key = column_text.split(":", 1)[1]
            value = row.get(column)
            if value is not None and str(value).strip():
                tags[key] = str(value)
    return tags


def _resource_identifier(row):
    """Obtiene un identificador legible para hallazgos."""
    for column in ["nombre", "name", "id", "resource_id", "arn", "url", "username", "key_id"]:
        if column in row.index:
            value = row.get(column)
            if value is not None and str(value).strip():
                return str(value)
    return "Sin identificador"


def _first_available_row_value(row, columns):
    """Retorna el primer valor no vacio disponible en una fila."""
    for column in columns:
        if column not in row.index:
            continue
        value = row.get(column)
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text and text.lower() not in {"none", "nan", "nat", "n/a"}:
            return text
    return ""


def _component_last_usage(row):
    """Obtiene la mejor senal disponible de ultimo llamado, uso o actividad."""
    return _first_available_row_value(
        row,
        [
            "ultima_invocacion",
            "lambda_last_invoked_at",
            "Lambda last invoked at",
            "fecha_ultima_modificacion",
            "ultima_modificacion",
            "ultima_actualizacion",
            "LastUpdated",
            "last_updated",
            "creacion",
            "fecha_creacion",
            "creationTime",
            "launchTime",
        ],
    )


def _build_lambda_last_usage_lookup(lambda_df):
    """Indexa ultimos llamados Lambda por nombre y ARN."""
    lookup = {}
    if lambda_df is None or lambda_df.empty:
        return lookup
    for _, row in lambda_df.iterrows():
        last_usage = _component_last_usage(row)
        if not last_usage:
            continue
        for column in ["nombre", "arn"]:
            value = row.get(column)
            if value is not None and str(value).strip():
                lookup[str(value).strip()] = last_usage
    return lookup


def build_tag_compliance_dataframe(account_name, selected_region):
    """Construye analisis transversal de tags obligatorios."""
    rows = []
    for service_key, display_name, _ in ANALYTICS_SERVICE_LABELS:
        data = _load_service_scope_rows(account_name, selected_region, service_key, display_name)
        if data.empty:
            continue
        for _, row in data.iterrows():
            tags = _extract_row_tags(row)
            present_required_tags = [tag for tag in MANDATORY_TAGS if tags.get(tag)]
            missing_tags = [tag for tag in MANDATORY_TAGS if not tags.get(tag)]
            compliance_ratio = len(present_required_tags) / len(MANDATORY_TAGS)
            if compliance_ratio == 1:
                tag_status = "Cumple"
            elif tags:
                tag_status = "Validado con faltantes"
            else:
                tag_status = "Sin evidencia de tags"
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": display_name,
                    "Recurso": _resource_identifier(row),
                    "Estado tags": tag_status,
                    "Tags obligatorios presentes": (
                        f"{len(present_required_tags)} de {len(MANDATORY_TAGS)} "
                        f"({compliance_ratio:.0%})"
                    ),
                    "Tags presentes": ", ".join(present_required_tags) if present_required_tags else "Ninguno",
                    "Tags faltantes": ", ".join(missing_tags) if missing_tags else "Ninguno",
                    "Cumple tags": tag_status == "Cumple",
                    "Evidencia disponible": "Si" if tags else "No",
                    **{f"Tag {tag}": tags.get(tag, "") for tag in MANDATORY_TAGS},
                }
            )
    return pd.DataFrame(rows)


def _get_numeric(row, columns, default=0):
    for column in columns:
        if column in row.index:
            try:
                return float(row.get(column) or 0)
            except (TypeError, ValueError):
                return default
    return default


def build_billing_recommendations_dataframe(account_name, selected_region):
    """Genera hallazgos FinOps desde el inventario cacheado."""
    rows = []

    ec2_df = _load_service_scope_rows(account_name, selected_region, "ec2", "EC2")
    for _, row in ec2_df.iterrows():
        if str(row.get("estado", "")).lower() == "stopped":
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": "EC2",
                    "Recurso": _resource_identifier(row),
                    "Hallazgo": "Instancia detenida",
                    "Accion recomendada": "Validar si puede eliminarse, apagarse definitivamente o convertir a AMI.",
                    "Prioridad": "Media",
                }
            )
        if str(row.get("monitoringState", "")).lower() == "disabled":
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": "EC2",
                    "Recurso": _resource_identifier(row),
                    "Hallazgo": "Monitoreo detallado deshabilitado",
                    "Accion recomendada": "Revisar si requiere metricas detalladas antes de optimizar capacidad.",
                    "Prioridad": "Baja",
                }
            )

    nat_df = _load_service_scope_rows(account_name, selected_region, "vpc_outbound_ips", "NAT/IPs")
    for _, row in nat_df.iterrows():
        if row.get("type") == "Elastic IP" and row.get("state") == "available":
            public_ip = row.get("public_ip", "")
            allocation_id = row.get("allocation_id", "")
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": "Elastic IP",
                    "Recurso": public_ip or allocation_id or _resource_identifier(row),
                    "Hallazgo": "Elastic IP disponible sin asociacion",
                    "Accion recomendada": (
                        f"Liberar si no esta reservada para una actividad planificada. "
                        f"AllocationId: {allocation_id or 'N/A'}"
                    ),
                    "Prioridad": "Alta",
                }
            )
        if row.get("type") == "NAT Gateway" and row.get("state") != "available":
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": "NAT Gateway",
                    "Recurso": _resource_identifier(row),
                    "Hallazgo": f"NAT Gateway en estado {row.get('state')}",
                    "Accion recomendada": "Confirmar si corresponde mantenerlo o limpiar recursos asociados.",
                    "Prioridad": "Media",
                }
            )

    rds_df = _load_service_scope_rows(account_name, selected_region, "rds", "RDS")
    for _, row in rds_df.iterrows():
        storage = _get_numeric(row, ["almacenamiento_gb"])
        if storage >= 1000:
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": "RDS",
                    "Recurso": _resource_identifier(row),
                    "Hallazgo": f"Almacenamiento alto ({storage:.0f} GB)",
                    "Accion recomendada": "Revisar metricas de uso, retencion y politica de snapshots.",
                    "Prioridad": "Media",
                }
            )
        if str(row.get("estado", "")).lower() not in {"available", "storage-optimization"}:
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": "RDS",
                    "Recurso": _resource_identifier(row),
                    "Hallazgo": f"Estado no disponible: {row.get('estado')}",
                    "Accion recomendada": "Validar si genera costo sin entregar servicio.",
                    "Prioridad": "Alta",
                }
            )

    dynamodb_df = _load_service_scope_rows(account_name, selected_region, "dynamodb", "DynamoDB")
    for _, row in dynamodb_df.iterrows():
        if str(row.get("billing_mode", "")).upper() == "PROVISIONED":
            rows.append(
                {
                    "Cuenta": account_name,
                    "Region": row.get("region", ""),
                    "Servicio": "DynamoDB",
                    "Recurso": _resource_identifier(row),
                    "Hallazgo": "Tabla en modo PROVISIONED",
                    "Accion recomendada": "Comparar consumo real contra capacidad provisionada o evaluar on-demand.",
                    "Prioridad": "Media",
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=["Cuenta", "Region", "Servicio", "Recurso", "Hallazgo", "Accion recomendada", "Prioridad"]
        )
    return pd.DataFrame(rows)


def fetch_cost_explorer_dataframe(account_name):
    """Consulta Cost Explorer para la cuenta seleccionada si existen permisos."""
    if account_name == ALL_ACCOUNTS_OPTION:
        frames = []
        for real_account in get_selected_account_names(account_name):
            account_df = fetch_cost_explorer_dataframe(real_account)
            if not account_df.empty:
                account_df["Cuenta"] = real_account
                frames.append(account_df)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    profile_name = PERFILES.get(account_name, {}).get("perfil")
    if not profile_name:
        return pd.DataFrame()

    session = boto3.Session(profile_name=profile_name)
    client = session.client("ce", region_name="us-east-1")
    today = date.today()
    end_date = today + timedelta(days=1)
    start_month = (today.replace(day=1) - timedelta(days=90)).replace(day=1)

    response = client.get_cost_and_usage(
        TimePeriod={"Start": start_month.isoformat(), "End": end_date.isoformat()},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[
            {"Type": "DIMENSION", "Key": "SERVICE"},
            {"Type": "DIMENSION", "Key": "REGION"},
        ],
    )

    rows = []
    for period in response.get("ResultsByTime", []):
        month = period.get("TimePeriod", {}).get("Start")
        for group in period.get("Groups", []):
            service, region = (group.get("Keys") or ["Sin servicio", "Sin region"])[:2]
            metric = group.get("Metrics", {}).get("UnblendedCost", {})
            rows.append(
                {
                    "Cuenta": account_name,
                    "Mes": month,
                    "Servicio": service,
                    "Region": region or "Global",
                    "Costo USD": float(metric.get("Amount", 0)),
                    "Moneda": metric.get("Unit", "USD"),
                }
            )
    return pd.DataFrame(rows)


def _current_and_previous_months(cost_df):
    """Retorna etiquetas de mes actual y anterior segun datos consultados."""
    if cost_df.empty or "Mes" not in cost_df.columns:
        return None, None
    months = sorted(cost_df["Mes"].dropna().astype(str).unique())
    if not months:
        return None, None
    current_month = months[-1]
    previous_month = months[-2] if len(months) > 1 else None
    return current_month, previous_month


def build_cost_dashboard_metrics(cost_df):
    """Calcula KPIs ejecutivos para Billing."""
    if cost_df.empty:
        return {
            "current_month": None,
            "current_total": 0.0,
            "previous_total": 0.0,
            "variation_pct": 0.0,
            "active_services": 0,
        }

    current_month, previous_month = _current_and_previous_months(cost_df)
    current_df = cost_df[cost_df["Mes"] == current_month] if current_month else pd.DataFrame()
    previous_df = cost_df[cost_df["Mes"] == previous_month] if previous_month else pd.DataFrame()
    current_total = float(current_df["Costo USD"].sum()) if not current_df.empty else 0.0
    previous_total = float(previous_df["Costo USD"].sum()) if not previous_df.empty else 0.0
    variation_pct = ((current_total - previous_total) / previous_total * 100) if previous_total else 0.0
    active_services = int(current_df[current_df["Costo USD"] > 0]["Servicio"].nunique()) if not current_df.empty else 0

    return {
        "current_month": current_month,
        "current_total": current_total,
        "previous_total": previous_total,
        "variation_pct": variation_pct,
        "active_services": active_services,
    }


def filter_costs_by_selected_scope(cost_df, selected_region):
    """Filtra costos por region cuando el usuario selecciona una region puntual."""
    if cost_df.empty or selected_region == ALL_REGIONS_OPTION:
        return cost_df
    valid_regions = {selected_region, get_region_display_label(selected_region), "Global", "NoRegion", ""}
    return cost_df[cost_df["Region"].fillna("").isin(valid_regions)]


def get_current_month_costs(cost_df):
    """Obtiene costos del mes mas reciente disponible."""
    current_month, _ = _current_and_previous_months(cost_df)
    if not current_month:
        return pd.DataFrame()
    return cost_df[cost_df["Mes"] == current_month].copy()


def map_cost_service_to_inventory_service(service_name):
    """Mapea nombres de Cost Explorer a servicios del inventario para estimaciones."""
    text = str(service_name or "").lower()
    mapping = [
        ("DynamoDB", ["dynamodb"]),
        ("Lambda", ["lambda"]),
        ("RDS", ["relational database", "rds"]),
        ("S3", ["simple storage", " s3", "amazon s3"]),
        ("SQS", ["simple queue", "sqs"]),
        ("API Gateway", ["api gateway"]),
        ("VPC", ["vpc", "nat gateway", "elastic ip", "data transfer"]),
        ("EC2", ["ec2", "elastic compute", "compute cloud"]),
        ("KMS", ["key management", "kms"]),
        ("CloudFormation", ["cloudformation"]),
        ("SSM", ["systems manager", "ssm"]),
        ("IAM Users", ["identity and access", "iam"]),
    ]
    for inventory_service, needles in mapping:
        if any(needle in text for needle in needles):
            return inventory_service
    return ""


def build_cost_by_service_dataframe(cost_df):
    """Agrupa costo del mes actual por servicio AWS."""
    current_df = get_current_month_costs(cost_df)
    if current_df.empty:
        return pd.DataFrame(columns=["Servicio", "Costo USD", "% del Total"])
    grouped = (
        current_df.groupby("Servicio", as_index=False)["Costo USD"]
        .sum()
        .sort_values("Costo USD", ascending=False)
    )
    total = grouped["Costo USD"].sum()
    grouped["% del Total"] = grouped["Costo USD"].apply(lambda value: (value / total * 100) if total else 0)
    return grouped


def build_estimated_product_cost_dataframe(account_name, selected_region, cost_df):
    """Estima costo por producto distribuyendo costo por servicio segun recursos detectados."""
    product_df = build_product_inventory_dataframe(account_name, selected_region)
    current_df = get_current_month_costs(filter_costs_by_selected_scope(cost_df, selected_region))
    if product_df.empty or current_df.empty:
        return pd.DataFrame(columns=["Producto", "Recursos", "Costo Mensual USD", "% del Total", "Metodo"])

    current_df = current_df.copy()
    current_df["Servicio inventario"] = current_df["Servicio"].apply(map_cost_service_to_inventory_service)
    mapped_costs = (
        current_df[current_df["Servicio inventario"] != ""]
        .groupby("Servicio inventario", as_index=False)["Costo USD"]
        .sum()
    )

    allocation_rows = []
    for _, cost_row in mapped_costs.iterrows():
        inventory_service = cost_row["Servicio inventario"]
        service_resources = product_df[product_df["Servicio"] == inventory_service]
        if service_resources.empty:
            continue
        counts = service_resources.groupby("Producto", as_index=False).size()
        total_count = counts["size"].sum()
        if total_count <= 0:
            continue
        for _, count_row in counts.iterrows():
            allocation_rows.append(
                {
                    "Producto": count_row["Producto"],
                    "Recursos asignados": int(count_row["size"]),
                    "Costo asignado": float(cost_row["Costo USD"]) * int(count_row["size"]) / total_count,
                }
            )

    if not allocation_rows:
        return pd.DataFrame(columns=["Producto", "Recursos", "Costo Mensual USD", "% del Total", "Metodo"])

    allocation_df = pd.DataFrame(allocation_rows)
    product_resources = product_df.groupby("Producto", as_index=False).size()
    product_resources.columns = ["Producto", "Recursos"]
    summary = (
        allocation_df.groupby("Producto", as_index=False)
        .agg({"Costo asignado": "sum", "Recursos asignados": "sum"})
        .merge(product_resources, on="Producto", how="left")
    )
    total_cost = summary["Costo asignado"].sum()
    summary["Costo Mensual USD"] = summary["Costo asignado"]
    summary["% del Total"] = summary["Costo Mensual USD"].apply(lambda value: (value / total_cost * 100) if total_cost else 0)
    summary["Metodo"] = "Estimado por recursos del inventario"
    return summary[["Producto", "Recursos", "Costo Mensual USD", "% del Total", "Metodo"]].sort_values(
        "Costo Mensual USD",
        ascending=False,
    )


def _normalize_vulnerability_dataframe(rows):
    """Retorna hallazgos con columnas de gestion y detalle tecnico consistentes."""
    if not rows:
        return pd.DataFrame(columns=VULNERABILITY_COLUMNS)

    vulnerability_df = pd.DataFrame(rows)
    extraction_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for column in VULNERABILITY_COLUMNS:
        if column not in vulnerability_df.columns:
            vulnerability_df[column] = ""
    for index, row in vulnerability_df.iterrows():
        management = get_vulnerability_management_defaults(row, extraction_time)
        for column, value in management.items():
            if not str(vulnerability_df.at[index, column] or "").strip():
                vulnerability_df.at[index, column] = value
        product = get_vulnerability_product_defaults(row)
        for column, value in product.items():
            if not str(vulnerability_df.at[index, column] or "").strip():
                vulnerability_df.at[index, column] = value
    return vulnerability_df[VULNERABILITY_COLUMNS]


def get_vulnerability_product_defaults(row):
    """Asigna producto sugerido al hallazgo desde tags o nombre del recurso."""
    product_key = str(row.get("Producto key") or "").strip()
    product_name = str(row.get("Producto") or "").strip()
    if product_key and product_name:
        return {}

    candidates = [
        row.get("Resource tags"),
        row.get("Recurso"),
        row.get("Titulo"),
        row.get("Finding ARN"),
        row.get("Vulnerability Id"),
    ]
    for candidate in candidates:
        inferred_key, inferred_name, source, confidence = _infer_product_from_name(candidate)
        if inferred_key:
            return {
                "Producto key": inferred_key,
                "Producto": inferred_name,
                "Origen producto": source,
                "Confianza producto": confidence,
            }

    return {
        "Producto key": "sin_producto",
        "Producto": "Sin producto",
        "Origen producto": "Sin evidencia",
        "Confianza producto": "Baja",
    }


def get_vulnerability_management_defaults(row, extraction_time):
    """Asigna responsable y estado de gestion inicial segun tipo de hallazgo."""
    finding_type = str(row.get("Tipo hallazgo") or row.get("Finding Type") or "").lower()
    service = str(row.get("Servicio") or "").lower()
    priority = str(row.get("Prioridad") or "").lower()
    exploit = str(row.get("Exploit disponible") or "").lower()
    fix = str(row.get("Fix disponible") or "").lower()

    owner = "Ciberseguridad"
    support = "Infraestructura / Desarrollo"
    if "lambda" in service and any(term in finding_type for term in ["runtime", "package", "layer"]):
        owner = "Desarrollo"
        support = "Infraestructura valida inventario; Ciberseguridad prioriza"
    elif "rds" in service and any(term in finding_type for term in ["motor", "engine", "version"]):
        owner = "Infraestructura + Desarrollo"
        support = "Ciberseguridad valida riesgo"
    elif "rds" in service:
        owner = "Infraestructura"
        support = "Desarrollo valida impacto; Ciberseguridad valida riesgo"
    elif "iam" in service:
        owner = "Infraestructura / Seguridad"
        support = "Dueno funcional valida uso"
    elif "s3" in service:
        owner = "Infraestructura / Seguridad"
        support = "Dueno del dato valida excepciones"

    internal_priority = "P3"
    if "critical" in priority or ("si" in exploit and "si" in fix):
        internal_priority = "P0"
    elif "alta" in priority or "high" in priority:
        internal_priority = "P1" if "si" in fix else "P2"
    elif "media" in priority or "medium" in priority:
        internal_priority = "P3"

    return {
        "Responsable sugerido": owner,
        "Apoyo": support,
        "Prioridad interna": internal_priority,
        "Estado remediacion": "Nuevo",
        "Evidencia cierre": "",
        "Riesgo aceptado": "No",
        "Comentario responsable": "",
        "Fuente hallazgo": "Inventario AWS",
        "Fecha extraccion": extraction_time,
    }


def build_vulnerability_dataframe(account_name, selected_region):
    """Genera hallazgos de version/configuracion desde inventario disponible."""
    rows = []

    lambda_df = _load_service_scope_rows(account_name, selected_region, "lambda", "Lambda")
    for _, row in lambda_df.iterrows():
        runtime = str(row.get("runtime", "")).strip()
        runtime_target = LAMBDA_RUNTIME_UPGRADE_RECOMMENDATIONS.get(runtime.lower())
        if runtime_target:
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": "Lambda",
                    "Tipo de recurso": "AWS Lambda function",
                    "Recurso": _resource_identifier(row),
                    "Titulo": f"Actualizar runtime Lambda {runtime}",
                    "Riesgo": f"Runtime obsoleto o deprecado: {runtime}",
                    "Severidad": "High",
                    "Version actual": runtime,
                    "Version objetivo": runtime_target,
                    "Estado": "Deprecado",
                    "Tipo hallazgo": "Runtime deprecado",
                    "Finding Type": "Inventario - Runtime deprecado",
                    "Fix disponible": "Si",
                    "Exploit disponible": "No evaluado",
                    "Lambda package type": row.get("package_type", ""),
                    "Lambda last updated at": row.get("ultima_modificacion", ""),
                    "Lambda last invoked at": row.get("ultima_invocacion", ""),
                    "Lambda invocations 30d": row.get("invocaciones_30d", ""),
                    "Lambda idle days": row.get("dias_desde_ultima_invocacion", ""),
                    "Lambda usage status": row.get("estado_uso", ""),
                    "Accion recomendada": LAMBDA_RUNTIME_UPGRADE_ACTION,
                    "Evidencia requerida": LAMBDA_RUNTIME_EVIDENCE,
                    "Prioridad": "Alta",
                }
            )
        if str(row.get("estado_ultima_actualizacion", "")).lower() not in {"successful", "n/a", ""}:
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": "Lambda",
                    "Tipo de recurso": "AWS Lambda function",
                    "Recurso": _resource_identifier(row),
                    "Titulo": "Revisar ultima actualizacion Lambda",
                    "Riesgo": f"Ultima actualizacion en estado {row.get('estado_ultima_actualizacion')}",
                    "Severidad": "Medium",
                    "Version actual": runtime,
                    "Version objetivo": "Successful",
                    "Estado": "Requiere revision",
                    "Tipo hallazgo": "Estado de despliegue",
                    "Finding Type": "Inventario - Estado de despliegue",
                    "Fix disponible": "Si",
                    "Exploit disponible": "No aplica",
                    "Lambda package type": row.get("package_type", ""),
                    "Lambda last updated at": row.get("ultima_modificacion", ""),
                    "Lambda last invoked at": row.get("ultima_invocacion", ""),
                    "Lambda invocations 30d": row.get("invocaciones_30d", ""),
                    "Lambda idle days": row.get("dias_desde_ultima_invocacion", ""),
                    "Lambda usage status": row.get("estado_uso", ""),
                    "Accion recomendada": "Revisar el ultimo despliegue y confirmar que la funcion queda en Successful.",
                    "Evidencia requerida": "Estado Successful en Lambda y ejecucion de prueba correcta.",
                    "Prioridad": "Media",
                }
            )

    rds_df = _load_service_scope_rows(account_name, selected_region, "rds", "RDS")
    for _, row in rds_df.iterrows():
        engine = str(row.get("motor", "")).lower()
        version = str(row.get("version", "")).strip()
        major = version.split(".", 1)[0] if version else ""
        priority = None
        if engine in {"mysql", "mariadb"} and major in {"5", "10"}:
            priority = "Alta" if major == "5" else "Media"
        elif engine == "postgres" and major in {"9", "10", "11", "12"}:
            priority = "Alta" if major in {"9", "10", "11"} else "Media"
        if priority:
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": "RDS",
                    "Tipo de recurso": "AWS RDS instance",
                    "Recurso": _resource_identifier(row),
                    "Titulo": f"Revisar version {engine} {version}",
                    "Riesgo": f"Motor/version requiere revision: {engine} {version}",
                    "Severidad": "High" if priority == "Alta" else "Medium",
                    "Version actual": version,
                    "Version objetivo": "Version soportada por AWS y estandar interno",
                    "Estado": "Requiere revision",
                    "Tipo hallazgo": "Version de motor",
                    "Finding Type": "Inventario - Version de motor",
                    "Fix disponible": "Si",
                    "Exploit disponible": "No evaluado",
                    "Accion recomendada": "Validar fin de soporte del motor, plan de upgrade y ventana de mantenimiento.",
                    "Evidencia requerida": "Plan de upgrade aprobado, snapshot/backups y version final soportada.",
                    "Prioridad": priority,
                }
            )
        if not bool(row.get("multi_az", False)):
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": "RDS",
                    "Tipo de recurso": "AWS RDS instance",
                    "Recurso": _resource_identifier(row),
                    "Titulo": "Habilitar o justificar Multi-AZ",
                    "Riesgo": "Base de datos sin Multi-AZ",
                    "Severidad": "Medium",
                    "Version actual": version,
                    "Version objetivo": "Multi-AZ para componentes criticos",
                    "Estado": "Brecha de resiliencia",
                    "Tipo hallazgo": "Resiliencia",
                    "Finding Type": "Inventario - Resiliencia",
                    "Fix disponible": "Si",
                    "Exploit disponible": "No aplica",
                    "Accion recomendada": "Confirmar criticidad del servicio y habilitar Multi-AZ si aplica.",
                    "Evidencia requerida": "Configuracion Multi-AZ o excepcion documentada por criticidad.",
                    "Prioridad": "Media",
                }
            )

    iam_df = _load_service_scope_rows(account_name, selected_region, "iam_users", "IAM Users")
    for _, row in iam_df.iterrows():
        if row.get("mfa_enabled") is False:
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": "IAM",
                    "Tipo de recurso": "AWS IAM user",
                    "Recurso": _resource_identifier(row),
                    "Titulo": "Habilitar MFA en usuario IAM",
                    "Riesgo": "Usuario IAM sin MFA",
                    "Severidad": "High",
                    "Version actual": "MFA deshabilitado",
                    "Version objetivo": "MFA habilitado",
                    "Estado": "Brecha de acceso",
                    "Tipo hallazgo": "Control de acceso",
                    "Finding Type": "Inventario - Control de acceso",
                    "Fix disponible": "Si",
                    "Exploit disponible": "No aplica",
                    "Accion recomendada": "Habilitar MFA o retirar el usuario si no corresponde a uso interactivo.",
                    "Evidencia requerida": "MFA activo o excepcion documentada para usuario no interactivo.",
                    "Prioridad": "Alta",
                }
            )

    s3_df = _load_service_scope_rows(account_name, selected_region, "s3", "S3")
    for _, row in s3_df.iterrows():
        if row.get("region") == "unknown":
            rows.append(
                {
                    "Cuenta": row.get("cuenta", account_name),
                    "Region": row.get("region", ""),
                    "Servicio": "S3",
                    "Tipo de recurso": "AWS S3 bucket",
                    "Recurso": _resource_identifier(row),
                    "Titulo": "Completar evidencia de region S3",
                    "Riesgo": "No se pudo determinar region del bucket",
                    "Severidad": "Medium",
                    "Version actual": "Sin evidencia completa",
                    "Version objetivo": "Inventario con metadata completa",
                    "Estado": "Evidencia incompleta",
                    "Tipo hallazgo": "Evidencia incompleta",
                    "Finding Type": "Inventario - Evidencia incompleta",
                    "Fix disponible": "Si",
                    "Exploit disponible": "No aplica",
                    "Accion recomendada": "Reprocesar inventario y validar permisos de lectura de ubicacion del bucket.",
                    "Evidencia requerida": "Region detectada en cache/inventario o causa de acceso documentada.",
                    "Prioridad": "Media",
                }
            )

    return _normalize_vulnerability_dataframe(rows)


def _humanize_product_name(value):
    """Convierte una clave detectada en nombre legible."""
    text = str(value or "").strip()
    if not text:
        return "Sin producto"
    parts = [part for part in re.split(r"[_\-\s.]+", text) if part]
    if not parts:
        return "Sin producto"
    return " ".join(part.upper() if len(part) <= 3 else part.capitalize() for part in parts)


def _infer_product_from_tags(row):
    """Busca tags que normalmente identifican producto/aplicacion."""
    tags = _extract_row_tags(row)
    for key in PRODUCT_TAG_KEYS:
        value = tags.get(key)
        if value and str(value).strip():
            product_key = normalize_component_name(value)
            if product_key:
                return product_key, _humanize_product_name(value), "Tag", "Alta"
    return "", "", "", ""


def _infer_product_from_name(value):
    """Deduce producto desde nombres de recursos cuando no hay tag util."""
    if value is None:
        return "", "", "", ""

    text = str(value).strip()
    if not text:
        return "", "", "", ""

    normalized = normalize_component_name(text)
    tokens = [
        token
        for token in re.split(r"[_\-\s.]+", normalized)
        if token and not token.isdigit() and token not in PRODUCT_NAME_STOPWORDS
    ]
    tokens = [
        token
        for token in tokens
        if not re.match(r"^(i|vpc|subnet|sg|rtb|nat|eipalloc|eni)-?[a-f0-9]+$", token)
    ]
    if not tokens:
        return "", "", "", ""

    if len(tokens) >= 2 and tokens[1] not in PRODUCT_NAME_STOPWORDS:
        selected_tokens = tokens[:2]
    else:
        selected_tokens = tokens[:1]

    product_key = "_".join(selected_tokens)
    return product_key, _humanize_product_name(product_key), "Nombre", "Media"


def _infer_product_for_row(row):
    """Obtiene producto sugerido para una fila de inventario."""
    tag_key, tag_name, source, confidence = _infer_product_from_tags(row)
    if tag_key:
        return tag_key, tag_name, source, confidence

    for column in [
        "api_nombre",
        "lambda_function",
        "nombre",
        "name",
        "id",
        "resource_id",
        "arn",
        "url",
        "username",
        "key_id",
    ]:
        if column not in row.index:
            continue
        product_key, product_name, source, confidence = _infer_product_from_name(row.get(column))
        if product_key:
            return product_key, product_name, source, confidence

    return "", "", "", ""


def build_product_inventory_dataframe(account_name, selected_region):
    """Agrupa recursos en productos sugeridos sin persistir cambios."""
    rows = []
    for service_key, display_name, _ in ANALYTICS_SERVICE_LABELS:
        if service_key == "api_gateway_routes":
            continue
        data = _load_service_scope_rows(account_name, selected_region, service_key, display_name)
        if data.empty:
            continue

        for _, row in data.iterrows():
            product_key, product_name, source, confidence = _infer_product_for_row(row)
            if not product_key:
                continue
            rows.append(
                {
                    "Cuenta": account_name,
                    "Region": row.get("region", ""),
                    "Producto key": product_key,
                    "Producto": product_name,
                    "Servicio": display_name,
                    "Recurso": _resource_identifier(row),
                    "Ultimo llamado / uso": _component_last_usage(row),
                    "Origen deteccion": source,
                    "Confianza": confidence,
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "Cuenta",
                "Region",
                "Producto key",
                "Producto",
                "Servicio",
                "Recurso",
                "Ultimo llamado / uso",
                "Origen deteccion",
                "Confianza",
            ]
        )
    return pd.DataFrame(rows)


def build_product_relationships_dataframe(account_name, selected_region):
    """Detecta relaciones conocidas entre servicios cacheados."""
    rows = []
    lambda_df = _load_service_scope_rows(account_name, selected_region, "lambda", "Lambda")
    lambda_last_usage_lookup = _build_lambda_last_usage_lookup(lambda_df)
    routes_df = _load_service_scope_rows(
        account_name,
        selected_region,
        "api_gateway_routes",
        "API Gateway -> Lambda",
    )
    if not routes_df.empty:
        for _, row in routes_df.iterrows():
            product_key, product_name, source, confidence = _infer_product_for_row(row)
            if not product_key:
                continue
            lambda_target = row.get("lambda_function", row.get("lambda_arn", ""))
            rows.append(
                {
                    "Cuenta": account_name,
                    "Region": row.get("region", ""),
                    "Producto key": product_key,
                    "Producto": product_name,
                    "Relacion": "API Gateway -> Lambda",
                    "Origen": row.get("api_nombre", row.get("api_id", "")),
                    "Destino": lambda_target,
                    "Ultimo llamado / uso": lambda_last_usage_lookup.get(
                        str(lambda_target).strip(),
                        lambda_last_usage_lookup.get(str(row.get("lambda_arn", "")).strip(), ""),
                    ),
                    "Detalle": row.get("route_key", row.get("ruta", "")),
                    "Evidencia": "Integracion API Gateway",
                    "Confianza": "Alta" if confidence != "Alta" else confidence,
                    "Origen deteccion": source or "Relacion",
                }
            )

    if not lambda_df.empty:
        for _, row in lambda_df.iterrows():
            product_key, product_name, source, confidence = _infer_product_for_row(row)
            if not product_key:
                continue
            role_name = row.get("execution_role_name") or row.get("execution_role_arn")
            lambda_last_usage = _component_last_usage(row)
            if role_name:
                rows.append(
                    {
                        "Cuenta": account_name,
                        "Region": row.get("region", ""),
                        "Producto key": product_key,
                        "Producto": product_name,
                        "Relacion": "Lambda -> IAM Role",
                        "Origen": row.get("nombre", ""),
                        "Destino": role_name,
                        "Ultimo llamado / uso": lambda_last_usage,
                        "Detalle": row.get("access_actions", ""),
                        "Evidencia": "Rol de ejecucion Lambda",
                        "Confianza": confidence,
                        "Origen deteccion": source,
                    }
                )
            if row.get("vpc"):
                rows.append(
                    {
                        "Cuenta": account_name,
                        "Region": row.get("region", ""),
                        "Producto key": product_key,
                        "Producto": product_name,
                        "Relacion": "Lambda -> VPC",
                        "Origen": row.get("nombre", ""),
                        "Destino": row.get("vpc", ""),
                        "Ultimo llamado / uso": lambda_last_usage,
                        "Detalle": row.get("subnets", ""),
                        "Evidencia": "Configuracion VPC Lambda",
                        "Confianza": confidence,
                        "Origen deteccion": source,
                    }
                )

    if not rows:
        return pd.DataFrame(
            columns=[
                "Cuenta",
                "Region",
                "Producto key",
                "Producto",
                "Relacion",
                "Origen",
                "Destino",
                "Ultimo llamado / uso",
                "Detalle",
                "Evidencia",
                "Confianza",
                "Origen deteccion",
            ]
        )
    return pd.DataFrame(rows)


def build_product_summary_dataframe(product_df, relationships_df):
    """Resume productos detectados con conteos y servicios involucrados."""
    if product_df.empty and relationships_df.empty:
        return pd.DataFrame(
            columns=[
                "Producto key",
                "Producto",
                "Recursos",
                "Relaciones",
                "Servicios",
                "Confianza",
                "Origen principal",
                "Estado",
            ]
        )

    product_keys = set(product_df.get("Producto key", pd.Series(dtype=str)).dropna())
    product_keys.update(relationships_df.get("Producto key", pd.Series(dtype=str)).dropna())

    rows = []
    confidence_rank = {"Alta": 3, "Media": 2, "Baja": 1}
    for product_key in sorted(product_keys):
        resources = product_df[product_df["Producto key"] == product_key] if not product_df.empty else pd.DataFrame()
        relations = (
            relationships_df[relationships_df["Producto key"] == product_key]
            if not relationships_df.empty
            else pd.DataFrame()
        )
        product_name = ""
        if not resources.empty:
            product_name = resources.iloc[0].get("Producto", "")
        elif not relations.empty:
            product_name = relations.iloc[0].get("Producto", "")

        services = sorted(set(resources.get("Servicio", pd.Series(dtype=str)).dropna()))
        if not relations.empty:
            relation_services = set()
            for relation in relations["Relacion"].dropna():
                relation_services.update(part.strip() for part in str(relation).split("->") if part.strip())
            services = sorted(set(services) | relation_services)

        confidences = list(resources.get("Confianza", pd.Series(dtype=str)).dropna())
        confidences.extend(list(relations.get("Confianza", pd.Series(dtype=str)).dropna()))
        confidence = max(confidences, key=lambda item: confidence_rank.get(item, 0)) if confidences else "Baja"
        origins = list(resources.get("Origen deteccion", pd.Series(dtype=str)).dropna())
        origins.extend(list(relations.get("Origen deteccion", pd.Series(dtype=str)).dropna()))
        origin = sorted(set(origins))[0] if origins else "Nombre"

        rows.append(
            {
                "Producto key": product_key,
                "Producto": product_name or _humanize_product_name(product_key),
                "Recursos": len(resources),
                "Relaciones": len(relations),
                "Servicios": ", ".join(services) if services else "Sin servicios asociados",
                "Confianza": confidence,
                "Origen principal": origin,
                "Estado": "Sugerido",
            }
        )

    return pd.DataFrame(rows).sort_values(
        by=["Recursos", "Relaciones", "Producto"],
        ascending=[False, False, True],
        kind="stable",
    )


INFRA_MAP_SERVICE_STYLES = {
    "EC2": {"color": "#2563eb", "category": "Red"},
    "VPC": {"color": "#0f766e", "category": "Red"},
    "NAT/IPs salida": {"color": "#0891b2", "category": "Red"},
    "RDS": {"color": "#7c3aed", "category": "Datos"},
    "DynamoDB": {"color": "#3b82f6", "category": "Datos"},
    "SQS": {"color": "#eab308", "category": "Datos"},
    "Lambda": {"color": "#f59e0b", "category": "Serverless"},
    "API Gateway": {"color": "#ef4444", "category": "Serverless"},
    "S3": {"color": "#06b6d4", "category": "Global"},
    "IAM Users": {"color": "#64748b", "category": "Global"},
    "IAM Role": {"color": "#64748b", "category": "Global"},
    "KMS": {"color": "#475569", "category": "Global"},
    "SSM": {"color": "#475569", "category": "Global"},
    "CloudFormation": {"color": "#2563eb", "category": "Otros"},
    "CloudWatch Logs": {"color": "#334155", "category": "Otros"},
}


def _map_node_id(service_name, resource_name):
    """Crea identificador estable para nodos del mapa."""
    raw = f"{service_name}:{resource_name}"
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", raw).strip("_")
    return normalized[:90] or "node"


def _guess_map_service_from_relation(relation_name, value, side):
    """Deduce tipo de servicio para nodos creados desde relaciones."""
    relation_text = str(relation_name or "").lower()
    value_text = str(value or "").lower()
    if "api gateway" in relation_text and side == "source":
        return "API Gateway"
    if "lambda" in relation_text and ("lambda" in value_text or side == "target"):
        return "Lambda"
    if "iam role" in relation_text or ":role/" in value_text:
        return "IAM Role"
    if "vpc" in relation_text or value_text.startswith("vpc-"):
        return "VPC"
    if value_text.startswith("/aws/lambda/"):
        return "CloudWatch Logs"
    return "Otros"


def build_infra_map(product_df, relationships_df, product_key, service_filter="Todos los servicios", max_nodes=60):
    """Construye nodos y aristas para el mapa de infraestructura."""
    resources = product_df[product_df["Producto key"] == product_key] if not product_df.empty else pd.DataFrame()
    relationships = (
        relationships_df[relationships_df["Producto key"] == product_key]
        if not relationships_df.empty
        else pd.DataFrame()
    )

    if service_filter != "Todos los servicios" and not resources.empty:
        resources = resources[resources["Servicio"] == service_filter]

    nodes = {}
    edges = []

    def add_node(service_name, resource_name, region="", source="Inventario"):
        if not resource_name or str(resource_name).strip() == "":
            return ""
        service_name = service_name or "Otros"
        node_id = _map_node_id(service_name, resource_name)
        style = INFRA_MAP_SERVICE_STYLES.get(service_name, {"color": "#6b7280", "category": "Otros"})
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "service": service_name,
                "resource": str(resource_name),
                "region": str(region or ""),
                "source": source,
                "color": style["color"],
                "category": style["category"],
            }
        return node_id

    for _, row in resources.head(max_nodes).iterrows():
        add_node(row.get("Servicio", "Otros"), row.get("Recurso", ""), row.get("Region", ""), row.get("Origen deteccion", "Inventario"))

    for _, row in relationships.iterrows():
        source_service = _guess_map_service_from_relation(row.get("Relacion"), row.get("Origen"), "source")
        target_service = _guess_map_service_from_relation(row.get("Relacion"), row.get("Destino"), "target")
        source_id = add_node(source_service, row.get("Origen", ""), row.get("Region", ""), row.get("Evidencia", "Relacion"))
        target_id = add_node(target_service, row.get("Destino", ""), row.get("Region", ""), row.get("Evidencia", "Relacion"))
        if source_id and target_id:
            edges.append(
                {
                    "from": source_id,
                    "to": target_id,
                    "label": str(row.get("Relacion", "")),
                    "detail": str(row.get("Detalle", "")),
                }
            )

    lambda_nodes = [node for node in nodes.values() if node["service"] == "Lambda"]
    for node in lambda_nodes:
        log_name = f"/aws/lambda/{node['resource']}"
        log_id = add_node("CloudWatch Logs", log_name, node["region"], "Inferido")
        if log_id:
            edges.append({"from": log_id, "to": node["id"], "label": "logs for", "detail": "Convencion CloudWatch Logs"})

    if len(nodes) > max_nodes:
        keep_ids = set(list(nodes.keys())[:max_nodes])
        nodes = {node_id: node for node_id, node in nodes.items() if node_id in keep_ids}
        edges = [edge for edge in edges if edge["from"] in keep_ids and edge["to"] in keep_ids]

    return list(nodes.values()), edges


def render_infra_map_html(nodes, edges):
    """Renderiza un mapa HTML/SVG simple, sin dependencias externas."""
    if not nodes:
        return "<div class='infra-map-empty'>No hay recursos para dibujar.</div>", 360

    categories = ["Red", "Serverless", "Datos", "Global", "Otros"]
    grouped = {category: [] for category in categories}
    for node in nodes:
        grouped.setdefault(node["category"], []).append(node)

    card_w = 260
    card_h = 92
    gap_x = 56
    lane_gap = 54
    lane_header_h = 44
    margin_x = 44
    margin_y = 34
    positions = {}
    lane_blocks = []
    card_blocks = []
    y = margin_y
    width = 1180

    for category in categories:
        category_nodes = grouped.get(category, [])
        if not category_nodes:
            continue
        row_count = (len(category_nodes) + 2) // 3
        lane_h = lane_header_h + row_count * card_h + max(0, row_count - 1) * 20 + 28
        lane_blocks.append(
            f"<div class='infra-lane' style='left:{margin_x}px; top:{y}px; width:{width - margin_x * 2}px; height:{lane_h}px;'>"
            f"<div class='infra-lane-title'>{html_lib.escape(category)}</div></div>"
        )
        for idx, node in enumerate(category_nodes):
            col = idx % 3
            row = idx // 3
            x = margin_x + 32 + col * (card_w + gap_x)
            card_y = y + lane_header_h + row * (card_h + 20)
            positions[node["id"]] = (x + card_w / 2, card_y + card_h / 2)
            resource = html_lib.escape(node["resource"])
            if len(resource) > 42:
                resource = resource[:39] + "..."
            service = html_lib.escape(node["service"].upper())
            region = html_lib.escape(node["region"] or "global")
            source = html_lib.escape(node["source"])
            color = html_lib.escape(node["color"])
            card_blocks.append(
                f"<div class='infra-node' style='left:{x}px; top:{card_y}px; width:{card_w}px; height:{card_h}px; border-color:{color};'>"
                f"<div class='infra-node-header' style='background:{color};'>{service}</div>"
                f"<div class='infra-node-body'><strong title='{html_lib.escape(node['resource'])}'>{resource}</strong>"
                f"<span>{html_lib.escape(node['service'].lower())} / {region}</span>"
                f"<em>{source}</em></div></div>"
            )
        y += lane_h + lane_gap

    height = max(y + 40, 480)
    svg_lines = []
    for edge in edges:
        if edge["from"] not in positions or edge["to"] not in positions:
            continue
        x1, y1 = positions[edge["from"]]
        x2, y2 = positions[edge["to"]]
        mid_x = (x1 + x2) / 2
        label = html_lib.escape(edge["label"])
        svg_lines.append(
            f"<path d='M{x1:.1f},{y1:.1f} C{mid_x:.1f},{y1:.1f} {mid_x:.1f},{y2:.1f} {x2:.1f},{y2:.1f}' "
            f"class='infra-edge' marker-end='url(#arrow)' />"
        )
        svg_lines.append(
            f"<text x='{mid_x:.1f}' y='{((y1 + y2) / 2) - 6:.1f}' class='infra-edge-label'>{label}</text>"
        )

    html = f"""
    <style>
    .infra-map-wrap {{
        position: relative;
        width: 100%;
        height: {height}px;
        overflow: auto;
        background-color: #f8fafc;
        background-image: radial-gradient(#dbe5dd 1px, transparent 1px);
        background-size: 18px 18px;
        border: 1px solid #d8e3db;
        border-radius: 12px;
    }}
    .infra-lane {{
        position: absolute;
        border: 2px dashed #94a3b8;
        border-radius: 18px;
        background: rgba(255,255,255,0.55);
    }}
    .infra-lane-title {{
        padding: 14px 22px;
        color: #334155;
        font-size: 20px;
        font-weight: 700;
    }}
    .infra-node {{
        position: absolute;
        background: #ffffff;
        border: 3px solid #64748b;
        border-radius: 12px;
        box-shadow: 0 12px 28px rgba(15,23,42,0.08);
        overflow: hidden;
        z-index: 2;
    }}
    .infra-node-header {{
        color: #ffffff;
        font-weight: 800;
        font-size: 13px;
        padding: 9px 14px;
        letter-spacing: .02em;
    }}
    .infra-node-body {{
        padding: 12px 14px;
        color: #10291b;
        display: flex;
        flex-direction: column;
        gap: 3px;
    }}
    .infra-node-body strong {{
        font-size: 15px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .infra-node-body span, .infra-node-body em {{
        color: #81909e;
        font-size: 12px;
        font-style: normal;
    }}
    .infra-map-svg {{
        position: absolute;
        left: 0;
        top: 0;
        width: {width}px;
        height: {height}px;
        z-index: 1;
        pointer-events: none;
    }}
    .infra-edge {{
        fill: none;
        stroke: #94a3b8;
        stroke-width: 2.5;
        stroke-dasharray: 7 7;
    }}
    .infra-edge-label {{
        fill: #64748b;
        font-size: 12px;
        font-family: Arial, sans-serif;
        paint-order: stroke;
        stroke: #ffffff;
        stroke-width: 4px;
    }}
    .infra-map-empty {{
        height: 320px;
        display: grid;
        place-items: center;
        color: #64748b;
        border: 1px solid #d8e3db;
        border-radius: 12px;
        background: #f8fafc;
    }}
    </style>
    <div class='infra-map-wrap'>
        <svg class='infra-map-svg' viewBox='0 0 {width} {height}' preserveAspectRatio='xMinYMin meet'>
            <defs>
                <marker id='arrow' markerWidth='10' markerHeight='10' refX='7' refY='3' orient='auto'>
                    <path d='M0,0 L0,6 L8,3 z' fill='#94a3b8'></path>
                </marker>
            </defs>
            {''.join(svg_lines)}
        </svg>
        {''.join(lane_blocks)}
        {''.join(card_blocks)}
    </div>
    """
    return html, height


def build_code_block(lines):
    """Renderiza un bloque de texto con estilo consistente."""
    if not lines:
        return ""

    safe_lines = [str(line) for line in lines]
    line_items = "".join(f'<div class="code-line">{line}</div>' for line in safe_lines)
    return f'<div class="code-surface">{line_items}</div>'


def build_resource_summary_card(title, value, freshness):
    """Renderiza una tarjeta resumen alineada a la izquierda para infraestructura."""
    return f"""
    <div class="resource-summary-card">
        <div class="resource-summary-title">{title}</div>
        <div class="resource-summary-value">{value}</div>
        <div class="resource-summary-status">{freshness}</div>
    </div>
    """


def style_plotly_figure(fig, theme_name, chart_kind="default"):
    """Aplica una apariencia consistente a figuras Plotly."""
    if theme_name == "Claro":
        font_color = "#163222"
        legend_bg = "rgba(255,255,255,0.98)"
        legend_border = "#bfd4c6"
        paper_bg = "#ffffff"
        plot_bg = "#ffffff"
        grid_color = "#dbe7df"
        axis_line_color = "#6e8a78"
        template = "plotly_white"
    else:
        font_color = "#f3f4f6"
        legend_bg = "rgba(24,24,27,0.98)"
        legend_border = "#3f3f46"
        paper_bg = "#18181b"
        plot_bg = "#18181b"
        grid_color = "#3f3f46"
        axis_line_color = "#71717a"
        template = "plotly_dark"

    if theme_name == "Claro":
        fig.update_layout(
            template=template,
            paper_bgcolor=paper_bg,
            plot_bgcolor=plot_bg,
            font_color=font_color,
            legend_bgcolor=legend_bg,
            legend_bordercolor=legend_border,
            legend_borderwidth=1,
        )
    else:
        fig.update_layout(
            template=template,
            paper_bgcolor=paper_bg,
            plot_bgcolor=plot_bg,
            font_color=font_color,
            legend_bgcolor=legend_bg,
            legend_bordercolor=legend_border,
            legend_borderwidth=1,
        )

    legend_config = dict(
        title_text="",
        font=dict(size=15, color=font_color),
        bgcolor=legend_bg,
        bordercolor=legend_border,
        borderwidth=1,
    )

    margin = dict(l=20, r=20, t=135, b=20)
    if chart_kind == "pie":
        legend_config.update(
            orientation="v",
            yanchor="top",
            y=0.95,
            xanchor="left",
            x=1.02,
        )
        margin = dict(l=20, r=180, t=90, b=20)
    else:
        legend_config.update(
            orientation="h",
            yanchor="top",
            y=1.10,
            xanchor="left",
            x=0.02,
        )

    fig.update_layout(
        title=dict(
            x=0.02,
            y=0.97,
            xanchor="left",
            yanchor="top",
            font=dict(size=22),
        ),
        margin=margin,
        legend=legend_config,
        xaxis=dict(
            title_font=dict(color=font_color),
            tickfont=dict(color=font_color),
            gridcolor=grid_color,
            linecolor=axis_line_color,
            zerolinecolor=grid_color,
            showline=True,
        ),
        yaxis=dict(
            title_font=dict(color=font_color),
            tickfont=dict(color=font_color),
            gridcolor=grid_color,
            linecolor=axis_line_color,
            zerolinecolor=grid_color,
            showline=True,
        ),
    )
    return fig


def get_theme_palette(theme_name):
    """Retorna variables CSS para el tema seleccionado."""
    if theme_name == "Claro":
        return {
            "app_bg": "#f7faf7",
            "panel_bg": "#ffffff",
            "sidebar_bg": "#0d361e",
            "header_bg": "#f7faf7",
            "text": "#163222",
            "muted_text": "#486150",
            "border": "#cad8ce",
            "accent": "#1a4a2e",
            "accent_soft": "#d9e8de",
            "table_header": "#edf4ef",
            "button_bg": "#ffffff",
            "button_text": "#163222",
            "button_border": "#b9cbbb",
            "hover_bg": "#e6efe8",
            "sidebar_text": "#f3f7f3",
            "sidebar_muted": "#9ab3a1",
            "sidebar_border": "#225235",
            "sidebar_panel_bg": "#1d4729",
            "sidebar_button_bg": "#16b85f",
            "sidebar_button_text": "#ffffff",
            "sidebar_metric_bg": "#1a3f25",
            "sidebar_metric_border": "#2b5b39",
            "sidebar_success_bg": "#1b5a31",
        }

    return {
        "app_bg": "#09090b",
        "panel_bg": "#18181b",
        "sidebar_bg": "#111113",
        "header_bg": "#111113",
        "text": "#f3f4f6",
        "muted_text": "#a1a1aa",
        "border": "#3f3f46",
        "accent": "#3f8f5a",
        "accent_soft": "#1f2a23",
        "table_header": "#232326",
        "button_bg": "#202024",
        "button_text": "#f3f4f6",
        "button_border": "#3f3f46",
        "hover_bg": "#2a2a2f",
        "sidebar_text": "#f3f4f6",
        "sidebar_muted": "#a1a1aa",
        "sidebar_border": "#2a2a2f",
        "sidebar_panel_bg": "#202024",
        "sidebar_button_bg": "#2f2f35",
        "sidebar_button_text": "#f3f4f6",
        "sidebar_metric_bg": "#202024",
        "sidebar_metric_border": "#3f3f46",
        "sidebar_success_bg": "#1f2a23",
    }


@st.cache_resource
def init_app():
    """Inicializa la aplicacion."""
    return initialize_download_engine()


init_app()

theme_name = "Claro"
theme = get_theme_palette(theme_name)

st.markdown(
    f"""
    <style>
    .stApp {{
        background: {theme["app_bg"]};
        color: {theme["text"]};
    }}
    [data-testid="stHeader"] {{
        background: {theme["header_bg"]};
    }}
    [data-testid="stToolbar"] {{
        right: 1rem;
    }}
    [data-testid="stSidebar"] {{
        background: {theme["sidebar_bg"]};
        border-right: 1px solid {theme["sidebar_border"]};
    }}
    [data-testid="stSidebar"] section {{
        padding-top: 0;
    }}
    [data-testid="stSidebar"] .block-container {{
        padding-top: 0 !important;
        margin-top: 0 !important;
    }}
    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
        padding-top: 0 !important;
        margin-top: 0 !important;
    }}
    [data-testid="stSidebar"] [data-testid="stSidebarNav"] {{
        padding-top: 0;
    }}
    [data-testid="stSidebarCollapseButton"] {{
        top: 0.15rem;
    }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        gap: 0.55rem;
    }}
    [data-testid="stSidebar"] hr {{
        margin: 0.75rem 0;
        border-color: {theme["sidebar_border"]};
    }}
    [data-testid="stSidebar"] h1 {{
        font-size: 28px;
        margin: 0 0 0.45rem 0;
    }}
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {{
        font-size: 21px;
        margin: 0.35rem 0 0.2rem 0;
    }}
    [data-testid="stSidebar"] label {{
        margin-bottom: 0.15rem;
    }}
    [data-testid="stSidebar"] * {{
        color: {theme["sidebar_text"]};
    }}
    [data-testid="stSidebar"] small,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span {{
        color: {theme["sidebar_text"]};
    }}
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] .stCaption {{
        color: {theme["sidebar_muted"]};
    }}
    [data-testid="stSidebarCollapseButton"] svg,
    [data-testid="collapsedControl"] svg {{
        fill: {theme["sidebar_text"]};
    }}
    h1, h2, h3, h4, h5, h6, label, p, span {{
        color: {theme["text"]};
    }}
    small {{
        color: {theme["muted_text"]};
    }}
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    div[data-testid="stSelectbox"] > div > div,
    div[data-testid="stTextInput"] > div > div {{
        background: {theme["panel_bg"]};
        border-color: {theme["border"]};
        color: {theme["text"]};
    }}
    [data-testid="stSidebar"] div[data-baseweb="select"] > div,
    [data-testid="stSidebar"] div[data-baseweb="input"] > div,
    [data-testid="stSidebar"] div[data-testid="stSelectbox"] > div > div,
    [data-testid="stSidebar"] div[data-testid="stTextInput"] > div > div {{
        background: {theme["sidebar_panel_bg"]};
        border-color: {theme["sidebar_border"]};
        color: {theme["sidebar_text"]};
        min-height: 42px;
        border-radius: 10px;
    }}
    [data-testid="stSidebar"] div[role="radiogroup"] {{
        gap: 0.2rem;
    }}
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        min-height: 24px;
        padding-top: 0;
        padding-bottom: 0;
    }}
    div[data-baseweb="select"] input,
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] svg,
    div[data-baseweb="input"] input,
    div[data-baseweb="input"] span,
    div[data-baseweb="input"] svg {{
        color: {theme["text"]};
        fill: {theme["text"]};
    }}
    [data-testid="stSidebar"] div[data-baseweb="select"] input,
    [data-testid="stSidebar"] div[data-baseweb="select"] span,
    [data-testid="stSidebar"] div[data-baseweb="select"] svg,
    [data-testid="stSidebar"] div[data-baseweb="input"] input,
    [data-testid="stSidebar"] div[data-baseweb="input"] span,
    [data-testid="stSidebar"] div[data-baseweb="input"] svg {{
        color: {theme["sidebar_text"]};
        fill: {theme["sidebar_text"]};
    }}
    div[role="listbox"] {{
        background: {theme["panel_bg"]} !important;
        border: 1px solid {theme["border"]};
        color: {theme["text"]};
    }}
    div[role="option"] {{
        background: {theme["panel_bg"]} !important;
        color: {theme["text"]} !important;
    }}
    div[role="option"][aria-selected="true"] {{
        background: {theme["hover_bg"]} !important;
        color: {theme["text"]} !important;
    }}
    div[role="option"]:hover {{
        background: {theme["hover_bg"]} !important;
    }}
    div[data-testid="stAlert"] {{
        border-radius: 14px;
    }}
    div[data-testid="stMetric"] {{
        text-align: center;
        background: {theme["panel_bg"]};
        border: 1px solid {theme["border"]};
        border-radius: 18px;
        padding: 14px 8px;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
    }}
    div[data-testid="stMetric"] > div {{
        align-items: center;
        justify-content: center;
    }}
    div[data-testid="stMetricLabel"] {{
        justify-content: center;
    }}
    div[data-testid="stMetricValue"] {{
        justify-content: center;
    }}
    div[data-testid="stMetricDelta"] {{
        justify-content: center;
        color: {theme["accent"]};
    }}
    [data-testid="stSidebar"] div[data-testid="stMetric"] {{
        background: {theme["sidebar_metric_bg"]};
        border: 1px solid {theme["sidebar_metric_border"]};
        box-shadow: none;
        border-radius: 12px;
        padding: 7px 7px;
        min-height: 74px;
    }}
    [data-testid="stSidebar"] div[data-testid="stMetricLabel"],
    [data-testid="stSidebar"] div[data-testid="stMetricValue"] {{
        color: {theme["sidebar_text"]};
    }}
    [data-testid="stSidebar"] div[data-testid="stMetricLabel"] {{
        font-size: 14px;
    }}
    [data-testid="stSidebar"] div[data-testid="stMetricValue"] {{
        font-size: 28px;
        line-height: 1.05;
    }}
    [data-testid="stSidebar"] div[data-testid="stMetricDelta"] {{
        color: {theme["sidebar_text"]};
    }}
    div[data-testid="stDataFrame"] {{
        background: {theme["panel_bg"]};
        border: 1px solid {theme["border"]};
        border-radius: 18px;
        overflow: hidden;
    }}
    div[data-testid="stDataFrame"] * {{
        scrollbar-color: {theme["accent"]} {theme["table_header"]};
    }}
    div[data-testid="stDataFrame"] *::-webkit-scrollbar {{
        height: 12px;
        width: 12px;
    }}
    div[data-testid="stDataFrame"] *::-webkit-scrollbar-track {{
        background: {theme["table_header"]};
        border-radius: 999px;
    }}
    div[data-testid="stDataFrame"] *::-webkit-scrollbar-thumb {{
        background: {theme["accent"]};
        border-radius: 999px;
        border: 2px solid {theme["table_header"]};
    }}
    div[data-testid="stDataFrame"] *::-webkit-scrollbar-corner {{
        background: {theme["table_header"]};
    }}
    .resource-summary-card {{
        background: {theme["panel_bg"]};
        border: 1px solid {theme["border"]};
        border-radius: 22px;
        padding: 22px 28px;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
        text-align: left;
    }}
    .resource-summary-title {{
        color: {theme["muted_text"]};
        font-size: 15px;
        margin-bottom: 18px;
    }}
    .resource-summary-value {{
        color: {theme["text"]};
        font-size: 54px;
        font-weight: 700;
        line-height: 1.05;
        margin-bottom: 8px;
    }}
    .resource-summary-status {{
        color: {theme["accent"]};
        font-size: 18px;
        font-weight: 600;
    }}
    div[data-testid="stTabs"] button[role="tab"] {{
        color: {theme["muted_text"]};
    }}
    div[data-testid="stTabs"] button[aria-selected="true"] {{
        color: {theme["accent"]};
        border-bottom-color: {theme["accent"]};
    }}
    button[kind="secondary"],
    button[kind="primary"] {{
        border-radius: 12px;
    }}
    .stButton > button,
    [data-testid="baseButton-secondary"],
    [data-testid="baseButton-primary"] {{
        background: {theme["button_bg"]};
        color: {theme["button_text"]};
        border: 1px solid {theme["button_border"]};
    }}
    .stButton > button:hover,
    [data-testid="baseButton-secondary"]:hover,
    [data-testid="baseButton-primary"]:hover {{
        background: {theme["hover_bg"]};
        color: {theme["button_text"]};
        border-color: {theme["button_border"]};
    }}
    [data-testid="stSidebar"] .stButton > button,
    [data-testid="stSidebar"] [data-testid="baseButton-secondary"],
    [data-testid="stSidebar"] [data-testid="baseButton-primary"] {{
        background: {theme["sidebar_button_bg"]};
        color: {theme["sidebar_button_text"]};
        border: 1px solid {theme["sidebar_border"]};
        min-height: 42px;
        width: 100%;
        padding: 6px 12px;
        border-radius: 10px;
        font-size: 15px;
        font-weight: 700;
        line-height: 1.25;
    }}
    [data-testid="stSidebar"] .stButton > button:hover,
    [data-testid="stSidebar"] [data-testid="baseButton-secondary"]:hover,
    [data-testid="stSidebar"] [data-testid="baseButton-primary"]:hover {{
        background: {theme["accent"]};
        color: {theme["sidebar_button_text"]};
        border-color: {theme["accent"]};
    }}
    [data-testid="stSidebar"] div[data-testid="stAlert"] {{
        background: {theme["sidebar_success_bg"]};
        border: 1px solid {theme["sidebar_metric_border"]};
        color: {theme["sidebar_text"]};
        box-shadow: none;
        padding: 0.55rem 0.75rem;
        min-height: 44px;
    }}
    [data-testid="stSidebar"] div[data-testid="stAlert"] * {{
        color: {theme["sidebar_text"]} !important;
    }}
    .account-comparison-table table {{
        width: 100%;
        border-collapse: collapse;
        table-layout: auto;
        background: {theme["panel_bg"]};
        border: 1px solid {theme["border"]};
        border-radius: 18px;
        overflow: hidden;
    }}
    .account-comparison-table th {{
        text-align: center !important;
        padding: 14px 16px;
        min-width: 88px;
        white-space: nowrap;
        background: {theme["table_header"]};
        color: {theme["text"]};
        border-bottom: 1px solid {theme["border"]};
    }}
    .account-comparison-table td {{
        text-align: center;
        vertical-align: middle;
        padding: 14px 16px;
        min-width: 88px;
        color: {theme["text"]};
        border-bottom: 1px solid {theme["border"]};
    }}
    .account-comparison-table td:first-child,
    .account-comparison-table th:first-child {{
        text-align: left !important;
        min-width: 140px;
        position: sticky;
        left: 0;
        background: {theme["panel_bg"]};
    }}
    table.account-comparison-table tbody tr:last-child td {{
        background: {theme["panel_bg"]} !important;
        font-weight: 700;
    }}
    table.account-comparison-table tbody tr:last-child td:first-child {{
        background: {theme["panel_bg"]} !important;
        font-weight: 700;
    }}
    .account-comparison-wrapper {{
        width: 100%;
        overflow-x: auto;
        padding-bottom: 8px;
    }}
    .summary-table table {{
        width: 100%;
        border-collapse: collapse;
        table-layout: auto;
        background: {theme["panel_bg"]};
        border: 1px solid {theme["border"]};
        border-radius: 18px;
        overflow: hidden;
    }}
    .summary-table th {{
        text-align: center !important;
        padding: 14px 16px;
        white-space: nowrap;
        background: {theme["table_header"]};
        color: {theme["text"]};
        border-bottom: 1px solid {theme["border"]};
        border-right: 1px solid {theme["border"]};
    }}
    .summary-table td {{
        text-align: center !important;
        vertical-align: middle;
        padding: 14px 16px;
        color: {theme["text"]};
        border-bottom: 1px solid {theme["border"]};
        border-right: 1px solid {theme["border"]};
        white-space: nowrap;
    }}
    .summary-table td:first-child,
    .summary-table th:first-child,
    .summary-table td:nth-child(2),
    .summary-table th:nth-child(2) {{
        text-align: left !important;
    }}
    .summary-table td.nonzero-cell {{
        background: {theme["accent_soft"]};
        color: {theme["text"]};
        font-weight: 700;
        box-shadow: inset 0 0 0 1px {theme["border"]};
    }}
    .summary-table-wrapper {{
        width: 100%;
        overflow-x: auto;
        padding-bottom: 8px;
        border-radius: 18px;
    }}
    .code-surface {{
        background: {theme["panel_bg"]};
        border: 1px solid {theme["border"]};
        border-radius: 18px;
        padding: 18px 20px;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
    }}
    .code-line {{
        color: {theme["text"]};
        font-family: Consolas, "Courier New", monospace;
        font-size: 15px;
        line-height: 1.65;
        margin: 0;
    }}
    .code-line + .code-line {{
        margin-top: 4px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.title("AWS Inventory")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navegacion",
    [
        "Dashboard",
        "Infraestructura AWS",
        "Productos",
        "Mapa de Infra",
        "Tags",
        "Billing",
        "Vulnerabilidades",
        "Comparacion Regional",
    ],
)

st.sidebar.divider()

account_names = [
    account for account in ACCOUNT_DISPLAY_ORDER if account in PERFILES
] + [
    account for account in PERFILES.keys() if account not in ACCOUNT_DISPLAY_ORDER
]
account_selector_options = account_names + [ALL_ACCOUNTS_OPTION]
selected_account = st.sidebar.selectbox(
    "Cuenta AWS",
    account_selector_options,
    format_func=get_account_display_label,
)
selected_account_regions = get_region_selector_options(selected_account)

selected_region = st.sidebar.selectbox(
    "Region",
    selected_account_regions,
    format_func=get_scope_display_label,
)
selected_region_label = get_scope_display_label(selected_region)

st.sidebar.divider()
st.sidebar.subheader("Descargas")

selected_export_accounts = get_selected_account_names(selected_account)
selected_account_label = get_account_display_label(selected_account)
excel_download_name = (
    "inventario_global.xlsx"
    if selected_account == ALL_ACCOUNTS_OPTION
    else f"{selected_account}_inventario.xlsx"
)
st.session_state.setdefault("excel_download_data", None)
st.session_state.setdefault("excel_download_name", excel_download_name)

download_refresh_label = st.sidebar.selectbox(
    "Modo cache",
    list(DOWNLOAD_REFRESH_MODES.keys()),
)
download_service_label = st.sidebar.selectbox(
    "Servicio cache",
    list(DOWNLOAD_RESOURCE_OPTIONS.keys()),
)
download_refresh_mode = DOWNLOAD_REFRESH_MODES[download_refresh_label]
download_service = DOWNLOAD_RESOURCE_OPTIONS[download_service_label]
download_accounts = get_selected_account_names(selected_account)
download_regions = get_download_regions(selected_region)
download_resources = get_download_resources(download_service)

if st.sidebar.button("Descargar cache seleccion actual", use_container_width=True):
    with st.spinner("Descargando seleccion actual..."):
        result = download_scope(
            account_names=download_accounts,
            regions=download_regions,
            resource_types=download_resources,
            max_workers=4,
            refresh_mode=download_refresh_mode,
        )
        show_download_result(result)

if st.sidebar.button("Descargar cache cuenta completa", use_container_width=True):
    with st.spinner("Descargando cuenta completa..."):
        result = download_scope(
            account_names=download_accounts,
            resource_types=download_resources,
            max_workers=4,
            refresh_mode=download_refresh_mode,
        )
        show_download_result(result)

if st.sidebar.button("Descargar cache total", use_container_width=True):
    with st.spinner("Descargando cache total..."):
        if download_refresh_mode == "force" and download_resources is None:
            result = download_all_parallel(max_workers=4)
        else:
            result = download_scope(
                resource_types=download_resources,
                max_workers=4,
                refresh_mode=download_refresh_mode,
            )
        show_download_result(result)

if st.sidebar.button("Archivo .xlsx seleccion actual", use_container_width=True):
    try:
        excel_output_path = build_excel_export_path(selected_account_label)
        generated_path = export_to_excel(
            cache_manager,
            selected_export_accounts,
            PERFILES,
            str(excel_output_path),
        )
        if generated_path and excel_output_path.exists():
            st.session_state["excel_download_data"] = excel_output_path.read_bytes()
            st.session_state["excel_download_name"] = excel_download_name
            st.success(f"Excel listo para {selected_account_label}")
        else:
            st.error("No se pudo generar el archivo Excel.")
    except Exception as exc:
        st.error(f"Error generando Excel: {exc}")

if st.sidebar.button("Archivo .xlsx total", use_container_width=True):
    try:
        excel_output_path = build_excel_export_path("inventario_global")
        generated_path = export_to_excel(
            cache_manager,
            account_names,
            PERFILES,
            str(excel_output_path),
        )
        if generated_path and excel_output_path.exists():
            st.session_state["excel_download_data"] = excel_output_path.read_bytes()
            st.session_state["excel_download_name"] = "inventario_global.xlsx"
            st.success("Excel global listo para todas las cuentas")
        else:
            st.error("No se pudo generar el Excel global.")
    except Exception as exc:
        st.error(f"Error generando Excel global: {exc}")

if st.session_state.get("excel_download_data"):
    st.sidebar.download_button(
        "Bajar .xlsx",
        data=st.session_state["excel_download_data"],
        file_name=st.session_state["excel_download_name"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

if "confirm_clear_cache" not in st.session_state:
    st.session_state["confirm_clear_cache"] = False
if "clear_cache_confirmation_nonce" not in st.session_state:
    st.session_state["clear_cache_confirmation_nonce"] = 0

if not st.session_state["confirm_clear_cache"]:
    if st.sidebar.button("Limpiar Cache", use_container_width=True):
        st.session_state["confirm_clear_cache"] = True
        st.rerun()
else:
    st.sidebar.warning("Esta accion elimina todo el cache local descargado.")
    clear_cache_confirmation = st.sidebar.text_input(
        "Escribe ELIMINAR CACHE para confirmar",
        key=f"clear_cache_confirmation_{st.session_state['clear_cache_confirmation_nonce']}",
    )
    confirm_col, cancel_col = st.sidebar.columns(2)
    with confirm_col:
        if st.button(
            "Confirmar",
            disabled=clear_cache_confirmation.strip() != "ELIMINAR CACHE",
            use_container_width=True,
        ):
            cache_manager.clear()
            st.session_state["confirm_clear_cache"] = False
            st.session_state["clear_cache_confirmation_nonce"] += 1
            st.success("Cache limpiado")
            st.rerun()
    with cancel_col:
        if st.button("Cancelar", use_container_width=True):
            st.session_state["confirm_clear_cache"] = False
            st.session_state["clear_cache_confirmation_nonce"] += 1
            st.rerun()

st.sidebar.divider()
st.sidebar.subheader("Estado del Cache")
cache_status = get_cache_status()
col1, col2 = st.sidebar.columns(2)
with col1:
    st.metric("Archivos", cache_status["cache_files"])
with col2:
    st.metric("Tamano", f"{cache_status['cache_size_mb']:.1f} MB")

if cache_status["discovery_complete"]:
    st.sidebar.success("Discovery completo")
else:
    st.sidebar.warning("Discovery pendiente")

if page == "Dashboard":
    st.title("Dashboard Global")

    tab1, tab2 = st.tabs(["Cuenta Actual", "Todas las Cuentas"])

    with tab1:
        st.subheader(f"Cuenta: {selected_account_label} | Vista: {selected_region_label}")
        if selected_region == ALL_REGIONS_OPTION:
            st.caption("Resumen consolidado de todas las regiones descubiertas y cacheadas para la cuenta.")

        metrics_data = {}
        for service_key, display_name in SERVICE_LABELS:
            service_df, status, exists = load_account_service_dataframe(
                selected_account,
                service_key,
                selected_region,
            )
            count = len(service_df) if exists and isinstance(service_df, pd.DataFrame) else 0
            metrics_data[display_name] = (count, status)

        total_components = sum(count for count, _ in metrics_data.values())
        sorted_metrics = sorted(
            metrics_data.items(),
            key=lambda item: item[1][0],
            reverse=True,
        )
        dashboard_metric_items = [("Total componentes", total_components, selected_region_label)]
        dashboard_metric_items.extend(
            (display_name, count, status)
            for display_name, (count, status) in sorted_metrics
        )
        render_metric_cards(dashboard_metric_items)

        if selected_region == ALL_REGIONS_OPTION:
            if selected_account == ALL_ACCOUNTS_OPTION:
                region_summary_frames = [
                    build_account_region_summary(account)
                    for account in get_selected_account_names(selected_account)
                ]
                region_summary_df = (
                    pd.concat(region_summary_frames, ignore_index=True)
                    if region_summary_frames
                    else pd.DataFrame()
                )
            else:
                region_summary_df = build_account_region_summary(selected_account)
            if not region_summary_df.empty:
                region_summary_df = region_summary_df.sort_values(
                    ["Total recursos", "Cuenta", "Region"],
                    ascending=[False, True, True],
                )
                st.subheader("Cobertura por Region")
                display_region_summary_df = sanitize_dataframe_for_display(region_summary_df)
                st.markdown(
                    build_summary_table_html(display_region_summary_df),
                    unsafe_allow_html=True,
                )

                chart_df = display_region_summary_df[["Region", "Total recursos"]]
                fig = px.bar(
                    chart_df,
                    x="Region",
                    y="Total recursos",
                    title="Total de Recursos por Region",
                    labels={"Region": "Region", "Total recursos": "Recursos"},
                    color="Total recursos",
                )
                fig = style_plotly_figure(fig, theme_name)
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Resumen Global")

        totals = {
            "EC2": 0,
            "RDS": 0,
            "VPC": 0,
            "NAT/IPs": 0,
            "S3": 0,
            "Lambda": 0,
            "API": 0,
            "CloudFormation": 0,
            "SSM": 0,
            "KMS": 0,
            "DynamoDB": 0,
            "SQS": 0,
            "IAM": 0,
            "Total componentes": 0,
        }

        account_data = []

        for account in account_names:
            acc_data = {
                "Cuenta": account,
                "EC2": 0,
                "RDS": 0,
                "VPC": 0,
                "NAT/IPs": 0,
                "S3": 0,
                "Lambda": 0,
                "API": 0,
                "CloudFormation": 0,
                "SSM": 0,
                "KMS": 0,
                "DynamoDB": 0,
                "SQS": 0,
                "IAM": 0,
                "Total componentes": 0,
            }

            regional_services = [
                ("ec2", "EC2"),
                ("rds", "RDS"),
                ("vpc", "VPC"),
                ("vpc_outbound_ips", "NAT/IPs"),
                ("lambda", "Lambda"),
                ("api_gateway", "API"),
                ("cloudformation", "CloudFormation"),
                ("ssm", "SSM"),
                ("kms", "KMS"),
                ("dynamodb", "DynamoDB"),
                ("sqs", "SQS"),
            ]

            for region in get_prioritized_regions(account):
                for svc, key in regional_services:
                    data, _, exists = cache_manager.get(account, region, svc)
                    if exists and isinstance(data, pd.DataFrame):
                        acc_data[key] += len(data)

            global_region = get_global_region(account)
            for svc, key in [("s3", "S3"), ("iam_users", "IAM")]:
                data, _, exists = cache_manager.get(account, global_region, svc)
                if exists and isinstance(data, pd.DataFrame):
                    acc_data[key] = len(data)

            acc_data["Total componentes"] = sum(
                value for key, value in acc_data.items() if key != "Cuenta"
            )
            account_data.append(acc_data)

        for acc_data in account_data:
            for key in totals:
                totals[key] += acc_data[key]

        global_metric_items = [("Total componentes", totals["Total componentes"], "")]
        global_metric_items.extend(
            (display_name, totals[display_name], "")
            for display_name in sorted(
                [key for key in totals if key != "Total componentes"],
                key=lambda key: totals[key],
                reverse=True,
            )
        )
        render_metric_cards(global_metric_items)

        st.subheader("Comparativa por Cuenta")
        if account_data:
            df_comp = pd.DataFrame(account_data).sort_values(
                "Total componentes",
                ascending=False,
                kind="stable",
            )
            ordered_service_columns = sorted(
                [key for key in totals if key != "Total componentes"],
                key=lambda key: totals[key],
                reverse=True,
            )
            df_comp = df_comp[["Cuenta", *ordered_service_columns, "Total componentes"]]
            total_row = {"Cuenta": "Total"}
            for column in df_comp.columns:
                if column != "Cuenta":
                    total_row[column] = df_comp[column].sum()
            df_comp = pd.concat([df_comp, pd.DataFrame([total_row])], ignore_index=True)
            formatters = {}
            for column in df_comp.columns:
                if is_numeric_dtype(df_comp[column]):
                    formatters[column] = lambda value: f"{int(value)}"

            table_html = (
                '<div class="account-comparison-wrapper">'
                + df_comp.to_html(
                    index=False,
                    classes=["account-comparison-table"],
                    border=0,
                    justify="center",
                    formatters=formatters,
                )
                + "</div>"
            )
            st.markdown(table_html, unsafe_allow_html=True)

        st.subheader("Distribucion por Tipo")
        chart_data = {
            "EC2": totals["EC2"],
            "RDS": totals["RDS"],
            "VPC": totals["VPC"],
            "S3": totals["S3"],
            "Lambda": totals["Lambda"],
            "API": totals["API"],
            "CloudFormation": totals["CloudFormation"],
            "SSM": totals["SSM"],
            "KMS": totals["KMS"],
            "DynamoDB": totals["DynamoDB"],
            "SQS": totals["SQS"],
            "NAT/IPs": totals["NAT/IPs"],
            "IAM": totals["IAM"],
        }

        fig = px.bar(
            x=list(chart_data.keys()),
            y=list(chart_data.values()),
            title="Cantidad de Recursos por Tipo",
            labels={"x": "Tipo", "y": "Cantidad"},
            color=list(range(len(chart_data))),
        )
        fig = style_plotly_figure(fig, theme_name)
        st.plotly_chart(fig, use_container_width=True)

elif page == "Infraestructura AWS":
    st.title("Infraestructura AWS")

    resource_type = st.selectbox("Tipo de Recurso", list(RESOURCE_OPTIONS.keys()))
    cache_key = RESOURCE_OPTIONS[resource_type]
    data, freshness, exists = load_account_service_dataframe(selected_account, cache_key, selected_region)

    try:
        if not exists:
            st.warning(f"No hay datos de {resource_type} cacheados. Realiza una descarga primero.")
        elif data is None:
            st.warning("Los datos estan vacios (None). Intenta descargar de nuevo.")
        elif not isinstance(data, pd.DataFrame):
            st.error(f"Error: Tipo de dato incorrecto. Se esperaba DataFrame, se obtuvo {type(data)}")
        elif len(data) == 0:
            st.warning(f"La busqueda no retorno resultados para {resource_type}.")
        else:
            scope_text = f"{selected_account_label} | {selected_region_label}"
            st.markdown(
                build_resource_summary_card(resource_type, len(data), f"{freshness} | {scope_text}"),
                unsafe_allow_html=True,
            )

            st.subheader("Datos")
            display_data = sanitize_dataframe_for_display(data)
            display_data = ensure_monitoring_alert_columns(display_data)
            if cache_key == "lambda":
                display_data = ensure_lambda_usage_columns(display_data)
            if cache_key == "iam_users":
                display_data = ensure_iam_access_columns(display_data)
            if cache_key == "dynamodb":
                display_data = add_dynamodb_readable_size(display_data)
            if "region" in display_data.columns:
                display_data["region"] = display_data["region"].map(get_region_display_label)
            if cache_key == "lambda":
                display_data = order_lambda_columns(display_data)

            if cache_key == "s3":
                s3_preferred_columns = [
                    "nombre",
                    "region",
                    "creacion",
                    "acceso_publico",
                    "estado_gobernanza",
                    "bloqueo_publico",
                    "policy_publica",
                    "acl_publica",
                    "cifrado_default",
                    "cifrado_algoritmo",
                    "versionado",
                    "logging_acceso",
                    "object_ownership",
                    "tags_count",
                    "tags",
                    "bloqueo_publico_detalle",
                    "acl_publica_detalle",
                ]
                ordered_s3_columns = [
                    column for column in s3_preferred_columns if column in display_data.columns
                ] + [
                    column for column in display_data.columns if column not in s3_preferred_columns
                ]
                display_data = display_data[ordered_s3_columns]

                if "acceso_publico" in display_data.columns:
                    public_count = int((display_data["acceso_publico"] == "Si").sum())
                    unknown_count = int((display_data["acceso_publico"] == "No disponible").sum())
                    gap_count = (
                        int((display_data["estado_gobernanza"] != "OK").sum())
                        if "estado_gobernanza" in display_data.columns
                        else 0
                    )
                    cols = st.columns(3)
                    cols[0].metric("Buckets publicos", public_count)
                    cols[1].metric("Validacion pendiente", unknown_count)
                    cols[2].metric("Brechas gobernanza", gap_count)

            if cache_key == "lambda":
                usage_df = display_data.copy()
                idle_days = pd.to_numeric(
                    usage_df.get("dias_desde_ultima_invocacion", pd.Series(dtype="float64")),
                    errors="coerce",
                )
                invocations_30d = pd.to_numeric(
                    usage_df.get("invocaciones_30d", pd.Series(dtype="float64")),
                    errors="coerce",
                ).fillna(0)
                no_invocations = usage_df["estado_uso"].astype(str).str.contains(
                    "Sin invocaciones", case=False, na=False
                )
                inactive_90d = no_invocations | (idle_days >= 90)
                active_30d = invocations_30d > 0
                usage_cols = st.columns(3)
                usage_cols[0].metric("Invocadas ultimos 30 dias", int(active_30d.sum()))
                usage_cols[1].metric("Sin uso >=90 dias", int(inactive_90d.sum()))
                usage_cols[2].metric("Sin invocaciones en ventana", int(no_invocations.sum()))
                st.caption(
                    "Uso Lambda estimado con metrica CloudWatch Invocations; la ventana maxima revisada es 455 dias."
                )
                if (usage_df["estado_uso"].astype(str) == "Pendiente de descarga").all():
                    st.info(
                        "El cache Lambda actual no trae datos de invocacion. "
                        "Descarga/actualiza el cache de Lambda para poblar estas columnas."
                    )

            if cache_key == "vpc_outbound_ips":
                ip_display_df = display_data.copy()
                for column in [
                    "state",
                    "type",
                    "name",
                    "allocation_id",
                    "instance_id",
                    "network_interface_id",
                    "public_ip",
                    "private_ip",
                    "vpc_id",
                    "subnet_id",
                    "region",
                ]:
                    if column not in ip_display_df.columns:
                        ip_display_df[column] = ""
                ip_display_df["Estado"] = ip_display_df["state"].map(
                    {
                        "associated": "Asociada",
                        "available": "Disponible",
                        "pending": "Pendiente",
                        "failed": "Fallida",
                        "deleted": "Eliminada",
                        "deleting": "Eliminando",
                        "detached": "Sin asociar",
                        "attached": "Asociada",
                    }
                ).fillna(ip_display_df["state"])
                ip_display_df["Tipo"] = ip_display_df["type"]
                ip_display_df["Nombre"] = ip_display_df["name"]
                ip_display_df["ID Asignacion"] = ip_display_df["allocation_id"]
                ip_display_df["ID Instancia"] = ip_display_df["instance_id"]
                ip_display_df["ID Interfaz (ENI)"] = ip_display_df["network_interface_id"]
                ip_display_df["IP Publica"] = ip_display_df["public_ip"]
                ip_display_df["IP Privada"] = ip_display_df["private_ip"]
                ip_display_df["VPC"] = ip_display_df["vpc_id"]
                ip_display_df["Subnet"] = ip_display_df["subnet_id"]
                ip_display_df["Region"] = ip_display_df["region"]
                preferred_ip_columns = [
                    "Estado",
                    "Tipo",
                    "Nombre",
                    "ID Asignacion",
                    "ID Instancia",
                    "ID Interfaz (ENI)",
                    "IP Publica",
                    "IP Privada",
                    "VPC",
                    "Subnet",
                    "Region",
                ]
                st.dataframe(
                    ip_display_df[preferred_ip_columns],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                styled_display_data = (
                    display_data.style
                    .set_properties(
                        **{
                            "background-color": theme["panel_bg"],
                            "color": theme["text"],
                            "border-color": theme["border"],
                        }
                    )
                    .set_table_styles(
                        [
                            {
                                "selector": "th",
                                "props": [
                                    ("background-color", theme["table_header"]),
                                    ("color", theme["text"]),
                                    ("border-color", theme["border"]),
                                ],
                            },
                            {
                                "selector": "td",
                                "props": [
                                    ("border-color", theme["border"]),
                                ],
                            },
                        ]
                    )
                )
                if cache_key == "dynamodb" and "items" in display_data.columns:
                    styled_display_data = styled_display_data.format({"items": format_integer_thousands_es})
                st.dataframe(styled_display_data, use_container_width=True)

            if selected_region == ALL_REGIONS_OPTION and "region" in display_data.columns:
                st.subheader("Distribucion por Region")
                region_counts = display_data["region"].value_counts().reset_index()
                region_counts.columns = ["Region", "Cantidad"]
                fig = px.bar(
                    region_counts,
                    x="Region",
                    y="Cantidad",
                    title=f"{resource_type} por Region",
                    labels={"Cantidad": "Cantidad", "Region": "Region"},
                    color="Cantidad",
                )
                fig = style_plotly_figure(fig, theme_name)
                st.plotly_chart(fig, use_container_width=True)

            if cache_key == "ec2" and "estado" in display_data.columns:
                st.subheader("Estado de Instancias")
                counts = display_data["estado"].value_counts()
                fig = px.pie(values=counts.values, names=counts.index, title="Estado EC2")
                fig = style_plotly_figure(fig, theme_name, chart_kind="pie")
                st.plotly_chart(fig, use_container_width=True)

            elif cache_key == "rds" and "motor" in display_data.columns:
                st.subheader("Motores de Base de Datos")
                motor_counts = display_data["motor"].value_counts()
                fig = px.bar(
                    x=motor_counts.index,
                    y=motor_counts.values,
                    title="Motores RDS",
                    labels={"x": "Motor", "y": "Cantidad"},
                )
                fig = style_plotly_figure(fig, theme_name, chart_kind="pie")
                st.plotly_chart(fig, use_container_width=True)

            elif cache_key == "iam_users" and "mfa_enabled" in display_data.columns:
                st.subheader("MFA Status")
                mfa_count = display_data["mfa_enabled"].value_counts()
                mfa_labels = [
                    "MFA Habilitado" if bool(value) else "MFA Deshabilitado"
                    for value in mfa_count.index
                ]
                fig = px.pie(values=mfa_count.values, names=mfa_labels, title="MFA Status")
                fig = style_plotly_figure(fig, theme_name, chart_kind="pie")
                st.plotly_chart(fig, use_container_width=True)

            elif cache_key == "s3" and "estado_gobernanza" in display_data.columns:
                st.subheader("Gobernanza S3")
                governance_count = display_data["estado_gobernanza"].value_counts()
                fig = px.pie(
                    values=governance_count.values,
                    names=governance_count.index,
                    title="Estado de gobernanza S3",
                )
                fig = style_plotly_figure(fig, theme_name, chart_kind="pie")
                st.plotly_chart(fig, use_container_width=True)

            elif cache_key == "dynamodb" and "billing_mode" in display_data.columns:
                st.subheader("Modo de Facturacion")
                billing_count = display_data["billing_mode"].value_counts()
                fig = px.pie(
                    values=billing_count.values,
                    names=billing_count.index,
                    title="Modo de Facturacion DynamoDB",
                )
                fig = style_plotly_figure(fig, theme_name)
                st.plotly_chart(fig, use_container_width=True)

            elif cache_key == "vpc_outbound_ips":
                if "public_ip" in display_data.columns:
                    ips_utiles = display_data[
                        display_data["public_ip"].astype(str).str.match(r"^\d+\.\d+\.\d+\.\d+$", na=False)
                    ]["public_ip"].dropna().unique()
                    if len(ips_utiles) > 0:
                        st.subheader("IPs publicas unicas de salida")
                        st.caption("Estas son las IPs que debes entregar para whitelisting externo")
                        st.markdown(
                            build_code_block(sorted(ips_utiles)),
                            unsafe_allow_html=True,
                        )

                if "type" in display_data.columns:
                    st.subheader("Distribucion por Tipo")
                    type_count = display_data["type"].value_counts()
                    fig = px.pie(
                        values=type_count.values,
                        names=type_count.index,
                        title="NAT Gateway vs Elastic IP vs Internet Gateway",
                    )
                    fig = style_plotly_figure(fig, theme_name)
                    st.plotly_chart(fig, use_container_width=True)

            elif cache_key == "api_gateway_routes":
                if "lambda_function" in display_data.columns:
                    lambda_counts = (
                        display_data["lambda_function"]
                        .fillna("Sin Lambda")
                        .replace("", "Sin Lambda")
                        .value_counts()
                        .head(15)
                    )
                    st.subheader("Top Lambdas conectadas")
                    fig = px.bar(
                        x=lambda_counts.index,
                        y=lambda_counts.values,
                        title="Rutas por Lambda",
                        labels={"x": "Lambda", "y": "Cantidad de rutas"},
                    )
                    fig = style_plotly_figure(fig, theme_name)
                    st.plotly_chart(fig, use_container_width=True)

                if "api_nombre" in display_data.columns:
                    api_counts = display_data["api_nombre"].fillna("Sin API").value_counts().head(15)
                    st.subheader("Top APIs con integraciones")
                    fig = px.bar(
                        x=api_counts.index,
                        y=api_counts.values,
                        title="Integraciones por API",
                        labels={"x": "API", "y": "Cantidad de integraciones"},
                    )
                    fig = style_plotly_figure(fig, theme_name)
                    st.plotly_chart(fig, use_container_width=True)

    except Exception as exc:
        st.error(f"Error procesando datos: {str(exc)}")

elif page == "Productos":
    st.title("Productos")
    st.caption(f"Cuenta: {selected_account_label} | Vista: {selected_region_label}")
    st.caption(
        "Agrupacion sugerida de recursos basada en tags, patrones de nombre y relaciones detectadas."
    )

    product_df = build_product_inventory_dataframe(selected_account, selected_region)
    relationships_df = build_product_relationships_dataframe(selected_account, selected_region)
    summary_df = build_product_summary_dataframe(product_df, relationships_df)

    total_products = len(summary_df)
    total_resources = int(summary_df["Recursos"].sum()) if not summary_df.empty else 0
    total_relationships = int(summary_df["Relaciones"].sum()) if not summary_df.empty else 0
    high_confidence = int((summary_df["Confianza"] == "Alta").sum()) if not summary_df.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Productos sugeridos", total_products)
    with col2:
        st.metric("Recursos agrupados", total_resources)
    with col3:
        st.metric("Relaciones", total_relationships)
    with col4:
        st.metric("Confianza alta", high_confidence)

    if summary_df.empty:
        st.warning("No hay suficiente informacion cacheada para sugerir productos en este alcance.")
    else:
        st.subheader("Auto-deteccion de productos")
        display_summary_df = sanitize_dataframe_for_display(summary_df.drop(columns=["Producto key"], errors="ignore"))
        st.dataframe(display_summary_df, use_container_width=True, hide_index=True)

        service_rows = []
        for _, summary_row in summary_df.iterrows():
            product_key = summary_row["Producto key"]
            product_resources = product_df[product_df["Producto key"] == product_key]
            if product_resources.empty:
                continue
            for service_name, amount in product_resources["Servicio"].value_counts().items():
                service_rows.append(
                    {
                        "Producto": summary_row["Producto"],
                        "Servicio": service_name,
                        "Cantidad": int(amount),
                    }
                )

        service_chart_df = pd.DataFrame(service_rows)
        if not service_chart_df.empty:
            fig = px.bar(
                service_chart_df,
                x="Producto",
                y="Cantidad",
                color="Servicio",
                barmode="stack",
                title="Recursos por producto y servicio",
            )
            fig = style_plotly_figure(fig, theme_name)
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Detalle por producto")
        for _, summary_row in summary_df.iterrows():
            product_key = summary_row["Producto key"]
            product_resources = product_df[product_df["Producto key"] == product_key]
            product_relationships = relationships_df[
                relationships_df["Producto key"] == product_key
            ] if not relationships_df.empty else pd.DataFrame()
            expander_title = (
                f"{summary_row['Producto']} | "
                f"{summary_row['Recursos']} recursos | "
                f"{summary_row['Relaciones']} relaciones | "
                f"{summary_row['Confianza']}"
            )

            with st.expander(expander_title, expanded=False):
                metric_col1, metric_col2, metric_col3 = st.columns(3)
                with metric_col1:
                    st.metric("Recursos", int(summary_row["Recursos"]))
                with metric_col2:
                    st.metric("Relaciones", int(summary_row["Relaciones"]))
                with metric_col3:
                    st.metric("Confianza", summary_row["Confianza"])

                st.caption(f"Servicios detectados: {summary_row['Servicios']}")

                if not product_resources.empty:
                    st.markdown("**Recursos asociados**")
                    resources_display_df = sanitize_dataframe_for_display(
                        product_resources.drop(columns=["Producto key"], errors="ignore")
                    )
                    if "Region" in resources_display_df.columns:
                        resources_display_df["Region"] = resources_display_df["Region"].map(
                            get_region_display_label
                        )
                    st.dataframe(resources_display_df, use_container_width=True, hide_index=True)

                if not product_relationships.empty:
                    st.markdown("**Relaciones detectadas**")
                    relationship_display_df = sanitize_dataframe_for_display(
                        product_relationships.drop(columns=["Producto key"], errors="ignore")
                    )
                    if "Region" in relationship_display_df.columns:
                        relationship_display_df["Region"] = relationship_display_df["Region"].map(
                            get_region_display_label
                        )
                    st.dataframe(relationship_display_df, use_container_width=True, hide_index=True)

elif page == "Mapa de Infra":
    st.title("Mapa de Infraestructura")
    st.caption(f"Cuenta: {selected_account_label} | Vista: {selected_region_label}")
    st.caption("MVP de red por producto basado en recursos y relaciones detectadas desde cache.")

    product_df = build_product_inventory_dataframe(selected_account, selected_region)
    relationships_df = build_product_relationships_dataframe(selected_account, selected_region)
    summary_df = build_product_summary_dataframe(product_df, relationships_df)

    if summary_df.empty:
        st.warning("No hay productos detectados para construir el mapa. Descarga cache o revisa el modulo Productos.")
    else:
        map_col1, map_col2, map_col3 = st.columns([2, 2, 1])
        product_options = summary_df["Producto key"].tolist()
        product_labels = dict(zip(summary_df["Producto key"], summary_df["Producto"]))
        with map_col1:
            selected_product_key = st.selectbox(
                "Producto",
                product_options,
                format_func=lambda key: product_labels.get(key, key),
            )

        selected_product_resources = product_df[
            product_df["Producto key"] == selected_product_key
        ] if not product_df.empty else pd.DataFrame()
        service_options = ["Todos los servicios"]
        if not selected_product_resources.empty:
            service_options.extend(sorted(selected_product_resources["Servicio"].dropna().unique()))

        with map_col2:
            selected_map_service = st.selectbox("Servicio", service_options)
        with map_col3:
            max_map_nodes = st.number_input("Max nodos", min_value=10, max_value=120, value=60, step=10)

        nodes, edges = build_infra_map(
            product_df,
            relationships_df,
            selected_product_key,
            service_filter=selected_map_service,
            max_nodes=int(max_map_nodes),
        )
        service_count = len({node["service"] for node in nodes})
        product_name = product_labels.get(selected_product_key, selected_product_key)

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        with metric_col1:
            st.metric("Producto", product_name)
        with metric_col2:
            st.metric("Recursos", len(nodes))
        with metric_col3:
            st.metric("Relaciones", len(edges))
        with metric_col4:
            st.metric("Servicios", service_count)

        map_html, map_height = render_infra_map_html(nodes, edges)
        components.html(map_html, height=min(max(map_height + 20, 520), 1400), scrolling=True)

        with st.expander("Datos del mapa", expanded=False):
            tab_nodes, tab_edges = st.tabs(["Nodos", "Relaciones"])
            with tab_nodes:
                nodes_df = pd.DataFrame(nodes)
                if not nodes_df.empty:
                    st.dataframe(
                        sanitize_dataframe_for_display(nodes_df.drop(columns=["id"], errors="ignore")),
                        use_container_width=True,
                        hide_index=True,
                    )
            with tab_edges:
                edges_df = pd.DataFrame(edges)
                if not edges_df.empty:
                    st.dataframe(
                        sanitize_dataframe_for_display(edges_df),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No se detectaron relaciones para este producto/filtro.")

elif page == "Tags":
    st.title("Tags")
    st.caption(f"Cuenta: {selected_account_label} | Vista: {selected_region_label}")
    st.caption("Tags obligatorios evaluados: " + ", ".join(MANDATORY_TAGS))

    tags_df = build_tag_compliance_dataframe(selected_account, selected_region)
    if tags_df.empty:
        st.warning("No hay recursos cacheados para analizar tags en este alcance.")
    else:
        total_resources = len(tags_df)
        compliant = int(tags_df["Cumple tags"].sum())
        missing = total_resources - compliant
        evidence_missing = int((tags_df["Evidencia disponible"] == "No").sum())

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Recursos analizados", total_resources)
        with col2:
            st.metric("Cumplen tags", compliant)
        with col3:
            st.metric("Con brecha", missing)
        with col4:
            st.metric("Sin evidencia en cache", evidence_missing)

        summary_df = (
            tags_df.groupby(["Servicio", "Estado tags"], dropna=False)
            .size()
            .reset_index(name="Cantidad")
        )
        fig = px.bar(
            summary_df,
            x="Servicio",
            y="Cantidad",
            color="Estado tags",
            barmode="stack",
            title="Cumplimiento de tags por servicio",
        )
        fig = style_plotly_figure(fig, theme_name)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Detalle de tags")
        display_df = sanitize_dataframe_for_display(tags_df)
        display_df["Region"] = display_df["Region"].map(get_region_display_label)
        preferred_tag_columns = [
            "Cuenta",
            "Region",
            "Servicio",
            "Recurso",
            "Estado tags",
            "Tags obligatorios presentes",
            "Tag Name",
            "Tag Environment",
            "Tag Owner",
            "Tag CostCenter",
            "Tag Application",
            "Tags presentes",
            "Tags faltantes",
            "Evidencia disponible",
        ]
        display_df = display_df[
            [column for column in preferred_tag_columns if column in display_df.columns]
            + [column for column in display_df.columns if column not in preferred_tag_columns and column != "Cumple tags"]
        ]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

elif page == "Billing":
    st.title("Billing")
    st.caption(f"Cuenta: {selected_account_label} | Vista: {selected_region_label}")

    recommendations_df = build_billing_recommendations_dataframe(selected_account, selected_region)
    high_count = int((recommendations_df["Prioridad"] == "Alta").sum()) if not recommendations_df.empty else 0
    medium_count = int((recommendations_df["Prioridad"] == "Media").sum()) if not recommendations_df.empty else 0
    low_count = int((recommendations_df["Prioridad"] == "Baja").sum()) if not recommendations_df.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Hallazgos FinOps", len(recommendations_df))
    with col2:
        st.metric("Alta prioridad", high_count)
    with col3:
        st.metric("Media prioridad", medium_count)
    with col4:
        st.metric("Baja prioridad", low_count)

    st.subheader("Cost Explorer")
    st.caption("Consulta los ultimos meses por servicio y region. Requiere permisos ce:GetCostAndUsage.")
    cost_state_key = f"cost_explorer_{selected_account}"
    if st.button("Consultar Cost Explorer", use_container_width=False):
        try:
            with st.spinner("Consultando Cost Explorer..."):
                cost_df = fetch_cost_explorer_dataframe(selected_account)
            if cost_df.empty:
                st.info("Cost Explorer no retorno costos para la cuenta seleccionada.")
            else:
                st.session_state[cost_state_key] = cost_df
                st.success("Costos actualizados desde Cost Explorer.")
        except Exception as exc:
            st.warning(f"No se pudo consultar Cost Explorer: {exc}")

    cached_cost_df = st.session_state.get(cost_state_key, pd.DataFrame())
    scoped_cost_df = filter_costs_by_selected_scope(cached_cost_df, selected_region)
    if cached_cost_df.empty:
        st.info("Consulta Cost Explorer para ver KPIs, graficos y costo por producto.")
    else:
        metrics = build_cost_dashboard_metrics(scoped_cost_df)
        month_label = metrics["current_month"] or "Sin mes"
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        with metric_col1:
            st.metric(f"Total mes actual ({month_label})", f"${metrics['current_total']:,.2f}")
        with metric_col2:
            st.metric("Variacion vs. mes anterior", f"{metrics['variation_pct']:.1f}%")
        with metric_col3:
            st.metric("Servicios activos", metrics["active_services"])

        service_cost_df = build_cost_by_service_dataframe(scoped_cost_df)
        if not service_cost_df.empty:
            st.subheader("Costo por servicio")
            chart_df = service_cost_df.head(11).sort_values("Costo USD", ascending=True).copy()
            chart_df["% del Total etiqueta"] = chart_df["% del Total"].apply(lambda value: f"{value:.1f}%")
            fig = px.bar(
                chart_df,
                x="Costo USD",
                y="Servicio",
                orientation="h",
                title="Top 11 servicios por costo mensual",
                color="Costo USD",
                text="% del Total etiqueta",
            )
            fig = style_plotly_figure(fig, theme_name)
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(xaxis_range=[0, chart_df["Costo USD"].max() * 1.16])
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                sanitize_dataframe_for_display(service_cost_df),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Costo USD": st.column_config.NumberColumn("Costo USD", format="$%.2f"),
                    "% del Total": st.column_config.NumberColumn("% del Total", format="%.1f%%"),
                },
            )

        current_cost_df = get_current_month_costs(scoped_cost_df)
        if not current_cost_df.empty:
            region_cost_df = (
                current_cost_df.groupby("Region", as_index=False)["Costo USD"]
                .sum()
                .sort_values("Costo USD", ascending=False)
            )
            st.subheader("Costo por region")
            fig = px.bar(
                region_cost_df,
                x="Region",
                y="Costo USD",
                title="Distribucion mensual por region",
                color="Costo USD",
            )
            fig = style_plotly_figure(fig, theme_name)
            st.plotly_chart(fig, use_container_width=True)

        product_cost_df = build_estimated_product_cost_dataframe(
            selected_account,
            selected_region,
            cached_cost_df,
        )
        if not product_cost_df.empty:
            st.subheader("Costo por producto")
            st.caption(
                "Estimacion basada en los productos detectados y distribucion proporcional de costos por servicio. "
                "Para precision contable, conviene habilitar cost allocation tags por producto."
            )
            st.dataframe(
                sanitize_dataframe_for_display(product_cost_df),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Costo Mensual USD": st.column_config.NumberColumn("Costo Mensual", format="$%.2f"),
                    "% del Total": st.column_config.NumberColumn("% del Total", format="%.1f%%"),
                },
            )

    st.subheader("Oportunidades desde inventario")
    if recommendations_df.empty:
        st.success("No se detectaron oportunidades FinOps con la informacion cacheada actual.")
    else:
        st.dataframe(
            sanitize_dataframe_for_display(recommendations_df),
            use_container_width=True,
            hide_index=True,
        )
        by_service = recommendations_df.groupby(["Servicio", "Prioridad"]).size().reset_index(name="Cantidad")
        fig = px.bar(
            by_service,
            x="Servicio",
            y="Cantidad",
            color="Prioridad",
            barmode="stack",
            title="Hallazgos FinOps por servicio",
        )
        fig = style_plotly_figure(fig, theme_name)
        st.plotly_chart(fig, use_container_width=True)

elif page == "Vulnerabilidades":
    st.title("Vulnerabilidades")
    st.caption(f"Cuenta: {selected_account_label} | Vista: {selected_region_label}")

    vulnerability_df = build_vulnerability_dataframe(selected_account, selected_region)
    high_count = int((vulnerability_df["Prioridad"] == "Alta").sum()) if not vulnerability_df.empty else 0
    medium_count = int((vulnerability_df["Prioridad"] == "Media").sum()) if not vulnerability_df.empty else 0
    by_service_count = vulnerability_df["Servicio"].nunique() if not vulnerability_df.empty else 0
    unique_resources_count = vulnerability_df["Recurso"].nunique() if not vulnerability_df.empty else 0
    no_owner_count = int((vulnerability_df["Responsable sugerido"].astype(str).str.strip() == "").sum()) if not vulnerability_df.empty else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Hallazgos", len(vulnerability_df))
    with col2:
        st.metric("Recursos unicos", unique_resources_count)
    with col3:
        st.metric("Alta prioridad", high_count)
    with col4:
        st.metric("Media prioridad", medium_count)
    with col5:
        st.metric("Servicios afectados", by_service_count)

    if vulnerability_df.empty:
        st.success("No se detectaron hallazgos con la informacion cacheada actual.")
    else:
        display_df = sanitize_dataframe_for_display(vulnerability_df)
        display_df["Region"] = display_df["Region"].map(get_region_display_label)

        tab_summary, tab_product, tab_technical, tab_export = st.tabs(
            ["Resumen", "Por producto", "Detalle tecnico", "Export"]
        )

        with tab_summary:
            summary_df = vulnerability_df.groupby(["Servicio", "Prioridad"]).size().reset_index(name="Cantidad")
            fig = px.bar(
                summary_df,
                x="Servicio",
                y="Cantidad",
                color="Prioridad",
                barmode="stack",
                title="Hallazgos por servicio",
            )
            fig = style_plotly_figure(fig, theme_name)
            st.plotly_chart(fig, use_container_width=True)

            owner_summary_df = (
                vulnerability_df.groupby(["Responsable sugerido", "Prioridad interna"], dropna=False)
                .size()
                .reset_index(name="Cantidad")
                .sort_values("Cantidad", ascending=False)
            )
            st.dataframe(
                sanitize_dataframe_for_display(owner_summary_df),
                use_container_width=True,
                hide_index=True,
            )

        with tab_product:
            st.subheader("Vulnerabilidades por producto")
            product_summary_df = (
                vulnerability_df.groupby(["Producto", "Responsable sugerido", "Prioridad interna"], dropna=False)
                .agg(
                    Hallazgos=("Recurso", "size"),
                    Recursos_unicos=("Recurso", "nunique"),
                )
                .reset_index()
                .sort_values(["Hallazgos", "Recursos_unicos"], ascending=False)
            )
            st.dataframe(
                sanitize_dataframe_for_display(product_summary_df),
                use_container_width=True,
                hide_index=True,
            )

            product_totals_df = (
                vulnerability_df.groupby("Producto", dropna=False)
                .agg(
                    Hallazgos=("Recurso", "size"),
                    Recursos_unicos=("Recurso", "nunique"),
                )
                .reset_index()
                .sort_values("Hallazgos", ascending=False)
                .head(20)
            )
            if not product_totals_df.empty:
                fig = px.bar(
                    product_totals_df.sort_values("Hallazgos", ascending=True),
                    x="Hallazgos",
                    y="Producto",
                    orientation="h",
                    title="Top productos por hallazgos",
                    color="Hallazgos",
                )
                fig = style_plotly_figure(fig, theme_name)
                st.plotly_chart(fig, use_container_width=True)

            product_export = BytesIO()
            product_summary_df.to_excel(product_export, index=False, sheet_name="Por_producto")
            st.download_button(
                "Descargar resumen por producto",
                data=product_export.getvalue(),
                file_name="vulnerabilidades_por_producto.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=False,
            )

            product_options = product_totals_df["Producto"].astype(str).tolist()
            if product_options:
                selected_product = st.selectbox("Producto", product_options)
                selected_product_df = display_df[display_df["Producto"].astype(str) == selected_product]
                product_columns = [
                    column for column in VULNERABILITY_BACKLOG_COLUMNS if column in selected_product_df.columns
                ]
                st.dataframe(
                    selected_product_df[product_columns],
                    use_container_width=True,
                    hide_index=True,
                )

        with tab_technical:
            st.subheader("Detalle tecnico y trazabilidad")
            technical_display_df = prepare_vulnerability_technical_display(display_df)
            lambda_usage_columns = [
                "Lambda last invoked at",
                "Lambda invocations 30d",
                "Lambda idle days",
                "Lambda usage status",
            ]
            if all(column in display_df.columns for column in lambda_usage_columns):
                lambda_findings_df = display_df[display_df["Servicio"].astype(str) == "Lambda"]
                if not lambda_findings_df.empty:
                    lambda_findings_unique_df = lambda_findings_df.drop_duplicates(
                        subset=["Cuenta", "Region", "Recurso"],
                        keep="first",
                    )
                    lambda_idle_days = pd.to_numeric(lambda_findings_unique_df["Lambda idle days"], errors="coerce")
                    lambda_invocations_30d = pd.to_numeric(
                        lambda_findings_unique_df["Lambda invocations 30d"],
                        errors="coerce",
                    ).fillna(0)
                    lambda_no_invocations = lambda_findings_unique_df["Lambda usage status"].astype(str).str.contains(
                        "Sin invocaciones",
                        case=False,
                        na=False,
                    )
                    lambda_usage_cols = st.columns(3)
                    lambda_usage_cols[0].metric(
                        "Lambdas con hallazgo invocadas 30d",
                        int((lambda_invocations_30d > 0).sum()),
                    )
                    lambda_usage_cols[1].metric(
                        "Lambdas con hallazgo sin uso >=90 dias",
                        int((lambda_no_invocations | (lambda_idle_days >= 90)).sum()),
                    )
                    lambda_usage_cols[2].metric(
                        "Lambdas con hallazgo sin invocaciones",
                        int(lambda_no_invocations.sum()),
                    )
                    st.caption(
                        "Este resumen considera solo recursos Lambda unicos con hallazgos. "
                        "Infraestructura AWS considera todas las Lambdas inventariadas."
                    )
                    if (
                        lambda_findings_unique_df["Lambda usage status"].astype(str).str.strip().eq("").all()
                    ):
                        st.info(
                            "Los hallazgos Lambda vienen de un cache anterior sin datos de invocacion. "
                            "Actualiza el cache Lambda para completar la trazabilidad de uso."
                        )
            if "Clasificacion uso Lambda" in technical_display_df.columns:
                available_classifications = [
                    classification
                    for classification in LAMBDA_USAGE_CLASSIFICATION_ORDER
                    if classification in set(technical_display_df["Clasificacion uso Lambda"].astype(str))
                ]
                remaining_classifications = sorted(
                    set(technical_display_df["Clasificacion uso Lambda"].astype(str))
                    - set(available_classifications)
                    - {""}
                )
                classification_options = available_classifications + remaining_classifications
                if classification_options:
                    selected_classifications = st.multiselect(
                        "Clasificacion uso Lambda",
                        classification_options,
                        default=classification_options,
                    )
                    lambda_classification_df = technical_display_df[
                        technical_display_df["Clasificacion uso Lambda"].astype(str).isin(classification_options)
                    ].drop_duplicates(subset=["Cuenta", "Region", "Recurso"], keep="first")
                    if not lambda_classification_df.empty:
                        classification_counts = (
                            lambda_classification_df["Clasificacion uso Lambda"]
                            .value_counts()
                            .reindex(classification_options, fill_value=0)
                        )
                        classification_cols = st.columns(min(len(classification_options), 5))
                        for index, classification in enumerate(classification_options[:5]):
                            classification_cols[index].metric(
                                classification,
                                int(classification_counts.get(classification, 0)),
                            )
                    technical_display_df = technical_display_df[
                        (technical_display_df["Clasificacion uso Lambda"].astype(str).isin(selected_classifications))
                        | (technical_display_df["Clasificacion uso Lambda"].astype(str).str.strip() == "")
                    ]

            sort_key = technical_display_df["Clasificacion uso Lambda"].map(
                {classification: index for index, classification in enumerate(LAMBDA_USAGE_CLASSIFICATION_ORDER)}
            )
            technical_display_df = (
                technical_display_df.assign(_orden_clasificacion=sort_key.fillna(99))
                .sort_values(["_orden_clasificacion", "Cuenta", "Region", "Recurso"], kind="stable")
                .drop(columns=["_orden_clasificacion"])
            )
            st.dataframe(
                style_lambda_usage_classification(technical_display_df),
                use_container_width=True,
                hide_index=True,
            )

        with tab_export:
            st.subheader("Export")
            vulnerability_export_df = add_lambda_usage_classification_for_export(vulnerability_df)
            backlog_export_columns = [
                column for column in [
                    "Clasificacion uso Lambda",
                    "Detalle clasificacion Lambda",
                    *VULNERABILITY_BACKLOG_COLUMNS,
                ]
                if column in vulnerability_export_df.columns
            ]
            backlog_export_df = vulnerability_export_df[backlog_export_columns]
            full_export = BytesIO()
            backlog_export = BytesIO()
            by_owner_export = BytesIO()
            vulnerability_export_df.to_excel(full_export, index=False, sheet_name="Vulnerabilidades")
            backlog_export_df.to_excel(backlog_export, index=False, sheet_name="Backlog")
            with pd.ExcelWriter(by_owner_export, engine="openpyxl") as writer:
                for owner, owner_df in vulnerability_export_df.groupby("Responsable sugerido", dropna=False):
                    sheet_name = _safe_export_slug(owner or "sin_responsable")[:31] or "sin_responsable"
                    owner_df.to_excel(writer, index=False, sheet_name=sheet_name)

            export_col1, export_col2, export_col3 = st.columns(3)
            with export_col1:
                st.download_button(
                    "Descargar detalle completo",
                    data=full_export.getvalue(),
                    file_name="vulnerabilidades_detalle.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            with export_col2:
                st.download_button(
                    "Descargar backlog ejecutivo",
                    data=backlog_export.getvalue(),
                    file_name="vulnerabilidades_backlog.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            with export_col3:
                st.download_button(
                    "Descargar por responsable",
                    data=by_owner_export.getvalue(),
                    file_name="vulnerabilidades_por_responsable.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

elif page == "Comparacion Regional":
    target_account = REGIONAL_COMPARISON_TARGET["account"]
    left_region = REGIONAL_COMPARISON_TARGET["left_region"]
    right_region = REGIONAL_COMPARISON_TARGET["right_region"]
    left_label = REGIONAL_COMPARISON_TARGET["left_label"]
    right_label = REGIONAL_COMPARISON_TARGET["right_label"]

    st.title("Comparacion Regional")
    st.caption(
        "Vista inicial de espejo/DR basada en cache local para afex-prod entre Virginia y Ohio."
    )

    st.markdown(
        build_resource_summary_card(
            "Par analizado",
            "afex-prod",
            f"{left_label} ({left_region}) vs {right_label} ({right_region})",
        ),
        unsafe_allow_html=True,
    )

    comparison_results = [
        compare_regional_service(target_account, left_region, right_region, service_meta)
        for service_meta in REGIONAL_COMPARISON_SERVICES
    ]

    total_only_left = sum(result["only_left"] for result in comparison_results)
    total_only_right = sum(result["only_right"] for result in comparison_results)
    total_shared_equal = sum(result["shared_equal"] for result in comparison_results)
    total_shared_different = sum(result["shared_different"] for result in comparison_results)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Solo Virginia", total_only_left)
    with col2:
        st.metric("Solo Ohio", total_only_right)
    with col3:
        st.metric("En ambas", total_shared_equal + total_shared_different)
    with col4:
        st.metric("Config distinta", total_shared_different)

    st.subheader("Servicios Regionales")
    st.caption(
        "El matching usa el nombre base del componente y elimina marcadores como prod/cert, Virginia/Ohio y us-east-1/us-east-2."
    )

    for result in comparison_results:
        cache_note = (
            f"{left_label}: {'Fresco' if result['left_fresh'] else 'Viejo' if result['left_exists'] else 'Sin datos'}"
            f" | {right_label}: {'Fresco' if result['right_fresh'] else 'Viejo' if result['right_exists'] else 'Sin datos'}"
        )
        expander_title = (
            f"{result['label']} | "
            f"solo {left_label}: {result['only_left']} | "
            f"solo {right_label}: {result['only_right']} | "
            f"ambas: {result['shared_equal'] + result['shared_different']}"
        )

        with st.expander(expander_title, expanded=False):
            st.caption(cache_note)

            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
            with metric_col1:
                st.metric(left_label, result["left_count"])
            with metric_col2:
                st.metric(right_label, result["right_count"])
            with metric_col3:
                st.metric("Coinciden", result["shared_equal"])
            with metric_col4:
                st.metric("Config distinta", result["shared_different"])

            if result["left_duplicates"] or result["right_duplicates"]:
                st.warning(
                    "Se detectaron claves repetidas al normalizar nombres. "
                    f"{left_label}: {result['left_duplicates']} | "
                    f"{right_label}: {result['right_duplicates']}"
                )

            if not result["left_exists"] and not result["right_exists"]:
                st.info("No hay cache disponible para este servicio en ninguna de las dos regiones.")
                continue

            results_df = result["results_df"]
            if results_df.empty:
                st.success("No se detectaron diferencias ni componentes comparables para este servicio.")
                continue

            display_df = sanitize_dataframe_for_display(results_df)
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.subheader("Resumen Visual")
    chart_rows = []
    for result in comparison_results:
        chart_rows.extend(
            [
                {"Servicio": result["label"], "Estado": f"Solo {left_label}", "Cantidad": result["only_left"]},
                {"Servicio": result["label"], "Estado": f"Solo {right_label}", "Cantidad": result["only_right"]},
                {
                    "Servicio": result["label"],
                    "Estado": "En ambas",
                    "Cantidad": result["shared_equal"] + result["shared_different"],
                },
            ]
        )

    chart_df = pd.DataFrame(chart_rows)
    if not chart_df.empty and chart_df["Cantidad"].sum() > 0:
        fig = px.bar(
            chart_df,
            x="Servicio",
            y="Cantidad",
            color="Estado",
            barmode="stack",
            title="Comparacion de Componentes por Servicio",
            labels={"Cantidad": "Cantidad de componentes", "Servicio": "Servicio"},
            color_discrete_map={
                f"Solo {left_label}": "#1a4a2e",
                f"Solo {right_label}": "#b91c1c",
                "En ambas": "#52525b",
            },
        )
        fig = style_plotly_figure(fig, theme_name)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aun no hay suficientes datos cacheados para construir el grafico comparativo.")

    st.subheader("Componentes Globales")
    st.caption(
        "Estos servicios pertenecen a la cuenta y se muestran aparte para no mezclarlos con la logica espejo regional."
    )
    global_services_df = get_global_services_snapshot(target_account)
    st.dataframe(sanitize_dataframe_for_display(global_services_df), use_container_width=True, hide_index=True)
