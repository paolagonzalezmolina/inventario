"""
app.py - Dashboard principal Streamlit

Inventario AWS multi-cuenta en tiempo real.
"""

import logging
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from pandas.api.types import is_numeric_dtype

from cache_manager import cache_manager
from conector_aws import PERFILES
from download_engine import (
    download_all_parallel,
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
ALL_REGIONS_OPTION = "__all_regions__"
PRIORITY_REGIONS = ["us-east-1", "us-east-2"]

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
    regions = list(dict.fromkeys(get_account_regions(account_name)))
    prioritized = [region for region in PRIORITY_REGIONS if region in regions]
    remaining = sorted(region for region in regions if region not in prioritized)
    return prioritized + remaining


def get_region_selector_options(account_name):
    """Retorna opciones del selector con una vista consolidada al inicio."""
    return [ALL_REGIONS_OPTION] + get_prioritized_regions(account_name)


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
        font_color = "#1f2937"
        legend_bg = "rgba(255,255,255,0.98)"
        legend_border = "#cbd5e1"
        paper_bg = "#ffffff"
        plot_bg = "#ffffff"
        grid_color = "#d1d9e6"
        axis_line_color = "#7c8aa0"
        template = "plotly_white"
    else:
        font_color = "#e5e7eb"
        legend_bg = "rgba(17,24,39,0.98)"
        legend_border = "#475569"
        paper_bg = "#111827"
        plot_bg = "#111827"
        grid_color = "#334155"
        axis_line_color = "#94a3b8"
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
            "app_bg": "#f6f8fb",
            "panel_bg": "#ffffff",
            "sidebar_bg": "#eef3f9",
            "header_bg": "#f6f8fb",
            "text": "#1f2937",
            "muted_text": "#5b6472",
            "border": "#d7dfeb",
            "accent": "#0f766e",
            "accent_soft": "#d9f3ef",
            "table_header": "#edf2f7",
            "button_bg": "#ffffff",
            "button_text": "#1f2937",
            "button_border": "#cfd8e3",
            "hover_bg": "#f3f6fb",
        }

    return {
        "app_bg": "#0f172a",
        "panel_bg": "#111827",
        "sidebar_bg": "#0b1220",
        "header_bg": "#0b1220",
        "text": "#e5e7eb",
        "muted_text": "#9ca3af",
        "border": "#243041",
        "accent": "#22c55e",
        "accent_soft": "#163322",
        "table_header": "#172131",
        "button_bg": "#1f2937",
        "button_text": "#e5e7eb",
        "button_border": "#334155",
        "hover_bg": "#273449",
    }


@st.cache_resource
def init_app():
    """Inicializa la aplicacion."""
    return initialize_download_engine()


init_app()

if "theme_name" not in st.session_state:
    st.session_state["theme_name"] = "Claro"

theme_name = st.sidebar.selectbox(
    "Tema visual",
    ["Claro", "Oscuro"],
    index=0 if st.session_state["theme_name"] == "Claro" else 1,
)
st.session_state["theme_name"] = theme_name
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
        border-right: 1px solid {theme["border"]};
    }}
    [data-testid="stSidebarCollapseButton"] svg,
    [data-testid="collapsedControl"] svg {{
        fill: {theme["text"]};
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
    div[data-baseweb="select"] input,
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] svg,
    div[data-baseweb="input"] input,
    div[data-baseweb="input"] span,
    div[data-baseweb="input"] svg {{
        color: {theme["text"]};
        fill: {theme["text"]};
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
        color: {theme["text"]};
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
    ["Dashboard", "Infraestructura AWS", "Comparacion Regional"],
)

st.sidebar.divider()

account_names = list(PERFILES.keys())
selected_account = st.sidebar.selectbox("Cuenta AWS", account_names)
selected_account_regions = get_region_selector_options(selected_account)

selected_region = st.sidebar.selectbox(
    "Region",
    selected_account_regions,
    format_func=get_scope_display_label,
)
selected_region_label = get_scope_display_label(selected_region)

st.sidebar.divider()
st.sidebar.subheader("Descargas")

excel_output_path = Path("aws_inventory.xlsx")
excel_download_data = None
excel_download_name = f"{selected_account}_inventario.xlsx"

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("Descargar cache", use_container_width=True):
        with st.spinner("Descargando en paralelo..."):
            result = download_all_parallel(max_workers=4)
            if result.get("status") == "failed":
                st.error(f"Error: {result.get('error', 'Error desconocido')}")
            else:
                completed = result.get("completed", 0)
                failed = result.get("failed", 0)
                partial = result.get("partial", 0)
                if failed == 0 and partial == 0:
                    st.success(f"{completed} completadas, {failed} fallidas")
                else:
                    st.warning(
                        f"{completed} completadas, {partial} parciales, {failed} fallidas"
                    )

                download_errors = []
                for detail in result.get("details", []):
                    for error in detail.get("errors", []):
                        download_errors.append(f"{detail['account']} / {detail['region']} -> {error}")

                if download_errors:
                    st.caption("Errores detectados durante la descarga")
                    st.code("\n".join(download_errors[:50]), language=None)

with col2:
    if st.button("Descarga .xlsx", use_container_width=True):
        try:
            generated_path = export_to_excel(
                cache_manager,
                [selected_account],
                PERFILES,
                str(excel_output_path),
            )
            if generated_path and excel_output_path.exists():
                excel_download_data = excel_output_path.read_bytes()
                st.success(f"Excel listo para {selected_account}")
            else:
                st.error("No se pudo generar el archivo Excel.")
        except Exception as exc:
            st.error(f"Error generando Excel: {exc}")

if st.sidebar.button("Descarga .xlsx total", use_container_width=True):
    try:
        generated_path = export_to_excel(
            cache_manager,
            account_names,
            PERFILES,
            str(excel_output_path),
        )
        if generated_path and excel_output_path.exists():
            excel_download_data = excel_output_path.read_bytes()
            excel_download_name = "inventario_global.xlsx"
            st.success("Excel global listo para todas las cuentas")
        else:
            st.error("No se pudo generar el Excel global.")
    except Exception as exc:
        st.error(f"Error generando Excel global: {exc}")

if excel_download_data:
    st.sidebar.download_button(
        "Bajar .xlsx",
        data=excel_download_data,
        file_name=excel_download_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

if st.sidebar.button("Limpiar Cache", use_container_width=True):
    cache_manager.clear()
    st.success("Cache limpiado")

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
        st.subheader(f"Cuenta: {selected_account} | Vista: {selected_region_label}")
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

        cols = st.columns(4)
        for idx, (display_name, (count, status)) in enumerate(metrics_data.items()):
            with cols[idx % 4]:
                st.metric(display_name, count, delta=status)

        if selected_region == ALL_REGIONS_OPTION:
            region_summary_df = build_account_region_summary(selected_account)
            if not region_summary_df.empty:
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

            account_data.append(acc_data)

        for acc_data in account_data:
            for key in totals:
                totals[key] += acc_data[key]

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("EC2", totals["EC2"])
        with col2:
            st.metric("RDS", totals["RDS"])
        with col3:
            st.metric("VPC", totals["VPC"])
        with col4:
            st.metric("S3", totals["S3"])
        with col5:
            st.metric("Lambda", totals["Lambda"])

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("API GW", totals["API"])
        with col2:
            st.metric("CloudFormation", totals["CloudFormation"])
        with col3:
            st.metric("SSM", totals["SSM"])
        with col4:
            st.metric("KMS", totals["KMS"])
        with col5:
            st.metric("DynamoDB", totals["DynamoDB"])

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("SQS", totals["SQS"])
        with col2:
            st.metric("NAT/IPs", totals["NAT/IPs"])
        with col3:
            st.metric("IAM", totals["IAM"])
        with col4:
            st.empty()
        with col5:
            st.empty()

        st.subheader("Comparativa por Cuenta")
        if account_data:
            df_comp = pd.DataFrame(account_data)
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
            scope_text = f"{selected_account} | {selected_region_label}"
            st.markdown(
                build_resource_summary_card(resource_type, len(data), f"{freshness} | {scope_text}"),
                unsafe_allow_html=True,
            )

            st.subheader("Datos")
            display_data = sanitize_dataframe_for_display(data)
            if "region" in display_data.columns:
                display_data["region"] = display_data["region"].map(get_region_display_label)

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

else:
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
                f"Solo {left_label}": "#0f766e",
                f"Solo {right_label}": "#dc2626",
                "En ambas": "#2563eb",
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
