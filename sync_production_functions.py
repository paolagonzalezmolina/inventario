"""
sync_production_functions.py
────────────────────────────────────────────────────────────────
Funciones de comparación para la sección "✅ Sincronización Production"

Compara:
1. Lambda CERT vs PROD (mismo nombre, diferentes etiquetas)
2. API CERT vs PROD (mismo nombre)
3. EC2 Virginia vs Ohio (mismo nombre, misma configuración)
"""

import pandas as pd
from conector_aws import (
    get_lambda_df, get_api_df, get_ec2_df,
    cache_manager, PERFILES, _regiones
)

# ─── LAMBDA: Comparar CERT vs PROD ────────────────────────────────────────────

def comparar_lambda_cert_vs_prod(perfil="afex-prod"):
    """
    Compara Lambdas CERT vs PROD en el mismo perfil.
    
    Retorna:
    - lambdas_cert: Set de nombres Lambda etiquetados como CERT
    - lambdas_prod: Set de nombres Lambda etiquetados como PROD
    - solo_cert: Lambdas que están SOLO en CERT
    - solo_prod: Lambdas que están SOLO en PROD
    - ambas: Lambdas que existen en CERT y PROD
    """
    
    cache_key = f"lambda_cert_prod_compare_{perfil}"
    cached = cache_manager.get(cache_key)
    if cached and not cached[1]: return cached[0]  # Si está en caché
    
    try:
        region = PERFILES[perfil]["region"]
        df = get_lambda_df(perfil=perfil, region=region)
        
        # Filtrar por etiqueta
        cert_lambdas = set(df[df['etiqueta'].str.contains('CERT', case=False, na=False)]['nombre'].str.lower())
        prod_lambdas = set(df[df['etiqueta'].str.contains('PROD', case=False, na=False)]['nombre'].str.lower())
        
        # Comparaciones
        solo_cert = cert_lambdas - prod_lambdas
        solo_prod = prod_lambdas - cert_lambdas
        ambas = cert_lambdas & prod_lambdas
        
        resultado = {
            'cert_count': len(cert_lambdas),
            'prod_count': len(prod_lambdas),
            'solo_cert': sorted(list(solo_cert)),
            'solo_prod': sorted(list(solo_prod)),
            'ambas': sorted(list(ambas)),
            'sincronizado': len(solo_cert) == 0 and len(solo_prod) == 0,
            'porcentaje_sync': round((len(ambas) / max(len(cert_lambdas), len(prod_lambdas), 1)) * 100, 1)
        }
        
        # Guardar en caché
        cache_manager.set(cache_key, resultado)
        return resultado
        
    except Exception as e:
        return {
            'error': str(e),
            'cert_count': 0,
            'prod_count': 0,
            'solo_cert': [],
            'solo_prod': [],
            'ambas': [],
            'sincronizado': False,
            'porcentaje_sync': 0
        }

# ─── API: Comparar CERT vs PROD ───────────────────────────────────────────────

def comparar_api_cert_vs_prod(perfil="afex-prod"):
    """
    Compara APIs CERT vs PROD en el mismo perfil.
    Busca "cert" o "prod" en el nombre de la API.
    """
    
    cache_key = f"api_cert_prod_compare_{perfil}"
    cached = cache_manager.get(cache_key)
    if cached and not cached[1]: return cached[0]
    
    try:
        region = PERFILES[perfil]["region"]
        df = get_api_df(perfil=perfil, region=region)
        
        # Filtrar por nombre
        cert_apis = set(
            df[df['nombre'].str.contains('cert', case=False, na=False)]['nombre'].str.lower()
        )
        prod_apis = set(
            df[df['nombre'].str.contains('prod', case=False, na=False)]['nombre'].str.lower()
        )
        
        # Limpiar nombres para comparación (remover cert/prod del final)
        def limpiar_nombre(nombre):
            """Extrae el nombre base sin cert/prod"""
            n = nombre.lower()
            for suf in ['-cert', '-prod', '_cert', '_prod', 'cert', 'prod']:
                if n.endswith(suf):
                    return n[:-len(suf)]
            return n
        
        cert_base = {limpiar_nombre(n): n for n in cert_apis}
        prod_base = {limpiar_nombre(n): n for n in prod_apis}
        
        solo_cert = []
        solo_prod = []
        ambas = []
        
        # Encontrar desajustes
        for base_name in set(cert_base.keys()) | set(prod_base.keys()):
            if base_name in cert_base and base_name in prod_base:
                ambas.append({
                    'nombre_base': base_name,
                    'cert': cert_base[base_name],
                    'prod': prod_base[base_name]
                })
            elif base_name in cert_base:
                solo_cert.append(cert_base[base_name])
            else:
                solo_prod.append(prod_base[base_name])
        
        resultado = {
            'cert_count': len(cert_apis),
            'prod_count': len(prod_apis),
            'solo_cert': solo_cert,
            'solo_prod': solo_prod,
            'ambas': ambas,
            'sincronizado': len(solo_cert) == 0 and len(solo_prod) == 0,
            'porcentaje_sync': round((len(ambas) / max(len(cert_apis), len(prod_apis), 1)) * 100, 1)
        }
        
        cache_manager.set(cache_key, resultado)
        return resultado
        
    except Exception as e:
        return {
            'error': str(e),
            'cert_count': 0,
            'prod_count': 0,
            'solo_cert': [],
            'solo_prod': [],
            'ambas': [],
            'sincronizado': False,
            'porcentaje_sync': 0
        }

# ─── EC2: Comparar Virginia vs Ohio ───────────────────────────────────────────

def comparar_ec2_virginia_vs_ohio(perfil="afex-prod"):
    """
    Compara instancias EC2 en Virginia (us-east-1) vs Ohio (us-east-2).
    Verifica que tengan el mismo nombre y tipo.
    """
    
    cache_key = f"ec2_virginia_ohio_compare_{perfil}"
    cached = cache_manager.get(cache_key)
    if cached and not cached[1]: return cached[0]
    
    try:
        # Obtener datos de ambas regiones
        df_virginia = get_ec2_df(perfil=perfil, region="us-east-1")
        df_ohio = get_ec2_df(perfil=perfil, region="us-east-2")
        
        # Normalizar nombres
        virginia_nombres = set(df_virginia['nombre'].str.lower())
        ohio_nombres = set(df_ohio['nombre'].str.lower())
        
        solo_virginia = []
        solo_ohio = []
        ambas_info = []
        
        # Instancias que están en ambas
        en_ambas = virginia_nombres & ohio_nombres
        
        # Verificar sincronización
        for nombre in en_ambas:
            vm = df_virginia[df_virginia['nombre'].str.lower() == nombre].iloc[0]
            om = df_ohio[df_ohio['nombre'].str.lower() == nombre].iloc[0]
            
            ambas_info.append({
                'nombre': nombre,
                'virginia': {
                    'tipo': vm['tipo'],
                    'estado': vm['estado'],
                    'ip': vm['ip_privada'],
                    'vpc': vm['vpc']
                },
                'ohio': {
                    'tipo': om['tipo'],
                    'estado': om['estado'],
                    'ip': om['ip_privada'],
                    'vpc': om['vpc']
                },
                'tipo_sincronizado': vm['tipo'] == om['tipo'],
                'estado_sincronizado': vm['estado'] == om['estado']
            })
        
        # Instancias solo en Virginia
        for nombre in virginia_nombres - ohio_nombres:
            vm = df_virginia[df_virginia['nombre'].str.lower() == nombre].iloc[0]
            solo_virginia.append({
                'nombre': nombre,
                'tipo': vm['tipo'],
                'estado': vm['estado'],
                'vpc': vm['vpc']
            })
        
        # Instancias solo en Ohio
        for nombre in ohio_nombres - virginia_nombres:
            om = df_ohio[df_ohio['nombre'].str.lower() == nombre].iloc[0]
            solo_ohio.append({
                'nombre': nombre,
                'tipo': om['tipo'],
                'estado': om['estado'],
                'vpc': om['vpc']
            })
        
        resultado = {
            'virginia_count': len(virginia_nombres),
            'ohio_count': len(ohio_nombres),
            'solo_virginia': solo_virginia,
            'solo_ohio': solo_ohio,
            'ambas': ambas_info,
            'sincronizado': len(solo_virginia) == 0 and len(solo_ohio) == 0,
            'porcentaje_sync': round((len(en_ambas) / max(len(virginia_nombres), len(ohio_nombres), 1)) * 100, 1),
            'desajustes_tipo': sum(1 for a in ambas_info if not a['tipo_sincronizado']),
            'desajustes_estado': sum(1 for a in ambas_info if not a['estado_sincronizado'])
        }
        
        cache_manager.set(cache_key, resultado)
        return resultado
        
    except Exception as e:
        return {
            'error': str(e),
            'virginia_count': 0,
            'ohio_count': 0,
            'solo_virginia': [],
            'solo_ohio': [],
            'ambas': [],
            'sincronizado': False,
            'porcentaje_sync': 0,
            'desajustes_tipo': 0,
            'desajustes_estado': 0
        }

# ─── RESUMEN GENERAL ──────────────────────────────────────────────────────────

def resumen_sincronizacion_production(perfil="afex-prod"):
    """
    Retorna un resumen de la sincronización de production.
    """
    
    lambda_sync = comparar_lambda_cert_vs_prod(perfil)
    api_sync = comparar_api_cert_vs_prod(perfil)
    ec2_sync = comparar_ec2_virginia_vs_ohio(perfil)
    
    return {
        'lambda': lambda_sync,
        'api': api_sync,
        'ec2': ec2_sync,
        'estado_general': (
            lambda_sync.get('sincronizado', False) and
            api_sync.get('sincronizado', False) and
            ec2_sync.get('sincronizado', False)
        ),
        'alertas': [
            *(['Lambda CERT sin replicación a PROD' for _ in (lambda_sync.get('solo_cert', []) or []) if lambda_sync.get('solo_cert')]),
            *(['Lambda PROD sin equivalente CERT' for _ in (lambda_sync.get('solo_prod', []) or []) if lambda_sync.get('solo_prod')]),
            *(['API CERT sin replicación a PROD' for _ in (api_sync.get('solo_cert', []) or []) if api_sync.get('solo_cert')]),
            *(['EC2 solo en Virginia' for _ in (ec2_sync.get('solo_virginia', []) or []) if ec2_sync.get('solo_virginia')]),
            *(['EC2 solo en Ohio' for _ in (ec2_sync.get('solo_ohio', []) or []) if ec2_sync.get('solo_ohio')]),
        ]
    }
