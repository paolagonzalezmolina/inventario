"""
app.py — Inventario AWS (1 cuenta)
======================================================
Secciones: Infraestructura · Lambda · Redes · EC2 · BBDD · Multi-cuenta
Corre con:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json

# ─── Fuente de datos ──────────────────────────────────────────────────────────
MODO_DEMO = False   # ← Cambiar a True si no tienes credenciales AWS

if MODO_DEMO:
    from datos_ejemplo import (
        get_ec2_df, get_rds_df, get_lambda_df,
        get_vpc_df, get_alertas,
        get_relaciones, get_resumen
    )
    # Funciones stub para modo demo
    def get_identity():
        return {"account_id": "123456789012", "account_name": "DEMO-ACCOUNT",
                "arn": "arn:aws:iam::123456789012:user/demo",
                "user_id": "DEMO", "region": "us-east-1"}
    def get_aurora_df():
        return pd.DataFrame(columns=["id","nombre","motor","version","estado","tipo","tipo_bd","region","az","vpc","multi_az","almacenamiento_gb","miembros","endpoint","ultima_actualizacion"])
    def get_dynamodb_df():
        return pd.DataFrame(columns=["id","nombre","motor","version","estado","tipo","tipo_bd","region","items","tamaño_bytes","rcu","wcu","gsi_count","ultima_actualizacion"])
    def get_subnets_df():
        return pd.DataFrame(columns=["id","nombre","vpc_id","cidr","az","ips_disponibles","publica","estado"])
    def get_azs_df():
        return pd.DataFrame(columns=["nombre","zone_id","tipo","estado","region","grupo"])
    def get_s3_df():
        return pd.DataFrame(columns=["nombre","region","creado"])
    def get_api_df():
        return pd.DataFrame(columns=["id","nombre","tipo","estado","region","endpoint","version"])
    def get_iam_users_df():
        return pd.DataFrame(columns=["nombre","tipo","estado","mfa","politicas","n_politicas","ultimo_acceso","pwd_rotacion","access_keys","arn"])
    def get_resumen_perfil(perfil):
        return {"perfil":perfil,"region":"us-east-1","ec2_total":0,"ec2_running":0,"rds_total":0,"aurora_total":0,"bd_total":0,"lambda_total":0,"s3_total":0,"dynamo_total":0,"vpc_total":0,"subnet_total":0}
    def get_identity_perfil(perfil):
        return {"account_id":"—","account_name":perfil,"arn":"—","region":"us-east-1","perfil":perfil}
    def get_ec2_perfil(perfil):      return pd.DataFrame()
    def get_rds_perfil(perfil):      return pd.DataFrame()
    def get_lambda_perfil(perfil):   return pd.DataFrame()
    def get_vpc_perfil(perfil):      return pd.DataFrame()
    def get_s3_perfil(perfil):       return pd.DataFrame()
    def get_dynamodb_perfil(perfil): return pd.DataFrame()
    def get_iam_users_perfil(perfil): return pd.DataFrame()
    def get_comparacion_regiones(perfil): return []
    def _regiones(perfil): return ["us-east-1"]
    def _df_region(perfil, region, tipo): return pd.DataFrame()
    def get_resumen_region(perfil, region): return {}
else:
    try:
        from conector_aws import (
            get_ec2_df, get_rds_df, get_lambda_df,
            get_vpc_df, get_alertas,
            get_relaciones, get_resumen,
            get_identity, get_aurora_df, get_dynamodb_df,
            get_subnets_df, get_azs_df, get_s3_df, get_api_df,
            get_iam_users_df, get_iam_users_perfil,
            get_resumen_perfil, get_identity_perfil,
            get_ec2_perfil, get_rds_perfil, get_lambda_perfil,
            get_vpc_perfil, get_s3_perfil, get_dynamodb_perfil,
            get_comparacion_regiones, _regiones, _df_region, get_resumen_region,
        )
    except Exception as _e:
        st.error(f"❌ Error conectando a AWS: {_e}")
        st.info("Verifica que corriste: aws configure --profile inventario")
        st.stop()

# ─── Configuración de la página ───────────────────────────────────────────────
st.set_page_config(
    page_title="Inventario AWS",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Estilos CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    [data-testid="stSidebar"] { background-color: #0f1117; border-right: 1px solid #2a2d3a; }
    [data-testid="stSidebar"] * { color: #c8ccd4 !important; }
    [data-testid="stSidebar"] .stRadio label { font-size: 0.9rem; padding: 6px 0; cursor: pointer; }
    [data-testid="stMetric"] { background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 8px; padding: 16px 20px; }
    [data-testid="stMetricLabel"] { font-size: 0.78rem; color: #8b8fa8 !important; text-transform: uppercase; letter-spacing: 0.05em; }
    [data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace; font-size: 1.8rem; color: #e8eaf0 !important; }
    .alerta-critica { background: #1f0f0f; border-left: 3px solid #e05252; border-radius: 4px; padding: 12px 16px; margin-bottom: 8px; font-size: 0.88rem; }
    .alerta-aviso   { background: #1a1505; border-left: 3px solid #d4a017; border-radius: 4px; padding: 12px 16px; margin-bottom: 8px; font-size: 0.88rem; }
    .alerta-info    { background: #0a1520; border-left: 3px solid #3a7bd5; border-radius: 4px; padding: 12px 16px; margin-bottom: 8px; font-size: 0.88rem; }
    .demo-badge { display:inline-block; background:#1a1505; color:#d4a017; border:1px solid #d4a017; padding:2px 10px; border-radius:4px; font-size:0.72rem; font-family:'IBM Plex Mono',monospace; margin-left:12px; vertical-align:middle; }
    .seccion-titulo { font-size:0.75rem; text-transform:uppercase; letter-spacing:0.12em; color:#5a5e72; margin:24px 0 12px; font-weight:500; }
    .header-titulo { font-size:1.6rem; font-weight:500; color:#e8eaf0; margin:0; }
    .header-sub    { font-size:0.82rem; color:#5a5e72; font-family:'IBM Plex Mono',monospace; margin-top:2px; }
    .ctx-box { background:#0d1117; border:1px solid #1e2330; border-radius:6px; padding:10px 14px; margin-bottom:16px; font-family:'IBM Plex Mono',monospace; font-size:0.78rem; color:#8b8fa8; }
    .ctx-box strong { color:#c8ccd4; }
    .policy-box { background:#0a1520; border:1px solid #1a3050; border-radius:8px; padding:16px; margin:12px 0; }
    .inv-group { background:#111520; border:1px solid #1e2538; border-radius:8px; padding:14px 18px; margin-bottom:10px; }
    .inv-group-title { font-size:0.8rem; font-weight:500; color:#7fb8f0; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:8px; display:flex; align-items:center; gap:8px; }
    .inv-group-count { font-family:'IBM Plex Mono',monospace; font-size:1.3rem; color:#e8eaf0; font-weight:500; }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
OPCIONES_MENU = [
    "📊 Infraestructura AWS",
    "🪣 S3 — Buckets",
    "👥 Usuarios IAM",
    "🗺️ Multi-región",
    "🌍 Multi-cuenta",
]

if "ir_a_seccion" in st.session_state:
    destino = st.session_state.pop("ir_a_seccion")
    if destino in OPCIONES_MENU:
        st.session_state["menu_radio"] = destino

with st.sidebar:
    st.markdown("### ☁️ Inventario AWS")
    st.markdown("---")
    seccion = st.radio("Sección", OPCIONES_MENU, label_visibility="collapsed", key="menu_radio")
    st.markdown("---")
    st.markdown("<small style='color:#3a3e52'>Última actualización</small>", unsafe_allow_html=True)
    st.markdown(f"<small style='font-family:IBM Plex Mono;color:#5a5e72'>{datetime.now().strftime('%Y-%m-%d %H:%M')}</small>", unsafe_allow_html=True)
    if MODO_DEMO:
        st.markdown("<br><small style='color:#d4a017'>⚠ Modo demo — datos de ejemplo</small>", unsafe_allow_html=True)

# ─── Cargar datos base (solo identidad — el resto se carga por sección) ───
identity = get_identity()

# ─── Helper: Context Bar ─────────────────────────────────────────────────────
def mostrar_contexto():
    """Muestra barra de contexto con cuenta, nombre, región y usuario."""
    nombre_cuenta = identity.get('account_name', '')
    label_cuenta = f"{nombre_cuenta} ({identity['account_id']})" if nombre_cuenta else identity['account_id']
    st.markdown(f"""
    <div class="ctx-box">
        <strong>Cuenta:</strong> {label_cuenta} &nbsp;·&nbsp;
        <strong>Región:</strong> {identity['region']} &nbsp;·&nbsp;
        <strong>Usuario:</strong> {identity['arn'].split('/')[-1] if '/' in identity['arn'] else identity['arn']}
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1 — INFRAESTRUCTURA AWS (inventario agrupado por tipo)
# ═══════════════════════════════════════════════════════════════════════════════
# ─── Helpers multi-cuenta ────────────────────────────────────────────────────
# Opciones de cuenta/región — agregar más aquí cuando se sumen cuentas
OPCIONES_CUENTA_REGION = [
    ("afex-des",     "us-east-1"),
    ("afex-prod",    "us-east-1"),
    ("afex-prod",    "us-east-2"),
    ("afex-peru",    "us-east-1"),
    ("afex-digital", "us-east-1"),
]

REGIONES_NOMBRES_APP = {
    "us-east-1": "us-east-1 Virginia",
    "us-east-2": "us-east-2 Ohio",
    "us-west-1": "us-west-1 California",
    "us-west-2": "us-west-2 Oregon",
    "sa-east-1": "sa-east-1 São Paulo",
}

@st.cache_data(ttl=300)
def _nombre_cuenta_region(perfil, region):
    try:
        d = get_identity_perfil(perfil)
        nombre = d.get("account_name", perfil)
        cuenta = d.get("account_id", "")
        region_nombre = REGIONES_NOMBRES_APP.get(region, region)
        return f"{nombre} ({cuenta}) - {region_nombre}"
    except Exception:
        return f"{perfil} - {REGIONES_NOMBRES_APP.get(region, region)}"

def selector_cuenta(key="sel"):
    """Retorna (perfil, region) según selección del usuario."""
    opciones = {_nombre_cuenta_region(p, r): (p, r) for p, r in OPCIONES_CUENTA_REGION}
    sel = st.selectbox("Cuenta / Región", list(opciones.keys()), key=f"cta_{key}")
    return opciones[sel]

def contexto_perfil(perfil):
    d   = get_identity_perfil(perfil)
    nom = d.get("account_name", perfil)
    lbl = f"{nom} ({d['account_id']})" if d.get("account_id","—") != "—" else nom
    usr = d["arn"].split("/")[-1] if "/" in d.get("arn","") else d.get("arn","—")
    st.markdown(f'''<div class="ctx-box"><strong>Cuenta:</strong> {lbl} &nbsp;·&nbsp;
        <strong>Región:</strong> {d["region"]} &nbsp;·&nbsp;
        <strong>Usuario:</strong> {usr}</div>''', unsafe_allow_html=True)

def contexto_perfil_region(perfil, region):
    d   = get_identity_perfil(perfil)
    nom = d.get("account_name", perfil)
    lbl = f"{nom} ({d['account_id']})" if d.get("account_id","—") != "—" else nom
    usr = d["arn"].split("/")[-1] if "/" in d.get("arn","") else d.get("arn","—")
    region_nombre = REGIONES_NOMBRES_APP.get(region, region)
    st.markdown(f'''<div class="ctx-box"><strong>Cuenta:</strong> {lbl} &nbsp;·&nbsp;
        <strong>Región:</strong> {region_nombre} &nbsp;·&nbsp;
        <strong>Usuario:</strong> {usr}</div>''', unsafe_allow_html=True)

if seccion == "📊 Infraestructura AWS":

    demo_tag = '<span class="demo-badge">DEMO</span>' if MODO_DEMO else ''
    st.markdown(f'<p class="header-titulo">Infraestructura AWS {demo_tag}</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">Inventario completo de componentes en la nube</p>', unsafe_allow_html=True)
    st.markdown("")

    perfil_activo, region_activa = selector_cuenta("infra")
    st.markdown("")

    # Cargar datos de la región seleccionada específicamente
    if perfil_activo == "inventario":
        resumen_base = get_resumen()
        df_ec2    = get_ec2_df()
        df_rds    = get_rds_df()
        df_aurora = get_aurora_df()
        df_dynamo = get_dynamodb_df()
        df_lambda = get_lambda_df()
        df_vpc    = get_vpc_df()
        df_subnet = get_subnets_df()
        df_s3     = get_s3_df()
        df_api    = get_api_df()
        regiones_perfil = ["us-east-1"]
    else:
        # Cargar datos de la región activa (no todas las regiones combinadas)
        df_ec2    = _df_region(perfil_activo, region_activa, "ec2")
        df_rds    = _df_region(perfil_activo, region_activa, "rds")
        df_lambda = _df_region(perfil_activo, region_activa, "lambda")
        df_vpc    = _df_region(perfil_activo, region_activa, "vpc")
        df_dynamo = _df_region(perfil_activo, region_activa, "dynamo")
        df_aurora = pd.DataFrame()
        df_subnet = pd.DataFrame()
        df_s3     = get_s3_perfil(perfil_activo)   # S3 es global, no por región
        df_api    = pd.DataFrame()
        resumen_base = get_resumen_region(perfil_activo, region_activa)
        regiones_perfil = _regiones(perfil_activo)

    # Resumen para los 8 cuadros — datos de la región activa
    resumen = {
        "ec2_total":    len(df_ec2),
        "ec2_running":  len(df_ec2[df_ec2["estado"]=="running"]) if not df_ec2.empty and "estado" in df_ec2.columns else 0,
        "lambda_total": len(df_lambda),
        "bd_total":     len(df_rds) + len(df_aurora) + len(df_dynamo),
        "vpc_total":    len(df_vpc),
        "subnet_total": len(df_subnet),
        "aurora_total": len(df_aurora),
        "dynamo_total": len(df_dynamo),
        "s3_total":     len(df_s3),
        "rds_total":    len(df_rds),
    }

    # ── Tarjetas resumen — 8 cuadros ─────────────────────────────────────────
    tarjetas = [
        ("#0c1f3a", "#185FA5", "#378ADD", "EC2",      str(resumen.get('ec2_total', len(df_ec2)))),
        ("#2a1a05", "#854F0B", "#d4a017", "LAMBDA",   str(resumen.get('lambda_total', len(df_lambda)))),
        ("#0a2a1f", "#0F6E56", "#3ecf8e", "BBDD",     str(resumen.get('bd_total', len(df_rds)))),
        ("#1a1040", "#534AB7", "#7F77DD", "VPC",      str(resumen.get('vpc_total', len(df_vpc)))),
        ("#0a1f1a", "#0F6E56", "#5DCAA5", "SUBNETS",  str(resumen.get('subnet_total', len(df_subnet)))),
        ("#1a0f30", "#7F77DD", "#AFA9EC", "AURORA",   str(resumen.get('aurora_total', len(df_aurora)))),
        ("#1a1a05", "#639922", "#97C459", "DYNAMO",   str(resumen.get('dynamo_total', len(df_dynamo)))),
        ("#1a0f0a", "#993C1D", "#F0997B", "S3",       str(resumen.get('s3_total', len(df_s3)))),
    ]
    col1, col2, col3, col4 = st.columns(4)
    col5, col6, col7, col8 = st.columns(4)
    for i, (bg, borde, texto, label, valor) in enumerate(tarjetas):
        col = [col1,col2,col3,col4,col5,col6,col7,col8][i]
        with col:
            st.markdown(f"""
            <div style="background:{bg};border:1px solid {borde};border-radius:10px;
                        padding:18px 12px;text-align:center;margin-bottom:4px">
                <div style="font-size:11px;color:{texto};text-transform:uppercase;
                            letter-spacing:0.06em;margin-bottom:8px">{label}</div>
                <div style="font-size:28px;font-weight:500;color:#e8eaf0;
                            font-family:monospace">{valor}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("")

    contexto_perfil_region(perfil_activo, region_activa)

    # ── Inventario agrupado por tipo ──────────────────────────────────────────
    st.markdown('<p class="seccion-titulo">Inventario agrupado por tipo de componente</p>', unsafe_allow_html=True)

    # Detectar si la cuenta tiene múltiples regiones
    regiones_perfil = _regiones(perfil_activo)
    multi_region    = len(regiones_perfil) > 1

    grupos = [
        ("🖥️", "EC2 — Instancias",    df_ec2,    ["nombre","tipo","estado","ip_privada","vpc"],          "ec2"),
        ("⚡",  "Lambda — Funciones",  df_lambda, ["nombre","runtime","estado","memoria_mb","tags"],             "lambda"),
        ("🌐",  "VPC — Redes",         df_vpc,    ["nombre","cidr","subnets","estado","internet_gateway"],"vpc"),
        ("📡",  "Subnets",             df_subnet, ["nombre","vpc_id","cidr","az","publica"],              "subnet"),
        ("🗄️",  "RDS — Instancias",    df_rds,    ["nombre","motor","version","estado","tipo"],           "rds"),
        ("🌀",  "Aurora — Clusters",   df_aurora, ["nombre","motor","version","estado","miembros"] if "miembros" in df_aurora.columns else ["nombre","motor","version","estado"], "aurora"),
        ("📦",  "DynamoDB — Tablas",   df_dynamo, ["nombre","estado","items","rcu","wcu"] if "items" in df_dynamo.columns else ["nombre","estado"], "dynamo"),
        ("🪣",  "S3 — Buckets",        df_s3,     ["nombre","region","creado"],                           "s3"),
    ]

    TIPOS_MULTIREGION = {"ec2","lambda","vpc","rds","dynamo"}

    for icono, titulo, df, columnas, tipo_key in grupos:
        cols_validas = [c for c in columnas if c in df.columns]
        count = len(df)
        st.markdown(f"""
        <div class="inv-group">
            <div class="inv-group-title">{icono} {titulo} <span class="inv-group-count">{count}</span></div>
        </div>""", unsafe_allow_html=True)

        if multi_region and tipo_key in TIPOS_MULTIREGION:
            # Dos columnas: una por región
            col_r1, col_r2 = st.columns(2)
            for col_r, region_iter in zip([col_r1, col_r2], regiones_perfil):
                region_nombre = REGIONES_NOMBRES_APP.get(region_iter, region_iter)
                with col_r:
                    st.markdown(f"**{region_nombre}**")
                    try:
                        df_r = _df_region(perfil_activo, region_iter, tipo_key)
                        cv   = [c for c in cols_validas if c in df_r.columns]
                        if not df_r.empty and cv:
                            st.dataframe(df_r[cv], use_container_width=True, hide_index=True)
                            st.caption(f"{len(df_r)} componentes")
                        else:
                            st.caption("Sin componentes en esta región.")
                    except Exception as ex:
                        st.caption(f"Error: {ex}")
        else:
            if not df.empty and cols_validas:
                st.dataframe(df[cols_validas], use_container_width=True, hide_index=True)
            else:
                st.caption("    Sin componentes de este tipo en la cuenta.")
        st.markdown("")


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2 — LAMBDA
# ═══════════════════════════════════════════════════════════════════════════════


elif seccion == "🪣 S3 — Buckets":
    st.markdown('<p class="header-titulo">S3 — Buckets</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">Todos los buckets en la cuenta seleccionada</p>', unsafe_allow_html=True)
    st.markdown("")
    perfil_s3, region_s3 = selector_cuenta("s3")
    contexto_perfil_region(perfil_s3, region_s3)
    df_s3 = get_s3_df() if perfil_s3 == "inventario" else get_s3_perfil(perfil_s3)

    if df_s3.empty:
        st.info("No se encontraron buckets S3 en esta cuenta.")
    else:
        st.metric("Total Buckets", len(df_s3))
        st.markdown("")
        st.dataframe(
            df_s3.rename(columns={"nombre": "Bucket"}),
            use_container_width=True, hide_index=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN — USUARIOS IAM
# ═══════════════════════════════════════════════════════════════════════════════


elif seccion == "👥 Usuarios IAM":
    st.markdown('<p class="header-titulo">Usuarios IAM</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">Cuentas de acceso, estado y políticas de permisos</p>', unsafe_allow_html=True)
    st.markdown("")
    perfil_iam, region_iam = selector_cuenta("iam")
    contexto_perfil_region(perfil_iam, region_iam)
    df_iam = get_iam_users_df() if perfil_iam == "inventario" else get_iam_users_perfil(perfil_iam)

    if df_iam.empty:
        st.info("No se encontraron usuarios IAM o falta el permiso IAMReadOnlyAccess.")
    else:
        total      = len(df_iam)
        activos    = len(df_iam[df_iam["estado"].str.contains("Activo",  na=False)])
        bloqueados = len(df_iam[df_iam["estado"].str.contains("Bloqueado", na=False)])
        sin_mfa    = len(df_iam[df_iam["mfa"].str.contains("Sin MFA", na=False)])

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: st.metric("Total usuarios",  total)
        with c2: st.metric("🟢 Activos",      activos)
        with c3: st.metric("🔴 Bloqueados",   bloqueados,  delta="revisar" if bloqueados else None, delta_color="inverse")
        with c4: st.metric("⚠️ Sin MFA",      sin_mfa,     delta="riesgo" if sin_mfa else None, delta_color="inverse")
        with c5: st.metric("Tipo servicio",   len(df_iam[df_iam["tipo"] == "Servicio"]) if "tipo" in df_iam.columns else 0)

        st.markdown("")

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1: filtro_estado = st.multiselect("Estado", df_iam["estado"].unique(), default=list(df_iam["estado"].unique()))
        with col_f2: filtro_tipo   = st.multiselect("Tipo",   df_iam["tipo"].unique(),   default=list(df_iam["tipo"].unique()))
        with col_f3: filtro_mfa    = st.multiselect("MFA",    df_iam["mfa"].unique(),    default=list(df_iam["mfa"].unique()))

        df_fil = df_iam[
            df_iam["estado"].isin(filtro_estado) &
            df_iam["tipo"].isin(filtro_tipo) &
            df_iam["mfa"].isin(filtro_mfa)
        ]

        st.markdown("")
        st.markdown('<p class="seccion-titulo">Detalle de usuarios</p>', unsafe_allow_html=True)
        st.dataframe(
            df_fil[["nombre","tipo","estado","mfa","politicas","n_politicas","ultimo_acceso","pwd_rotacion","access_keys"]].rename(columns={
                "nombre":"Usuario","tipo":"Tipo","estado":"Estado","mfa":"MFA",
                "politicas":"Políticas","n_politicas":"N° políticas",
                "ultimo_acceso":"Último acceso","pwd_rotacion":"Rotación pwd","access_keys":"Access Keys",
            }),
            use_container_width=True, hide_index=True,
        )
        st.caption(f"Mostrando {len(df_fil)} de {total} usuarios")

        st.markdown("")
        usuario_sel = st.selectbox("Ver detalle de usuario", df_fil["nombre"].tolist())
        if usuario_sel:
            row = df_fil[df_fil["nombre"] == usuario_sel].iloc[0]
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"""
                <div style="background:#1a1d27;border:1px solid #2a2d3a;border-radius:10px;padding:16px">
                    <div style="font-size:14px;font-weight:500;color:#e8eaf0;margin-bottom:12px">{row['nombre']}</div>
                    <div style="font-size:12px;color:#5a5e72;margin-bottom:4px">Tipo: <span style="color:#c8ccd4">{row['tipo']}</span></div>
                    <div style="font-size:12px;color:#5a5e72;margin-bottom:4px">Estado: <span style="color:#c8ccd4">{row['estado']}</span></div>
                    <div style="font-size:12px;color:#5a5e72;margin-bottom:4px">MFA: <span style="color:#c8ccd4">{row['mfa']}</span></div>
                    <div style="font-size:12px;color:#5a5e72;margin-bottom:4px">Último acceso: <span style="color:#c8ccd4">{row['ultimo_acceso']}</span></div>
                    <div style="font-size:12px;color:#5a5e72;margin-bottom:4px">Rotación: <span style="color:#c8ccd4">{row['pwd_rotacion']}</span></div>
                    <div style="font-size:12px;color:#5a5e72;margin-bottom:4px">Access Keys activos: <span style="color:#c8ccd4">{row['access_keys']}</span></div>
                    <div style="font-size:11px;color:#3a3e52;margin-top:8px;font-family:monospace">{row['arn']}</div>
                </div>""", unsafe_allow_html=True)
            with col_b:
                st.markdown('<p style="font-size:12px;color:#5a5e72;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px">Políticas asignadas</p>', unsafe_allow_html=True)
                for pol in str(row["politicas"]).split(", "):
                    color = "#e05252" if "Administrator" in pol else ("#d4a017" if "Power" in pol else "#3a7bd5")
                    bg    = "#1f0a0a" if "Administrator" in pol else ("#2a1a05" if "Power" in pol else "#0c1f3a")
                    st.markdown(f"""
                    <div style="background:{bg};border:1px solid {color};border-radius:6px;
                                padding:8px 12px;margin-bottom:6px;font-size:12px;
                                font-family:monospace;color:{color}">{pol}</div>""", unsafe_allow_html=True)

        if sin_mfa > 0:
            st.warning(f"⚠️ {sin_mfa} usuario(s) sin MFA — riesgo de seguridad.")

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN — MULTI-REGIÓN
# ═══════════════════════════════════════════════════════════════════════════════
elif seccion == "🗺️ Multi-región":
    st.markdown('<p class="header-titulo">Comparación multi-región</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">Distribución de componentes por región en la cuenta seleccionada</p>', unsafe_allow_html=True)
    st.markdown("")

    # Solo aplica a cuentas con múltiples regiones
    perfil_mr, region_mr = selector_cuenta("mr")
    contexto_perfil(perfil_mr)

    st.markdown("")

    with st.spinner("Consultando regiones..."):
        datos_regiones = get_comparacion_regiones(perfil_mr)

    if not datos_regiones:
        st.info("No hay regiones configuradas para esta cuenta.")
    elif len(datos_regiones) == 1:
        st.info(f"Esta cuenta solo tiene 1 región configurada: **{datos_regiones[0]['region_nombre']}**. "
                "Para agregar más regiones, edita `PERFILES` en `conector_aws.py`.")
    else:
        # ── Tarjetas por región ──
        st.markdown('<p class="seccion-titulo">Resumen por región</p>', unsafe_allow_html=True)
        colores = [("#0c2a4a","#185FA5","#7fb8f0"), ("#0a2a1f","#0F6E56","#3ecf8e"),
                   ("#1a1040","#534AB7","#a09ee0"), ("#2a1a05","#854F0B","#d4a017")]

        cols_r = st.columns(len(datos_regiones))
        for i, (col, dr) in enumerate(zip(cols_r, datos_regiones)):
            bg, borde, texto = colores[i % len(colores)]
            error = "_error" in dr
            with col:
                st.markdown(f"""
                <div style="background:{bg};border:1px solid {borde};border-radius:10px;
                            padding:16px;text-align:center">
                    <div style="font-size:0.72rem;color:{texto};text-transform:uppercase;
                                letter-spacing:0.08em;margin-bottom:6px">{dr['region_nombre']}</div>
                    <div style="font-size:0.72rem;color:{'#e05252' if error else '#5a5e72'};margin-top:4px">
                        {'❌ ' + dr.get('_error','Error')[:40] if error else '✅ Conectado'}
                    </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("")

        # ── Tabla comparativa ──
        st.markdown('<p class="seccion-titulo">Comparación de componentes entre regiones</p>', unsafe_allow_html=True)

        componentes = ["EC2 (total)", "EC2 (running)", "RDS", "Aurora", "Lambda", "DynamoDB", "VPC", "Subnets"]
        keys        = ["ec2_total", "ec2_running", "rds_total", "aurora_total",
                       "lambda_total", "dynamo_total", "vpc_total", "subnet_total"]

        filas = []
        for comp, key in zip(componentes, keys):
            fila = {"Componente": comp}
            for dr in datos_regiones:
                fila[dr["region_nombre"]] = dr.get(key, 0)
            filas.append(fila)

        df_mr = pd.DataFrame(filas)

        # Columna diferencia si hay exactamente 2 regiones
        if len(datos_regiones) == 2:
            r1 = datos_regiones[0]["region_nombre"]
            r2 = datos_regiones[1]["region_nombre"]
            df_mr["Diferencia"] = df_mr.apply(
                lambda row: "✅ Igual" if row[r1] == row[r2]
                            else f"⚠️ {abs(row[r1] - row[r2])} diferencia",
                axis=1
            )

        st.dataframe(df_mr, use_container_width=True, hide_index=True)

        st.markdown("")

        # ── Gráfico comparativo ──
        st.markdown('<p class="seccion-titulo">Distribución gráfica por región</p>', unsafe_allow_html=True)
        nombres_regiones = [dr["region_nombre"] for dr in datos_regiones]
        df_graf = df_mr[df_mr[nombres_regiones].sum(axis=1) > 0].copy()
        if not df_graf.empty:
            df_melt = df_graf.melt(
                id_vars="Componente",
                value_vars=nombres_regiones,
                var_name="Región", value_name="Cantidad"
            )
            fig = px.bar(
                df_melt[df_melt["Cantidad"] > 0],
                x="Componente", y="Cantidad", color="Región",
                barmode="group",
                color_discrete_sequence=["#3a7bd5","#3ecf8e","#d4a017","#a09ee0"],
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#c8ccd4", height=340, showlegend=True,
                xaxis=dict(gridcolor="#1a1d27"), yaxis=dict(gridcolor="#1a1d27"),
                margin=dict(l=0,r=0,t=10,b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

        # ── Alertas de diferencia ──
        if len(datos_regiones) == 2 and "Diferencia" in df_mr.columns:
            difs = df_mr[df_mr["Diferencia"].str.contains("⚠️", na=False)]
            if not difs.empty:
                st.markdown('<p class="seccion-titulo">⚠️ Diferencias entre regiones</p>', unsafe_allow_html=True)
                for _, row in difs.iterrows():
                    st.markdown(f"""
                    <div class="alerta-aviso">
                        <strong>{row["Componente"]}</strong> — {row["Diferencia"]}<br>
                        <span style="color:#5a5e72;font-size:0.8rem">
                        {r1}: {row[r1]} &nbsp;·&nbsp; {r2}: {row[r2]}
                        </span>
                    </div>""", unsafe_allow_html=True)
            else:
                st.success("✅ Ambas regiones tienen la misma cantidad de componentes.")

        st.markdown("")
        st.info("Para agregar más regiones a una cuenta: edita la lista `regiones` en `PERFILES` dentro de `conector_aws.py`.")


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 7 — MULTI-CUENTA
# ═══════════════════════════════════════════════════════════════════════════════


elif seccion == "🌍 Multi-cuenta":
    st.markdown('<p class="header-titulo">Multi-cuenta</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">Inventario real de todas las cuentas AWS configuradas</p>', unsafe_allow_html=True)
    st.markdown("")

    # ✅ ACTUALIZADO: Lista de 4 perfiles configurados
    PERFILES_MULTI = ["afex-des", "afex-prod", "afex-peru", "afex-digital"]

    # Cargar identidad y resumen de cada cuenta
    with st.spinner("Consultando todas las cuentas AWS..."):
        datos_cuentas = []
        for perfil in PERFILES_MULTI:
            id_cuenta  = get_identity_perfil(perfil)
            res_cuenta = get_resumen_perfil(perfil)
            datos_cuentas.append({"identidad": id_cuenta, "resumen": res_cuenta})

    # Tarjetas por cuenta
    st.markdown('<p class="seccion-titulo">Estado de las cuentas</p>', unsafe_allow_html=True)
    cols_cuentas = st.columns(len(datos_cuentas))
    colores = [("#0c2a4a","#185FA5","#7fb8f0"), ("#0a2a1f","#0F6E56","#3ecf8e"),
               ("#1a1040","#534AB7","#a09ee0"), ("#2a1a05","#854F0B","#d4a017")]

    for i, (col, dc) in enumerate(zip(cols_cuentas, datos_cuentas)):
        bg, borde, texto = colores[i % len(colores)]
        idc = dc["identidad"]
        res = dc["resumen"]
        error = "_error" in res
        with col:
            st.markdown(f"""
            <div style="background:{bg};border:1px solid {borde};border-radius:10px;
                        padding:16px;text-align:center">
                <div style="font-size:0.7rem;color:{texto};text-transform:uppercase;
                            letter-spacing:0.08em;margin-bottom:4px">{idc['region']}</div>
                <div style="font-size:1rem;font-weight:500;color:#e8eaf0">{idc['account_name']}</div>
                <div style="font-size:0.72rem;color:#5a5e72;font-family:monospace;margin:3px 0">{idc['account_id']}</div>
                <div style="font-size:0.75rem;color:{'#e05252' if error else texto};margin-top:6px">
                    {'❌ Error de conexión' if error else '✅ Conectado'}
                </div>
            </div>""", unsafe_allow_html=True)

    st.markdown("")

    # Tabla comparativa
    st.markdown('<p class="seccion-titulo">Inventario comparativo entre cuentas</p>', unsafe_allow_html=True)

    componentes = ["EC2","RDS","Aurora","DynamoDB","Lambda","VPC","Subnets","S3"]
    keys        = ["ec2_total","rds_total","aurora_total","dynamo_total",
                   "lambda_total","vpc_total","subnet_total","s3_total"]

    filas = []
    for comp, key in zip(componentes, keys):
        fila = {"Componente": comp}
        for dc in datos_cuentas:
            nombre_col = dc["identidad"]["account_name"]
            fila[nombre_col] = dc["resumen"].get(key, 0)
        filas.append(fila)

    df_comp = pd.DataFrame(filas)

    # Detectar diferencias entre cuentas (réplica)
    if len(datos_cuentas) >= 2:
        nombres = [dc["identidad"]["account_name"] for dc in datos_cuentas]
        col_a, col_b = nombres[0], nombres[1]
        df_comp["Diferencia"] = df_comp.apply(
            lambda r: "✅ Igual" if r.get(col_a, 0) == r.get(col_b, 0)
                      else f"⚠️ {abs(r.get(col_a,0) - r.get(col_b,0))} de diferencia",
            axis=1
        )

    st.dataframe(df_comp, use_container_width=True, hide_index=True)

    st.markdown("")

    # Gráfico comparativo
    if len(datos_cuentas) >= 2:
        st.markdown('<p class="seccion-titulo">Comparación gráfica</p>', unsafe_allow_html=True)
        df_graf = df_comp[df_comp.select_dtypes(include="number").sum(axis=1) > 0].copy()
        if not df_graf.empty:
            nombres_graf = [dc["identidad"]["account_name"] for dc in datos_cuentas]
            df_melt = df_graf.melt(id_vars="Componente", value_vars=nombres_graf,
                                    var_name="Cuenta", value_name="Cantidad")
            fig = px.bar(df_melt[df_melt["Cantidad"] > 0],
                         x="Componente", y="Cantidad", color="Cuenta", barmode="group",
                         color_discrete_sequence=["#3a7bd5","#3ecf8e","#d4a017","#a09ee0"])
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#c8ccd4", height=320, showlegend=True,
                xaxis=dict(gridcolor="#1a1d27"), yaxis=dict(gridcolor="#1a1d27"),
                margin=dict(l=0,r=0,t=10,b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Alertas de diferencias
        difs = df_comp[df_comp["Diferencia"].str.contains("⚠️", na=False)]
        if not difs.empty:
            st.markdown('<p class="seccion-titulo">⚠️ Diferencias detectadas entre cuentas</p>', unsafe_allow_html=True)
            for _, row in difs.iterrows():
                st.markdown(f"""
                <div class="alerta-aviso">
                    <strong>{row['Componente']}</strong> — {row['Diferencia']}<br>
                    <span style="color:#5a5e72;font-size:0.8rem">
                    {col_a}: {row.get(col_a,0)} &nbsp;·&nbsp; {col_b}: {row.get(col_b,0)}
                    </span>
                </div>""", unsafe_allow_html=True)
        else:
            st.success("✅ Ambas cuentas tienen la misma cantidad de componentes.")

    st.markdown("")
    st.info("Para agregar más cuentas: crea el perfil con 'aws configure --profile nombre' y agrégalo a PERFILES_MULTI en esta sección.")
