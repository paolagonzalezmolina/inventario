"""
app.py - Dashboard principal Streamlit

Inventario AWS multi-cuenta en tiempo real.
"""

import logging

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
    "CloudFormation": "cloudformation",
    "SSM (Parametros)": "ssm",
    "KMS (Claves)": "kms",
    "DynamoDB (Tablas)": "dynamodb",
    "SQS (Colas)": "sqs",
}


def get_account_regions(account_name):
    """Retorna las regiones configuradas para una cuenta con fallback seguro."""
    return PERFILES.get(account_name, {}).get("regiones") or ["us-east-1"]


def get_global_region(account_name):
    """Retorna la region base donde se guardan servicios globales."""
    return get_account_regions(account_name)[0]


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
        template = "plotly_white"
    else:
        font_color = "#e5e7eb"
        legend_bg = "rgba(17,24,39,0.98)"
        legend_border = "#475569"
        paper_bg = "#111827"
        plot_bg = "#111827"
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

page = st.sidebar.radio("Navegacion", ["Dashboard", "Infraestructura AWS"])

st.sidebar.divider()

account_names = list(PERFILES.keys())
selected_account = st.sidebar.selectbox("Cuenta AWS", account_names)
selected_account_regions = get_account_regions(selected_account)

selected_region = st.sidebar.selectbox("Region", selected_account_regions)

st.sidebar.divider()
st.sidebar.subheader("Descargas")

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("Descargar Todo", use_container_width=True):
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
    if st.button("Limpiar Cache", use_container_width=True):
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
        st.subheader(f"Cuenta: {selected_account} | Region: {selected_region}")

        metrics_data = {}
        for service_key, display_name in SERVICE_LABELS:
            service_region = get_service_region(
                selected_account,
                selected_region,
                service_key,
            )
            count, is_fresh, exists = load_cached_count(
                selected_account,
                service_region,
                service_key,
            )
            status = "Fresco" if is_fresh else "Viejo" if exists else "Sin datos"
            metrics_data[display_name] = (count, status)

        cols = st.columns(4)
        for idx, (display_name, (count, status)) in enumerate(metrics_data.items()):
            with cols[idx % 4]:
                st.metric(display_name, count, delta=status)

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

            for region in get_account_regions(account):
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

        if st.button("Descargar Excel", use_container_width=True):
            try:
                output_file = "aws_inventory.xlsx"
                export_to_excel(cache_manager, account_names, PERFILES, output_file)
                with open(output_file, "rb") as file_obj:
                    st.download_button(
                        "Descargar archivo",
                        file_obj,
                        "aws_inventory.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
            except Exception as exc:
                st.error(f"Error generando Excel: {exc}")

else:
    st.title("Infraestructura AWS")

    resource_type = st.selectbox("Tipo de Recurso", list(RESOURCE_OPTIONS.keys()))
    cache_key = RESOURCE_OPTIONS[resource_type]
    use_region = get_service_region(selected_account, selected_region, cache_key)

    data, is_fresh, exists = cache_manager.get(selected_account, use_region, cache_key)

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
            freshness = "Fresco" if is_fresh else "Viejo"
            st.markdown(
                build_resource_summary_card(resource_type, len(data), freshness),
                unsafe_allow_html=True,
            )

            st.subheader("Datos")
            display_data = sanitize_dataframe_for_display(data)
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

    except Exception as exc:
        st.error(f"Error procesando datos: {str(exc)}")
