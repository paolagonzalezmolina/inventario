"""
app.py — Inventario AWS (CON CACHÉ LOCAL)
======================================================
Secciones: Dashboard · Infraestructura · Lambda · Redes · EC2 · BBDD · Multi-cuenta
Corre con:  streamlit run app.py

NUEVAS CARACTERÍSTICAS:
- Caché local persistente en ~/.cache/aws_inventory/
- Detección automática de cambios
- Dashboard con estado del caché y alertas
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
from cache_manager import cache_manager

# ─── Fuente de datos ──────────────────────────────────────────────────────────
MODO_DEMO = False   # ← Cambiar a True si no tienes credenciales AWS

if MODO_DEMO:
    from datos_ejemplo import (
        get_ec2_df, get_rds_df, get_lambda_df,
        get_vpc_df, get_alertas,
        get_relaciones, get_resumen
    )
    def get_cache_status():
        return {'metadata': {}, 'stats': {'total_files': 0, 'total_size_mb': 0, 'cache_dir': 'demo'}}
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
            get_cache_status, comparar_lambdas_produccion, get_api_lambda_mapping,
        )
    except Exception as _e:
        st.error(f"❌ Error conectando a AWS: {_e}")
        st.info("Verifica que corriste: aws configure --profile inventario")
        st.stop()

# ─── CACHE PARA LLAMADAS FRECUENTES ───────────────────────────────────────────
@st.cache_resource(show_spinner=False)  # Silencioso, sin mostrar "Running..."
def get_identity_perfil_cached(perfil):
    """Versión cacheada SIN mostrar 'Running...'"""
    return get_identity_perfil(perfil)

# ─── FUNCIÓN PARA EXPORTAR TODO ───────────────────────────────────────────────
@st.cache_data(ttl=3600)
def obtener_inventario_completo():
    """Recopila TODA la información de todas las cuentas y regiones"""
    try:
        datos = []
        PERFILES = ["afex-des", "afex-prod", "afex-peru", "afex-digital"]
        
        for perfil in PERFILES:
            try:
                # Obtener nombre de cuenta
                cuenta_info = get_identity_perfil_cached(perfil)
                nombre_cuenta = cuenta_info.get('account_name', perfil) if cuenta_info else perfil
                
                # EC2
                try:
                    ec2_df = get_ec2_perfil(perfil)
                    if ec2_df is not None and not ec2_df.empty:
                        for _, row in ec2_df.iterrows():
                            datos.append({
                                'Tipo': 'EC2',
                                'Nombre': str(row.get('nombre', '—')),
                                'Cuenta': nombre_cuenta,
                                'Región': str(row.get('region', '—'))
                            })
                except: pass
                
                # Lambda
                try:
                    lambda_df = get_lambda_perfil(perfil)
                    if lambda_df is not None and not lambda_df.empty:
                        for _, row in lambda_df.iterrows():
                            datos.append({
                                'Tipo': 'Lambda',
                                'Nombre': str(row.get('nombre', '—')),
                                'Cuenta': nombre_cuenta,
                                'Región': str(row.get('region', '—'))
                            })
                except: pass
                
                # RDS
                try:
                    rds_df = get_rds_perfil(perfil)
                    if rds_df is not None and not rds_df.empty:
                        for _, row in rds_df.iterrows():
                            datos.append({
                                'Tipo': 'RDS',
                                'Nombre': str(row.get('nombre', '—')),
                                'Cuenta': nombre_cuenta,
                                'Región': str(row.get('region', '—'))
                            })
                except: pass
                
                # S3
                try:
                    s3_df = get_s3_perfil(perfil)
                    if s3_df is not None and not s3_df.empty:
                        for _, row in s3_df.iterrows():
                            datos.append({
                                'Tipo': 'S3',
                                'Nombre': str(row.get('nombre', '—')),
                                'Cuenta': nombre_cuenta,
                                'Región': str(row.get('region', '—'))
                            })
                except: pass
                
                # VPC
                try:
                    vpc_df = get_vpc_perfil(perfil)
                    if vpc_df is not None and not vpc_df.empty:
                        for _, row in vpc_df.iterrows():
                            datos.append({
                                'Tipo': 'VPC',
                                'Nombre': str(row.get('nombre', '—')),
                                'Cuenta': nombre_cuenta,
                                'Región': str(row.get('region', '—'))
                            })
                except: pass
                
            except Exception as e:
                pass
        
        if datos:
            return pd.DataFrame(datos)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

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
    .alerta-cambio  { background: #0a1a0f; border-left: 3px solid #5ecf8e; border-radius: 4px; padding: 12px 16px; margin-bottom: 8px; font-size: 0.88rem; }
    .demo-badge { display:inline-block; background:#1a1505; color:#d4a017; border:1px solid #d4a017; padding:2px 10px; border-radius:4px; font-size:0.72rem; font-family:'IBM Plex Mono',monospace; margin-left:12px; vertical-align:middle; }
    .seccion-titulo { font-size:0.75rem; text-transform:uppercase; letter-spacing:0.12em; color:#5a5e72; margin:24px 0 12px; font-weight:500; }
    .header-titulo { font-size:1.6rem; font-weight:500; color:#e8eaf0; margin:0; }
    .header-sub    { font-size:0.82rem; color:#5a5e72; font-family:'IBM Plex Mono',monospace; margin-top:2px; }
    .ctx-box { background:#0d1117; border:1px solid #1e2330; border-radius:6px; padding:10px 14px; margin-bottom:16px; font-family:'IBM Plex Mono',monospace; font-size:0.78rem; color:#8b8fa8; }
    .ctx-box strong { color:#c8ccd4; }
    .cache-box { background:#0d1520; border:1px solid #1a3050; border-radius:6px; padding:14px; margin-bottom:12px; font-family:'IBM Plex Mono',monospace; font-size:0.75rem; }
    .cache-box-item { margin-bottom: 8px; color: #8b8fa8; }
    .cache-box-item strong { color: #7fb8f0; }
    .cache-fresh { color: #5ecf8e; }
    .cache-stale { color: #d4a017; }
    .cache-error { color: #e05252; }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
OPCIONES_MENU = [
    "📊 Dashboard",
    "📈 Infraestructura AWS",
    "🪣 S3 — Buckets",
    "⚡ Lambda",
    "🔌 API Gateway",
    "👥 Usuarios IAM",
    "🗺️ Multi-región",
    "🔄 Virginia ↔ Ohio",
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
    
    # Botones de control del caché
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh", use_container_width=True, help="Fuerza actualización de datos"):
            st.cache_data.clear()
            st.rerun()
    with col2:
        if st.button("🗑️ Limpiar caché", use_container_width=True, help="Limpia caché local"):
            cache_manager.clear()
            st.success("Caché limpiado")
    
    st.markdown("---")
    st.markdown("<small style='color:#3a3e52'>Última actualización</small>", unsafe_allow_html=True)
    st.markdown(f"<small style='font-family:IBM Plex Mono;color:#5a5e72'>{datetime.now().strftime('%Y-%m-%d %H:%M')}</small>", unsafe_allow_html=True)
    if MODO_DEMO:
        st.markdown("<br><small style='color:#d4a017'>⚠ Modo demo — datos de ejemplo</small>", unsafe_allow_html=True)

# ─── Cargar identidad (si no es demo) ───
if not MODO_DEMO:
    identity = get_identity()
else:
    identity = {
        "account_id": "DEMO-123456789012",
        "account_name": "DEMO-ACCOUNT",
        "arn": "arn:aws:iam::123456789012:user/demo",
        "region": "us-east-1"
    }

# ─── Opciones estáticas (sin llamadas a AWS) ─────────────────────────────────────
OPCIONES_CUENTA_REGION_STATIC = [
    ("afex-des",     "us-east-1", "afex-des - us-east-1 Virginia"),
    ("afex-prod",    "us-east-1", "afex-prod - us-east-1 Virginia"),
    ("afex-prod",    "us-east-2", "afex-prod - us-east-2 Ohio"),
    ("afex-peru",    "us-east-1", "afex-peru - us-east-1 Virginia"),
    ("afex-digital", "us-east-1", "afex-digital - us-east-1 Virginia"),
]

# ─── Helper: Context Bar ─────────────────────────────────────────────────────────
def mostrar_contexto():
    """Muestra barra de contexto con cuenta, región y usuario."""
    nombre_cuenta = identity.get('account_name', '')
    label_cuenta = f"{nombre_cuenta} ({identity['account_id']})" if nombre_cuenta else identity['account_id']
    st.markdown(f"""
    <div class="ctx-box">
        <strong>Cuenta:</strong> {label_cuenta} &nbsp;·&nbsp;
        <strong>Región:</strong> {identity['region']} &nbsp;·&nbsp;
        <strong>Usuario:</strong> {identity['arn'].split('/')[-1] if '/' in identity['arn'] else identity['arn']}
    </div>
    """, unsafe_allow_html=True)

def mostrar_cache_status():
    """Muestra estado del caché local."""
    status = get_cache_status()
    stats = status['stats']
    metadata = status['metadata']
    
    st.markdown('<p class="seccion-titulo">📁 Estado del caché local</p>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Archivos en caché", f"{stats['total_files']}")
    with col2:
        st.metric("Tamaño total", f"{stats['total_size_mb']} MB")
    with col3:
        st.metric("Ubicación", "~/.cache/aws_inventory")
    
    # Detalles por servicio
    if metadata:
        st.markdown('<p class="seccion-titulo">📊 Detalles por servicio</p>', unsafe_allow_html=True)
        
        # Crear DataFrame con los datos
        detalles = []
        for key, info in metadata.items():
            ts = info.get('timestamp', '—')
            size = info.get('size_bytes', 0)
            
            # Determinar si está fresco
            from datetime import datetime, timedelta
            try:
                last_update = datetime.fromisoformat(ts)
                is_fresh = (datetime.now() - last_update) < timedelta(days=1)
                status = "✅ Fresco" if is_fresh else "⏱️ Antiguo"
            except:
                status = "❌ Error"
            
            fecha = ts.split('T')[0] if 'T' in ts else ts
            
            detalles.append({
                'Servicio': key.replace('_df', '').upper(),
                'Estado': status,
                'Actualizado': fecha,
                'Tamaño (KB)': round(size/1024, 1)
            })
        
        df_detalles = pd.DataFrame(detalles)
        
        with st.expander("🔄 Cache de servicios", expanded=True):
            st.dataframe(df_detalles, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 0 — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

if seccion == "📊 Dashboard":
    st.markdown('<p class="header-titulo">Dashboard</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">Estado general del inventario y cambios detectados</p>', unsafe_allow_html=True)
    st.markdown("")
    
    # Selector de vista
    col_vista1, col_vista2 = st.columns([3, 1])
    with col_vista1:
        vista_seleccionada = st.radio(
            "Vista:",
            ["🌍 Todas las cuentas", "📌 Cuenta actual"],
            horizontal=True,
            label_visibility="collapsed"
        )
    
    with col_vista2:
        # Botón de exportación (independiente, solo cuando hace click)
        st.markdown("")
        st.markdown("")
        if st.button("📥 Exportar CSV"):
            with st.spinner("Recopilando datos..."):
                inventario_df = obtener_inventario_completo()
                if not inventario_df.empty:
                    csv = inventario_df.to_csv(index=False)
                    st.download_button(
                        label="✅ Descargar CSV",
                        data=csv,
                        file_name="inventario_completo.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("Sin datos para exportar")
    
    # ─── VISTA 1: TODAS LAS CUENTAS ───
    if vista_seleccionada == "🌍 Todas las cuentas":
        st.markdown('<p class="seccion-titulo">Resumen global - 4 cuentas AWS</p>', unsafe_allow_html=True)
        
        try:
            # Listas de perfiles
            PERFILES_MULTI = ["afex-des", "afex-prod", "afex-peru", "afex-digital"]
            
            # Agregadores
            total_ec2 = 0
            total_ec2_running = 0
            total_rds = 0
            total_lambda = 0
            total_vpc = 0
            total_s3 = 0
            
            cuentas_info = []
            
            # SOLO caché local - SIN AWS (instantáneo)
            datos_encontrados = 0
            for perfil in PERFILES_MULTI:
                try:
                    cache_key = f"resumen_{perfil}"
                    cached_data, is_fresh, _ = cache_manager.get(cache_key)
                    
                    if cached_data:  # Si hay algo en caché, usarlo
                        res = cached_data
                        datos_encontrados += 1
                    else:
                        continue  # Sin caché = saltarlo, no llamar a AWS
                    
                    ec2_t = res.get("ec2_total", 0)
                    ec2_r = res.get("ec2_running", 0)
                    rds_t = res.get("rds_total", 0)
                    lam_t = res.get("lambda_total", 0)
                    vpc_t = res.get("vpc_total", 0)
                    s3_t = res.get("s3_total", 0)
                    
                    total_ec2 += ec2_t
                    total_ec2_running += ec2_r
                    total_rds += rds_t
                    total_lambda += lam_t
                    total_vpc += vpc_t
                    total_s3 += s3_t
                    
                    cuentas_info.append({
                        "cuenta": perfil,
                        "ec2": ec2_t,
                        "rds": rds_t,
                        "lambda": lam_t,
                        "vpc": vpc_t,
                        "s3": s3_t
                    })
                except:
                    pass
            
            # Si no hay datos en caché, mostrar aviso
            if datos_encontrados == 0:
                st.info("📦 No hay datos cacheados. Haz click en 🔄 **Refresh** (en la barra lateral) para cargar desde AWS (esto puede tomar ~60s)")
            else:
                # Mostrar resumen agregado en grande
                st.markdown('<p class="seccion-titulo">📊 Totales agregados</p>', unsafe_allow_html=True)
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                
                with col1:
                    st.metric("EC2 Total", total_ec2, delta=f"{total_ec2_running} en ejecución")
                with col2:
                    st.metric("BD RDS", total_rds)
                with col3:
                    st.metric("Lambda", total_lambda)
                with col4:
                    st.metric("VPCs", total_vpc)
                with col5:
                    st.metric("S3", total_s3)
                with col6:
                    st.metric("Cuentas", len(cuentas_info))
                
                st.markdown("")
                
                # Tabla de detalles por cuenta
                st.markdown('<p class="seccion-titulo">Desglose por cuenta</p>', unsafe_allow_html=True)
                
                df_cuentas = pd.DataFrame(cuentas_info)
                if not df_cuentas.empty:
                    st.dataframe(
                        df_cuentas.rename(columns={
                            "cuenta": "Cuenta",
                            "ec2": "EC2",
                            "rds": "RDS",
                            "lambda": "Lambda",
                            "vpc": "VPCs",
                            "s3": "S3"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                
                st.markdown("")
                
                # Gráfico comparativo
                st.markdown('<p class="seccion-titulo">Comparación entre cuentas</p>', unsafe_allow_html=True)
                
                if not df_cuentas.empty:
                    df_graf = df_cuentas.set_index("cuenta")[["ec2", "rds", "lambda", "vpc"]].reset_index()
                    df_melt = df_graf.melt(id_vars="cuenta", var_name="Servicio", value_name="Cantidad")
                    
                    fig = px.bar(
                        df_melt,
                        x="cuenta",
                        y="Cantidad",
                        color="Servicio",
                        barmode="group",
                        color_discrete_sequence=["#7fb8f0", "#a09ee0", "#d4a017", "#3ecf8e"],
                        labels={"cuenta": "Cuenta", "Cantidad": "Recursos"}
                    )
                    
                    fig.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#c8ccd4",
                        height=350,
                        xaxis=dict(gridcolor="#1a1d27"),
                        yaxis=dict(gridcolor="#1a1d27"),
                        margin=dict(l=0, r=0, t=10, b=0),
                    )
                    st.plotly_chart(fig, use_container_width=True)
        
        except Exception as e:
            st.error(f"Error cargando datos: {e}")
        
        # Alertas para "Todas las cuentas"
        st.markdown("")
        st.markdown('<p class="seccion-titulo">🚨 Alertas activas</p>', unsafe_allow_html=True)
        
        try:
            alertas = get_alertas()
            
            if not alertas:
                st.success("✅ Sin alertas críticas")
            else:
                alertas_criticas = [a for a in alertas if a.get("severidad") == "CRÍTICA"]
                alertas_aviso = [a for a in alertas if a.get("severidad") == "AVISO"]
                alertas_info = [a for a in alertas if a.get("severidad") == "INFO"]
                
                if alertas_criticas:
                    st.markdown("<h4>🔴 Críticas</h4>", unsafe_allow_html=True)
                    for alerta in alertas_criticas:
                        st.markdown(f"""
                        <div class="alerta-critica">
                            <strong>{alerta['componente']}</strong> — {alerta['mensaje']}<br>
                            <span style="color:#5a5e72;font-size:0.8rem">{alerta['tiempo']}</span>
                        </div>""", unsafe_allow_html=True)
                
                if alertas_aviso:
                    st.markdown("<h4>🟡 Avisos</h4>", unsafe_allow_html=True)
                    for alerta in alertas_aviso:
                        st.markdown(f"""
                        <div class="alerta-aviso">
                            <strong>{alerta['componente']}</strong> — {alerta['mensaje']}<br>
                            <span style="color:#5a5e72;font-size:0.8rem">{alerta['tiempo']}</span>
                        </div>""", unsafe_allow_html=True)
                
                if alertas_info:
                    st.markdown("<h4>ℹ️ Información</h4>", unsafe_allow_html=True)
                    for alerta in alertas_info:
                        st.markdown(f"""
                        <div class="alerta-info">
                            <strong>{alerta['componente']}</strong> — {alerta['mensaje']}<br>
                            <span style="color:#5a5e72;font-size:0.8rem">{alerta['tiempo']}</span>
                        </div>""", unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"Error cargando alertas: {e}")
    
    # ─── VISTA 2: CUENTA ACTUAL ───
    else:
        # Selectbox ESTÁTICO - sin llamadas a AWS (instantáneo)
        opciones_dict = {label: (perfil, region) for perfil, region, label in OPCIONES_CUENTA_REGION_STATIC}
        sel = st.selectbox("Selecciona Cuenta / Región", list(opciones_dict.keys()), key="cta_dashboard")
        perfil_activo, region_activa = opciones_dict[sel]
        
        st.markdown("")
        
        # Contexto del perfil y región (caché esto también)
        d   = get_identity_perfil_cached(perfil_activo)
        nom = d.get("account_name", perfil_activo)
        lbl = f"{nom} ({d['account_id']})" if d.get("account_id","—") != "—" else nom
        usr = d["arn"].split("/")[-1] if "/" in d.get("arn","") else d.get("arn","—")
        
        REGIONES_NOMBRES_APP = {
            "us-east-1": "us-east-1 Virginia",
            "us-east-2": "us-east-2 Ohio",
            "us-west-1": "us-west-1 California",
            "us-west-2": "us-west-2 Oregon",
            "sa-east-1": "sa-east-1 São Paulo",
        }
        region_nombre = REGIONES_NOMBRES_APP.get(region_activa, region_activa)
        st.markdown(f'''<div class="ctx-box"><strong>Cuenta:</strong> {lbl} &nbsp;·&nbsp;
            <strong>Región:</strong> {region_nombre} &nbsp;·&nbsp;
            <strong>Usuario:</strong> {usr}</div>''', unsafe_allow_html=True)
        
        st.markdown("")
        
        st.markdown('<p class="seccion-titulo">📊 Resumen de infraestructura</p>', unsafe_allow_html=True)
        
        try:
            # Estrategia: Intentar caché local PRIMERO (sin AWS)
            cache_key = f"resumen_region_{perfil_activo}_{region_activa}"
            cached_data, is_fresh, _ = cache_manager.get(cache_key)
            
            if cached_data:
                # Usar caché local si existe
                resumen = cached_data
            else:
                # Si no hay caché, cargar de AWS
                resumen = get_resumen_region(perfil_activo, region_activa)
                # Guardar en caché local
                cache_manager.set(cache_key, resumen)
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("Instancias EC2", resumen.get("ec2_total", 0))
            with col2:
                st.metric("En ejecución", resumen.get("ec2_running", 0))
            with col3:
                st.metric("BD RDS", resumen.get("rds_total", 0))
            with col4:
                st.metric("Funciones Lambda", resumen.get("lambda_total", 0))
            with col5:
                st.metric("VPCs", resumen.get("vpc_total", 0))
        except Exception as e:
            st.error(f"Error cargando resumen: {e}")
        
        # Alertas para "Cuenta actual"
        st.markdown("")
        st.markdown('<p class="seccion-titulo">🚨 Alertas activas</p>', unsafe_allow_html=True)
        
        try:
            alertas = get_alertas()
            
            if not alertas:
                st.success("✅ Sin alertas críticas")
            else:
                alertas_criticas = [a for a in alertas if a.get("severidad") == "CRÍTICA"]
                alertas_aviso = [a for a in alertas if a.get("severidad") == "AVISO"]
                alertas_info = [a for a in alertas if a.get("severidad") == "INFO"]
                
                if alertas_criticas:
                    st.markdown("<h4>🔴 Críticas</h4>", unsafe_allow_html=True)
                    for alerta in alertas_criticas:
                        st.markdown(f"""
                        <div class="alerta-critica">
                            <strong>{alerta['componente']}</strong> — {alerta['mensaje']}<br>
                            <span style="color:#5a5e72;font-size:0.8rem">{alerta['tiempo']}</span>
                        </div>""", unsafe_allow_html=True)
                
                if alertas_aviso:
                    st.markdown("<h4>🟡 Avisos</h4>", unsafe_allow_html=True)
                    for alerta in alertas_aviso:
                        st.markdown(f"""
                        <div class="alerta-aviso">
                            <strong>{alerta['componente']}</strong> — {alerta['mensaje']}<br>
                            <span style="color:#5a5e72;font-size:0.8rem">{alerta['tiempo']}</span>
                        </div>""", unsafe_allow_html=True)
                
                if alertas_info:
                    st.markdown("<h4>ℹ️ Información</h4>", unsafe_allow_html=True)
                    for alerta in alertas_info:
                        st.markdown(f"""
                        <div class="alerta-info">
                            <strong>{alerta['componente']}</strong> — {alerta['mensaje']}<br>
                            <span style="color:#5a5e72;font-size:0.8rem">{alerta['tiempo']}</span>
                        </div>""", unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"Error cargando alertas: {e}")
    
    st.markdown("")
    
    # Estado del caché (siempre mostrar)
    mostrar_cache_status()
    
    st.markdown("")
    st.markdown('<p class="seccion-titulo">💡 Información de caché</p>', unsafe_allow_html=True)
    
    info_col1, info_col2 = st.columns(2)
    
    with info_col1:
        st.markdown("""
        **¿Cómo funciona el caché?**
        
        - Los datos se guardan localmente en `~/.cache/aws_inventory/`
        - Se actualizan automáticamente cada **1 día**
        - Si detecta cambios, se muestra un indicador verde en el Dashboard
        - Puedes hacer refresh forzado con el botón 🔄 en el sidebar
        """)
    
    with info_col2:
        st.markdown("""
        **Beneficios:**
        
        ✅ Carga más rápida (sin esperar a AWS)
        ✅ Funciona sin conexión a AWS
        ✅ Detecta cambios automáticamente
        ✅ Ahorra tiempo y requests a AWS
        ✅ Historial de cambios
        """)

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1 — INFRAESTRUCTURA AWS
# ═══════════════════════════════════════════════════════════════════════════════

elif seccion == "📈 Infraestructura AWS":
    st.markdown('<p class="header-titulo">Infraestructura AWS</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">EC2 · RDS · Lambda · VPC · API Gateway</p>', unsafe_allow_html=True)
    st.markdown("")
    
    # Selector ESTÁTICO (sin llamadas a AWS)
    opciones_dict = {label: (perfil, region) for perfil, region, label in OPCIONES_CUENTA_REGION_STATIC}
    sel = st.selectbox("Cuenta / Región", list(opciones_dict.keys()), key="cta_infra")
    perfil_activo, region_activa = opciones_dict[sel]
    
    st.markdown("")
    
    # Contexto del perfil y región
    REGIONES_NOMBRES_APP = {
        "us-east-1": "us-east-1 Virginia",
        "us-east-2": "us-east-2 Ohio",
        "us-west-1": "us-west-1 California",
        "us-west-2": "us-west-2 Oregon",
        "sa-east-1": "sa-east-1 São Paulo",
    }
    d   = get_identity_perfil_cached(perfil_activo)
    nom = d.get("account_name", perfil_activo)
    lbl = f"{nom} ({d['account_id']})" if d.get("account_id","—") != "—" else nom
    usr = d["arn"].split("/")[-1] if "/" in d.get("arn","") else d.get("arn","—")
    region_nombre = REGIONES_NOMBRES_APP.get(region_activa, region_activa)
    st.markdown(f'''<div class="ctx-box"><strong>Cuenta:</strong> {lbl} &nbsp;·&nbsp;
        <strong>Región:</strong> {region_nombre} &nbsp;·&nbsp;
        <strong>Usuario:</strong> {usr}</div>''', unsafe_allow_html=True)
    
    # Cargar datos con caché local primero (sin AWS)
    def _cargar_df_con_cache(perfil, region, tipo):
        """Intenta caché local primero, si no existe carga de AWS"""
        cache_key = f"df_{tipo}_{perfil}_{region}"
        cached_data, _, _ = cache_manager.get(cache_key)
        
        if cached_data is not None:
            return cached_data  # Del caché local
        else:
            # Si no hay caché, cargar de AWS
            df = _df_region(perfil, region, tipo)
            # Guardar en caché
            try:
                cache_manager.set(cache_key, df)
            except:
                pass
            return df
    
    try:
        ec2_df    = _cargar_df_con_cache(perfil_activo, region_activa, "ec2")
        rds_df    = _cargar_df_con_cache(perfil_activo, region_activa, "rds")
        lambda_df = _cargar_df_con_cache(perfil_activo, region_activa, "lambda")
        vpc_df    = _cargar_df_con_cache(perfil_activo, region_activa, "vpc")
    except:
        ec2_df = pd.DataFrame()
        rds_df = pd.DataFrame()
        lambda_df = pd.DataFrame()
        vpc_df = pd.DataFrame()
    
    st.markdown("")
    
    # EC2
    st.markdown('<p class="seccion-titulo">🖥️ Instancias EC2</p>', unsafe_allow_html=True)
    try:
        if not ec2_df.empty:
            st.dataframe(ec2_df, use_container_width=True, hide_index=True)
        else:
            st.info("Sin instancias EC2 en esta región")
    except Exception as e:
        st.error(f"Error: {e}")
    
    st.markdown("")
    
    # RDS
    st.markdown('<p class="seccion-titulo">🗄️ Bases de datos RDS</p>', unsafe_allow_html=True)
    try:
        if not rds_df.empty:
            st.dataframe(rds_df, use_container_width=True, hide_index=True)
        else:
            st.info("Sin bases de datos RDS en esta región")
    except Exception as e:
        st.error(f"Error: {e}")
    
    st.markdown("")
    
    # Lambda
    st.markdown('<p class="seccion-titulo">⚡ Funciones Lambda</p>', unsafe_allow_html=True)
    try:
        if not lambda_df.empty:
            st.dataframe(lambda_df[["nombre","runtime","estado","memoria_mb"]] if "memoria_mb" in lambda_df.columns else lambda_df, use_container_width=True, hide_index=True)
        else:
            st.info("Sin funciones Lambda en esta región")
    except Exception as e:
        st.error(f"Error: {e}")
    
    st.markdown("")
    
    # VPC
    st.markdown('<p class="seccion-titulo">🌐 Virtual Private Clouds</p>', unsafe_allow_html=True)
    try:
        if not vpc_df.empty:
            st.dataframe(vpc_df, use_container_width=True, hide_index=True)
        else:
            st.info("Sin VPCs en esta región")
    except Exception as e:
        st.error(f"Error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2 — S3
# ═══════════════════════════════════════════════════════════════════════════════

elif seccion == "🪣 S3 — Buckets":
    st.markdown('<p class="header-titulo">S3 Buckets</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">Almacenamiento en S3</p>', unsafe_allow_html=True)
    st.markdown("")
    
    # Selector ESTÁTICO (sin llamadas a AWS)
    opciones_dict = {label: (perfil, region) for perfil, region, label in OPCIONES_CUENTA_REGION_STATIC}
    col1, col2 = st.columns([4, 1])
    
    with col1:
        sel = st.selectbox("Selecciona Cuenta / Región", list(opciones_dict.keys()), key="cta_s3")
    
    perfil_activo, region_activa = opciones_dict[sel]
    
    # Detectar cambio en selector y forzar rerun
    if "s3_perfil_anterior" not in st.session_state:
        st.session_state.s3_perfil_anterior = perfil_activo
    
    if st.session_state.s3_perfil_anterior != perfil_activo:
        st.session_state.s3_perfil_anterior = perfil_activo
        st.rerun()
    
    st.markdown("")
    
    # Contexto del perfil y región
    REGIONES_NOMBRES_APP = {
        "us-east-1": "us-east-1 Virginia",
        "us-east-2": "us-east-2 Ohio",
        "us-west-1": "us-west-1 California",
        "us-west-2": "us-west-2 Oregon",
        "sa-east-1": "sa-east-1 São Paulo",
    }
    d   = get_identity_perfil_cached(perfil_activo)
    nom = d.get("account_name", perfil_activo)
    lbl = f"{nom} ({d['account_id']})" if d.get("account_id","—") != "—" else nom
    usr = d["arn"].split("/")[-1] if "/" in d.get("arn","") else d.get("arn","—")
    region_nombre = REGIONES_NOMBRES_APP.get(region_activa, region_activa)
    st.markdown(f'''<div class="ctx-box"><strong>Cuenta:</strong> {lbl} &nbsp;·&nbsp;
        <strong>Región:</strong> {region_nombre} &nbsp;·&nbsp;
        <strong>Usuario:</strong> {usr}</div>''', unsafe_allow_html=True)
    
    st.markdown('<p class="seccion-titulo">🪣 Buckets</p>', unsafe_allow_html=True)
    
    # Mostrar indicador de carga
    with st.status("🔄 Cargando buckets S3...", expanded=True) as status:
        try:
            s3_df = get_s3_df(perfil_activo)
            status.update(label="✅ Buckets cargados", state="complete")
            
            if not s3_df.empty:
                # Agregar columna de privacidad
                def determinar_privacidad(nombre):
                    if 'public' in nombre.lower():
                        return '🔓 Público'
                    elif 'sandbox' in nombre.lower() or 'test' in nombre.lower():
                        return '🟡 Semi-público'
                    else:
                        return '🔒 Privado'
                
                s3_df['privacidad'] = s3_df['nombre'].apply(determinar_privacidad)
                
                # Reordenar columnas
                cols = list(s3_df.columns)
                if 'privacidad' in cols:
                    cols.remove('privacidad')
                    cols.insert(1, 'privacidad')
                    s3_df = s3_df[cols]
                
                st.dataframe(s3_df, use_container_width=True, hide_index=True)
            else:
                st.info("Sin buckets S3")
        except Exception as e:
            status.update(label="❌ Error al cargar", state="error")
            st.error(f"Error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3 — LAMBDA
# ═══════════════════════════════════════════════════════════════════════════════

elif seccion == "⚡ Lambda":
    st.markdown('<p class="header-titulo">AWS Lambda</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">Funciones Lambda y replicación entre regiones</p>', unsafe_allow_html=True)
    st.markdown("")
    
    # Tabs para dos vistas
    tab1 = st.tabs(["📋 Lambda por región"])[0]
    
    with tab1:
        st.markdown("")
        # Selector ESTÁTICO
        opciones_dict = {label: (perfil, region) for perfil, region, label in OPCIONES_CUENTA_REGION_STATIC}
        col1, col2 = st.columns([4, 1])
        
        with col1:
            sel = st.selectbox("Selecciona Cuenta / Región", list(opciones_dict.keys()), key="cta_lambda")
        
        perfil_activo, region_activa = opciones_dict[sel]
        
        # Detectar cambio en selector y forzar rerun
        if "lambda_perfil_anterior" not in st.session_state:
            st.session_state.lambda_perfil_anterior = perfil_activo
        
        if st.session_state.lambda_perfil_anterior != perfil_activo:
            st.session_state.lambda_perfil_anterior = perfil_activo
            st.rerun()
        
        st.markdown("")
        
        # Contexto
        REGIONES_NOMBRES_APP = {
            "us-east-1": "us-east-1 Virginia",
            "us-east-2": "us-east-2 Ohio",
            "us-west-1": "us-west-1 California",
            "us-west-2": "us-west-2 Oregon",
            "sa-east-1": "sa-east-1 São Paulo",
        }
        d   = get_identity_perfil_cached(perfil_activo)
        nom = d.get("account_name", perfil_activo)
        lbl = f"{nom} ({d['account_id']})" if d.get("account_id","—") != "—" else nom
        usr = d["arn"].split("/")[-1] if "/" in d.get("arn","") else d.get("arn","—")
        region_nombre = REGIONES_NOMBRES_APP.get(region_activa, region_activa)
        st.markdown(f'''<div class="ctx-box"><strong>Cuenta:</strong> {lbl} &nbsp;·&nbsp;
            <strong>Región:</strong> {region_nombre} &nbsp;·&nbsp;
            <strong>Usuario:</strong> {usr}</div>''', unsafe_allow_html=True)
        
        st.markdown('<p class="seccion-titulo">⚡ Funciones Lambda</p>', unsafe_allow_html=True)
        
        # Mostrar indicador de carga
        with st.status("🔄 Cargando funciones Lambda...", expanded=True) as status:
            try:
                lambda_df = get_lambda_df(perfil_activo, region_activa)
                status.update(label="✅ Lambda cargadas", state="complete")
                
                if not lambda_df.empty:
                    # Métricas rápidas
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total", len(lambda_df))
                    with col2:
                        cert = len(lambda_df[lambda_df["label"] == "🟢 CERT"])
                        st.metric("CERT", cert)
                    with col3:
                        prod = len(lambda_df[lambda_df["label"] == "🔵 PROD"])
                        st.metric("PROD", prod)
                    with col4:
                        sin = len(lambda_df[lambda_df["label"] == "⚪ SIN LABEL"])
                        st.metric("Sin label", sin)
                    
                    st.markdown("")
                    
                    # Tabla
                    st.dataframe(
                        lambda_df[[
                            "nombre", "label", "versión", "runtime", "memoria", 
                            "timeout", "api", "última_actualización", "estado"
                        ]].rename(columns={
                            "nombre": "Nombre Lambda",
                            "label": "Etiqueta",
                            "versión": "Versión",
                            "runtime": "Runtime",
                            "memoria": "Memoria (MB)",
                            "timeout": "Timeout (s)",
                            "api": "API Gateway",
                            "última_actualización": "Actualización",
                            "estado": "Estado"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Sin funciones Lambda en esta región")
            except Exception as e:
                status.update(label="❌ Error al cargar", state="error")
                st.error(f"Error: {e}")
    
# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4 — API GATEWAY
# ═══════════════════════════════════════════════════════════════════════════════

elif seccion == "🔌 API Gateway":
    st.markdown('<p class="header-titulo">API Gateway</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">APIs REST y configuraciones</p>', unsafe_allow_html=True)
    st.markdown("")
    
    # Selector ESTÁTICO
    opciones_dict = {label: (perfil, region) for perfil, region, label in OPCIONES_CUENTA_REGION_STATIC}
    col1, col2 = st.columns([4, 1])
    
    with col1:
        sel = st.selectbox("Selecciona Cuenta / Región", list(opciones_dict.keys()), key="cta_api")
    
    perfil_activo, region_activa = opciones_dict[sel]
    
    # Detectar cambio en selector y forzar rerun
    if "api_perfil_anterior" not in st.session_state:
        st.session_state.api_perfil_anterior = perfil_activo
    
    if st.session_state.api_perfil_anterior != perfil_activo:
        st.session_state.api_perfil_anterior = perfil_activo
        st.rerun()
    
    st.markdown("")
    
    # Contexto
    REGIONES_NOMBRES_APP = {
        "us-east-1": "us-east-1 Virginia",
        "us-east-2": "us-east-2 Ohio",
        "us-west-1": "us-west-1 California",
        "us-west-2": "us-west-2 Oregon",
        "sa-east-1": "sa-east-1 São Paulo",
    }
    d   = get_identity_perfil_cached(perfil_activo)
    nom = d.get("account_name", perfil_activo)
    lbl = f"{nom} ({d['account_id']})" if d.get("account_id","—") != "—" else nom
    usr = d["arn"].split("/")[-1] if "/" in d.get("arn","") else d.get("arn","—")
    region_nombre = REGIONES_NOMBRES_APP.get(region_activa, region_activa)
    st.markdown(f'''<div class="ctx-box"><strong>Cuenta:</strong> {lbl} &nbsp;·&nbsp;
        <strong>Región:</strong> {region_nombre} &nbsp;·&nbsp;
        <strong>Usuario:</strong> {usr}</div>''', unsafe_allow_html=True)
    
    # Tabs para dos vistas
    tab1, tab2 = st.tabs(["📋 APIs REST", "🔗 Conexiones API ↔ Lambda"])
    
    with tab1:
        st.markdown('<p class="seccion-titulo">🔌 APIs REST</p>', unsafe_allow_html=True)
        
        # Mostrar indicador de carga
        with st.status("🔄 Cargando APIs...", expanded=True) as status:
            try:
                api_df = get_api_df(perfil_activo, region_activa)
                status.update(label="✅ APIs cargadas", state="complete")
                
                if not api_df.empty:
                    # Métricas rápidas
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total APIs", len(api_df))
                    with col2:
                        st.metric("Total Recursos", api_df["recursos"].sum())
                    with col3:
                        st.metric("Total Métodos", api_df["num_métodos"].sum())
                    with col4:
                        st.metric("Total Etapas", api_df["num_etapas"].sum())
                    
                    st.markdown("")
                    
                    # Tabla
                    st.dataframe(
                        api_df[[
                            "nombre", "recursos", "métodos", "etapas", "creado", "estado"
                        ]].rename(columns={
                            "nombre": "Nombre API",
                            "recursos": "Recursos",
                            "métodos": "Métodos",
                            "etapas": "Etapas",
                            "creado": "Creado",
                            "estado": "Estado"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Sin APIs REST en esta región")
            except Exception as e:
                status.update(label="❌ Error al cargar", state="error")
                st.error(f"Error: {e}")
    
    with tab2:
        st.markdown('<p class="seccion-titulo">🔗 Mapeo API ↔ Lambda</p>', unsafe_allow_html=True)
        st.markdown("Todas las APIs y sus Lambdas asociadas")
        st.markdown("")
        
        with st.status("🔄 Analizando integraciones...", expanded=True) as status:
            try:
                mapping_df = get_api_lambda_mapping(perfil_activo, region_activa)
                status.update(label="✅ Análisis completado", state="complete")
                
                if not mapping_df.empty:
                    # Métricas
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Conexiones", len(mapping_df))
                    with col2:
                        apis_unicas = mapping_df["api"].nunique()
                        st.metric("APIs", apis_unicas)
                    with col3:
                        lambdas_unicas = mapping_df["lambda"].nunique()
                        st.metric("Lambdas", lambdas_unicas)
                    with col4:
                        metodos_unicos = mapping_df["metodo"].nunique()
                        st.metric("Métodos HTTP", metodos_unicos)
                    
                    st.markdown("")
                    
                    # Crear tabla resumida limpia
                    st.markdown("### 📋 API → Lambda Mapping")
                    
                    # Agrupar por API para mostrar de forma más clara
                    apis_group = mapping_df.groupby("api").apply(
                        lambda x: pd.Series({
                            "Lambdas": ", ".join(x["lambda"].unique()),
                            "Métodos": ", ".join(x["metodo"].unique()),
                            "Rutas": ", ".join(x["ruta"].unique()),
                            "Conexiones": len(x)
                        })
                    ).reset_index()
                    
                    st.dataframe(
                        apis_group.rename(columns={
                            "api": "API Gateway",
                            "Lambdas": "🔗 Función Lambda",
                            "Métodos": "HTTP",
                            "Rutas": "Rutas/Paths",
                            "Conexiones": "Total"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    st.markdown("")
                    st.markdown("### ⚡ Lambda → API Mapping")
                    
                    # Agrupar por Lambda para mostrar qué APIs la usan
                    lambdas_group = mapping_df.groupby("lambda").apply(
                        lambda x: pd.Series({
                            "APIs": ", ".join(x["api"].unique()),
                            "Métodos": ", ".join(x["metodo"].unique()),
                            "Rutas": ", ".join(x["ruta"].unique()),
                            "Conexiones": len(x)
                        })
                    ).reset_index()
                    
                    st.dataframe(
                        lambdas_group.rename(columns={
                            "lambda": "Función Lambda",
                            "APIs": "🔗 APIs que la usan",
                            "Métodos": "HTTP",
                            "Rutas": "Rutas/Paths",
                            "Conexiones": "Total"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    st.markdown("")
                    st.markdown("### 🔍 Detalle Completo")
                    st.markdown("Cada integración API → Lambda → Ruta → Método HTTP")
                    
                    # Tabla detallada completa
                    st.dataframe(
                        mapping_df[[
                            "api", "lambda", "ruta", "metodo", "tipo_integracion", "estado"
                        ]].rename(columns={
                            "api": "API Gateway",
                            "lambda": "Función Lambda",
                            "ruta": "Ruta",
                            "metodo": "Método HTTP",
                            "tipo_integracion": "Tipo Integración",
                            "estado": "Estado"
                        }).sort_values("API Gateway"),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Sin integraciones API → Lambda detectadas en esta región")
            except Exception as e:
                status.update(label="❌ Error en análisis", state="error")
                st.error(f"Error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 5 — IAM
# ═══════════════════════════════════════════════════════════════════════════════

elif seccion == "👥 Usuarios IAM":
    st.markdown('<p class="header-titulo">Usuarios IAM</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">Gestión de identidades y acceso</p>', unsafe_allow_html=True)
    st.markdown("")
    
    # Selector ESTÁTICO (sin llamadas a AWS)
    opciones_dict = {label: (perfil, region) for perfil, region, label in OPCIONES_CUENTA_REGION_STATIC}
    col1, col2 = st.columns([4, 1])
    
    with col1:
        sel = st.selectbox("Selecciona Cuenta / Región", list(opciones_dict.keys()), key="cta_iam")
    
    perfil_activo, region_activa = opciones_dict[sel]
    
    # Detectar cambio en selector y forzar rerun
    if "iam_perfil_anterior" not in st.session_state:
        st.session_state.iam_perfil_anterior = perfil_activo
    
    if st.session_state.iam_perfil_anterior != perfil_activo:
        st.session_state.iam_perfil_anterior = perfil_activo
        st.rerun()
    
    st.markdown("")
    
    # Contexto del perfil y región
    REGIONES_NOMBRES_APP = {
        "us-east-1": "us-east-1 Virginia",
        "us-east-2": "us-east-2 Ohio",
        "us-west-1": "us-west-1 California",
        "us-west-2": "us-west-2 Oregon",
        "sa-east-1": "sa-east-1 São Paulo",
    }
    d   = get_identity_perfil_cached(perfil_activo)
    nom = d.get("account_name", perfil_activo)
    lbl = f"{nom} ({d['account_id']})" if d.get("account_id","—") != "—" else nom
    usr = d["arn"].split("/")[-1] if "/" in d.get("arn","") else d.get("arn","—")
    region_nombre = REGIONES_NOMBRES_APP.get(region_activa, region_activa)
    st.markdown(f'''<div class="ctx-box"><strong>Cuenta:</strong> {lbl} &nbsp;·&nbsp;
        <strong>Región:</strong> {region_nombre} &nbsp;·&nbsp;
        <strong>Usuario:</strong> {usr}</div>''', unsafe_allow_html=True)
    
    st.markdown('<p class="seccion-titulo">👥 Usuarios</p>', unsafe_allow_html=True)
    
    # Mostrar indicador de carga
    with st.status("🔄 Cargando usuarios IAM...", expanded=True) as status:
        try:
            users_df = get_iam_users_df(perfil_activo)
            status.update(label="✅ Usuarios cargados", state="complete")
            
            if not users_df.empty:
                st.dataframe(users_df[["nombre","tipo","estado","mfa","n_politicas","ultimo_acceso"]], use_container_width=True, hide_index=True)
            else:
                st.info("Sin usuarios IAM")
        except Exception as e:
            status.update(label="❌ Error al cargar", state="error")
            st.error(f"Error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4 — MULTI-REGIÓN
# ═══════════════════════════════════════════════════════════════════════════════

elif seccion == "🗺️ Multi-región":
    st.markdown('<p class="header-titulo">Multi-región</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">Comparación de infraestructura entre regiones</p>', unsafe_allow_html=True)
    st.markdown("")
    
    # Selector de cuenta
    OPCIONES_CUENTA_MULTI = [
        ("afex-prod", "us-east-1"),
        ("afex-prod", "us-east-2"),
    ]
    
    opciones_mr = {f"{p} - {r}": (p, r) for p, r in OPCIONES_CUENTA_MULTI}
    
    col_sel1, col_sel2 = st.columns([2, 1])
    with col_sel1:
        sel_mr = st.selectbox("Selecciona cuenta para multi-región", list(opciones_mr.keys()), key="mr_selector")
    perfil_mr, region_base = opciones_mr[sel_mr]
    
    with col_sel2:
        if st.button("🔄 Refresh datos", key="mr_refresh"):
            st.cache_data.clear()
            st.rerun()
    
    st.markdown("")
    
    # Obtener regiones de esta cuenta
    regiones_cuenta = _regiones(perfil_mr)
    
    if len(regiones_cuenta) <= 1:
        st.markdown('<p class="seccion-titulo">Estado</p>', unsafe_allow_html=True)
        st.info(f"Esta cuenta solo tiene 1 región configurada: **{regiones_cuenta[0]}**. "
                "Para agregar más regiones, edita `PERFILES` en `conector_aws.py`.")
    else:
        # Cargar datos de cada región
        datos_regiones = []
        for region in regiones_cuenta:
            try:
                res_region = get_resumen_region(perfil_mr, region)
                datos_regiones.append(res_region)
            except:
                datos_regiones.append({"_error": f"No se pudo cargar {region}"})
        
        # Tarjetas por región
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
                                letter-spacing:0.08em;margin-bottom:6px">{dr.get('region_nombre', dr.get('region', 'N/A'))}</div>
                    <div style="font-size:0.72rem;color:{'#e05252' if error else '#5a5e72'};margin-top:4px">
                        {'❌ ' + dr.get('_error','Error')[:40] if error else '✅ Conectado'}
                    </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("")

        # Tabla comparativa
        st.markdown('<p class="seccion-titulo">Comparación de componentes entre regiones</p>', unsafe_allow_html=True)

        componentes = ["EC2 (total)", "EC2 (running)", "RDS", "Aurora", "Lambda", "DynamoDB", "VPC", "Subnets"]
        keys        = ["ec2_total", "ec2_running", "rds_total", "aurora_total",
                       "lambda_total", "dynamo_total", "vpc_total", "subnet_total"]

        filas = []
        for comp, key in zip(componentes, keys):
            fila = {"Componente": comp}
            for dr in datos_regiones:
                region_nombre = dr.get('region_nombre', dr.get('region', 'N/A'))
                fila[region_nombre] = dr.get(key, 0)
            filas.append(fila)

        df_mr = pd.DataFrame(filas)

        # Columna diferencia si hay exactamente 2 regiones
        if len(datos_regiones) == 2:
            r1 = datos_regiones[0].get('region_nombre', datos_regiones[0].get('region', 'Región 1'))
            r2 = datos_regiones[1].get('region_nombre', datos_regiones[1].get('region', 'Región 2'))
            df_mr["Diferencia"] = df_mr.apply(
                lambda row: "✅ Igual" if row.get(r1, 0) == row.get(r2, 0)
                            else f"⚠️ {abs(row.get(r1, 0) - row.get(r2, 0))} diferencia",
                axis=1
            )

        st.dataframe(df_mr, use_container_width=True, hide_index=True)

        st.markdown("")

        # Gráfico comparativo
        st.markdown('<p class="seccion-titulo">Distribución gráfica por región</p>', unsafe_allow_html=True)
        nombres_regiones = [dr.get('region_nombre', dr.get('region', 'N/A')) for dr in datos_regiones]
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

        # Alertas de diferencia
        if len(datos_regiones) == 2 and "Diferencia" in df_mr.columns:
            difs = df_mr[df_mr["Diferencia"].str.contains("⚠️", na=False)]
            if not difs.empty:
                st.markdown('<p class="seccion-titulo">⚠️ Diferencias entre regiones</p>', unsafe_allow_html=True)
                for _, row in difs.iterrows():
                    st.markdown(f"""
                    <div class="alerta-aviso">
                        <strong>{row["Componente"]}</strong> — {row["Diferencia"]}<br>
                        <span style="color:#5a5e72;font-size:0.8rem">
                        {r1}: {row.get(r1, 0)} &nbsp;·&nbsp; {r2}: {row.get(r2, 0)}
                        </span>
                    </div>""", unsafe_allow_html=True)
            else:
                st.success("✅ Ambas regiones tienen la misma cantidad de componentes.")

        st.markdown("")
        st.info("Para agregar más regiones a una cuenta: edita la lista `regiones` en `PERFILES` dentro de `conector_aws.py`.")

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN — VIRGINIA ↔ OHIO
# ═══════════════════════════════════════════════════════════════════════════════

elif seccion == "🔄 Virginia ↔ Ohio":
    st.header("🔄 Virginia ↔ Ohio")
    st.subheader("Datos lado a lado para análisis manual")
    
    st.markdown("""
    <div class="ctx-box">
    <strong>Cuenta:</strong> afex-prod (596294895478) · 
    <strong>Región 1:</strong> us-east-1 Virginia · 
    <strong>Región 2:</strong> us-east-2 Ohio
    </div>
    """, unsafe_allow_html=True)
    
    # Tabs para API y Lambda
    tab1, tab2 = st.tabs(["🔌 API REST", "⚡ Lambda"])
    
    # ─── TAB 1: API REST ──────────────────────────────────────────────────────
    with tab1:
        st.markdown("##### 🔌 APIs REST - Virginia vs Ohio")
        
        try:
            # Obtener datos
            df_api_va = get_api_df(perfil="afex-prod", region="us-east-1")
            df_api_oh = get_api_df(perfil="afex-prod", region="us-east-2")
            
            if df_api_va is None or df_api_va.empty:
                df_api_va = pd.DataFrame({'nombre': [], 'recursos': [], 'metodos': [], 'etapas': []})
            if df_api_oh is None or df_api_oh.empty:
                df_api_oh = pd.DataFrame({'nombre': [], 'recursos': [], 'metodos': [], 'etapas': []})
            
            # Preparar columnas a mostrar
            cols_mostrar = ['nombre']
            for col in ['recursos', 'metodos', 'etapas', 'estado']:
                if col in df_api_va.columns or col in df_api_oh.columns:
                    cols_mostrar.append(col)
            
            # Crear tabla lado a lado
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Virginia (us-east-1)**")
                df_va_display = df_api_va[cols_mostrar] if len(cols_mostrar) > 0 else df_api_va
                st.dataframe(df_va_display, use_container_width=True, hide_index=True, height=400)
            
            with col2:
                st.markdown("**Ohio (us-east-2)**")
                df_oh_display = df_api_oh[cols_mostrar] if len(cols_mostrar) > 0 else df_api_oh
                st.dataframe(df_oh_display, use_container_width=True, hide_index=True, height=400)
            
            # Botones de descarga
            st.markdown("**Descargar:**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_va = df_api_va.to_csv(index=False)
                st.download_button(
                    label="📥 Virginia (CSV)",
                    data=csv_va,
                    file_name="api_virginia.csv",
                    mime="text/csv"
                )
            
            with col2:
                csv_oh = df_api_oh.to_csv(index=False)
                st.download_button(
                    label="📥 Ohio (CSV)",
                    data=csv_oh,
                    file_name="api_ohio.csv",
                    mime="text/csv"
                )
            
            with col3:
                df_api_va['region'] = 'Virginia'
                df_api_oh['region'] = 'Ohio'
                df_combined = pd.concat([df_api_va, df_api_oh], ignore_index=True)
                csv_combined = df_combined.to_csv(index=False)
                st.download_button(
                    label="📥 Combinado (CSV)",
                    data=csv_combined,
                    file_name="api_combinado.csv",
                    mime="text/csv"
                )
            
            # Estadísticas
            st.markdown("**Estadísticas:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("APIs Virginia", len(df_api_va))
            with col2:
                st.metric("APIs Ohio", len(df_api_oh))
            with col3:
                st.metric("Diferencia", abs(len(df_api_va) - len(df_api_oh)))
        
        except Exception as e:
            st.error(f"Error: {str(e)}")
    
    # ─── TAB 2: LAMBDA ────────────────────────────────────────────────────────
    with tab2:
        st.markdown("##### ⚡ Funciones Lambda - Virginia vs Ohio")
        
        try:
            df_lambda_va = get_lambda_df(perfil="afex-prod", region="us-east-1")
            df_lambda_oh = get_lambda_df(perfil="afex-prod", region="us-east-2")
            
            if df_lambda_va is None or df_lambda_va.empty:
                df_lambda_va = pd.DataFrame()
            if df_lambda_oh is None or df_lambda_oh.empty:
                df_lambda_oh = pd.DataFrame()
            
            if len(df_lambda_va) > 0 and len(df_lambda_oh) > 0:
                cols_mostrar = ['nombre', 'runtime', 'memoria', 'timeout']
                cols_mostrar = [c for c in cols_mostrar if c in df_lambda_va.columns or c in df_lambda_oh.columns]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Virginia (us-east-1)**")
                    df_va_display = df_lambda_va[cols_mostrar] if len(cols_mostrar) > 0 else df_lambda_va
                    st.dataframe(df_va_display, use_container_width=True, hide_index=True, height=400)
                
                with col2:
                    st.markdown("**Ohio (us-east-2)**")
                    df_oh_display = df_lambda_oh[cols_mostrar] if len(cols_mostrar) > 0 else df_lambda_oh
                    st.dataframe(df_oh_display, use_container_width=True, hide_index=True, height=400)
                
                st.markdown("**Descargar:**")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    csv_va = df_lambda_va.to_csv(index=False)
                    st.download_button(
                        label="📥 Virginia (CSV)",
                        data=csv_va,
                        file_name="lambda_virginia.csv",
                        mime="text/csv"
                    )
                
                with col2:
                    csv_oh = df_lambda_oh.to_csv(index=False)
                    st.download_button(
                        label="📥 Ohio (CSV)",
                        data=csv_oh,
                        file_name="lambda_ohio.csv",
                        mime="text/csv"
                    )
                
                with col3:
                    df_lambda_va['region'] = 'Virginia'
                    df_lambda_oh['region'] = 'Ohio'
                    df_combined = pd.concat([df_lambda_va, df_lambda_oh], ignore_index=True)
                    csv_combined = df_combined.to_csv(index=False)
                    st.download_button(
                        label="📥 Combinado (CSV)",
                        data=csv_combined,
                        file_name="lambda_combinado.csv",
                        mime="text/csv"
                    )
                
                st.markdown("**Estadísticas:**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Lambda Virginia", len(df_lambda_va))
                with col2:
                    st.metric("Lambda Ohio", len(df_lambda_oh))
                with col3:
                    st.metric("Diferencia", abs(len(df_lambda_va) - len(df_lambda_oh)))
            else:
                st.info("Sin datos disponibles")
        
        except Exception as e:
            st.error(f"Error: {str(e)}")

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 5 — MULTI-CUENTA
# ═══════════════════════════════════════════════════════════════════════════════

elif seccion == "🌍 Multi-cuenta":
    st.markdown('<p class="header-titulo">Multi-cuenta</p>', unsafe_allow_html=True)
    st.markdown('<p class="header-sub">Inventario real de todas las cuentas AWS configuradas</p>', unsafe_allow_html=True)
    st.markdown("")

    # Lista de 4 perfiles configurados
    PERFILES_MULTI = ["afex-des", "afex-prod", "afex-peru", "afex-digital"]

    # Cargar identidad y resumen de cada cuenta
    with st.spinner("Consultando todas las cuentas AWS..."):
        datos_cuentas = []
        for perfil in PERFILES_MULTI:
            try:
                id_cuenta  = get_identity_perfil_cached(perfil)
                res_cuenta = get_resumen_perfil(perfil)
                datos_cuentas.append({"identidad": id_cuenta, "resumen": res_cuenta})
            except:
                datos_cuentas.append({"identidad": {"account_name": perfil, "account_id": "N/A"}, "resumen": {"_error": "Error"}})

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
                            letter-spacing:0.08em;margin-bottom:4px">{idc.get('region','N/A')}</div>
                <div style="font-size:1rem;font-weight:500;color:#e8eaf0">{idc.get('account_name','N/A')}</div>
                <div style="font-size:0.72rem;color:#5a5e72;font-family:monospace;margin:3px 0">{idc.get('account_id','N/A')}</div>
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
            nombre_col = dc["identidad"].get("account_name", "N/A")
            fila[nombre_col] = dc["resumen"].get(key, 0)
        filas.append(fila)

    df_comp = pd.DataFrame(filas)

    # Detectar diferencias entre cuentas
    if len(datos_cuentas) >= 2:
        nombres = [dc["identidad"].get("account_name", "N/A") for dc in datos_cuentas]
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
            nombres_graf = [dc["identidad"].get("account_name", "N/A") for dc in datos_cuentas]
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
            st.success("✅ Todas las cuentas tienen la misma cantidad de componentes.")

    st.markdown("")
    st.info("Para agregar más cuentas: crea el perfil con 'aws configure --profile nombre' y agrégalo a PERFILES_MULTI en esta sección.")
