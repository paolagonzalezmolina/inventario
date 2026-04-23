"""
download_engine.py - Motor de descarga paralela
════════════════════════════════════════════════════════════════
Descarga componentes de AWS en paralelo usando ThreadPoolExecutor.

Características:
- Descarga múltiples regiones/cuentas simultáneamente (4-8 threads)
- Caché inteligente: no redescarga si está fresco
- Discovery: averigua qué regiones existen en cada cuenta
- Logging detallado: sabe exactamente qué está descargando
- Sincronización semanal: automática cada lunes 8am
- IPs de salida de VPC: NAT Gateways, Elastic IPs e Internet Gateways

Cambios recientes:
- FIX: save_discovery es tolerante si CacheManager no lo implementa.
- FIX: import de 'config' es opcional (no rompe si el módulo no existe).
- FEATURE: descarga de IPs de salida de VPC (vpc_outbound_ips) por región.
"""

import streamlit as st
import logging
import json
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from cache_manager import cache_manager

# ──────────────────────────────────────────────────────────────────────────────
# Import defensivo de 'config' (algunos entornos no lo tienen)
# ──────────────────────────────────────────────────────────────────────────────
try:
    import config  # type: ignore
except ImportError:
    config = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if config is None:
    logger.warning(
        "⚠️  Módulo 'config' no encontrado. Se usará 'conector_aws.PERFILES' "
        "o 'us-east-1' como región global por defecto."
    )

# Variables globales para tracking
_discovery_complete = False
_download_stats = {
    'total_started': 0,
    'total_completed': 0,
    'total_failed': 0,
    'errors': []
}

# ═════════════════════════════════════════════════════════════════════════════
# HELPERS DEFENSIVOS
# ═════════════════════════════════════════════════════════════════════════════

def _infer_cache_dir():
    """Intenta deducir el directorio de caché que usa cache_manager."""
    for attr in ('cache_dir', 'base_dir', 'directory', 'path', 'root',
                 'cache_path', '_cache_dir'):
        if hasattr(cache_manager, attr):
            value = getattr(cache_manager, attr)
            if value:
                return Path(str(value))
    return Path('./cache')


def _save_discovery_safely(discovery_data):
    """
    Guarda el discovery usando cache_manager.save_discovery si existe;
    en caso contrario escribe a disco directamente. Evita romper la app
    si CacheManager no implementa save_discovery.
    """
    if hasattr(cache_manager, 'save_discovery'):
        try:
            cache_manager.save_discovery(discovery_data)
            return True
        except Exception as e:
            logger.warning(
                f"cache_manager.save_discovery falló ({e}). Usando fallback."
            )

    try:
        cache_dir = _infer_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        discovery_file = cache_dir / 'discovery.json'
        with open(discovery_file, 'w', encoding='utf-8') as f:
            json.dump(discovery_data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"💾 Discovery guardado en {discovery_file} (fallback)")
        return True
    except Exception as e:
        logger.error(f"❌ No se pudo guardar discovery: {e}")
        return False


def _get_global_region():
    """
    Retorna la región que se considera 'global' para bajar S3/IAM una sola
    vez por cuenta. Orden de preferencia:
      1) config.PERFILES (si el módulo existe)
      2) conector_aws.PERFILES
      3) 'us-east-1' por defecto
    """
    # 1) config.PERFILES
    if config is not None and hasattr(config, 'PERFILES'):
        try:
            first = next(iter(config.PERFILES.values()))
            region = first.get('region') if isinstance(first, dict) else None
            if region:
                return region
        except Exception as e:
            logger.debug(f"No se pudo leer config.PERFILES: {e}")

    # 2) conector_aws.PERFILES
    try:
        from conector_aws import PERFILES as _CA_PERFILES  # type: ignore
        first = next(iter(_CA_PERFILES.values()))
        region = first.get('region') if isinstance(first, dict) else None
        if region:
            return region
    except Exception as e:
        logger.debug(f"No se pudo leer conector_aws.PERFILES: {e}")

    # 3) Default
    return 'us-east-1'


# ═════════════════════════════════════════════════════════════════════════════
# HELPER: IPs DE SALIDA DE VPC (NAT Gateway, EIP, IGW)
# ═════════════════════════════════════════════════════════════════════════════

def _get_vpc_outbound_ips_inline(account_profile, region):
    """
    Obtiene las IPs públicas de salida de la VPC. Se usa como fallback si
    conector_aws no expone la función correspondiente.

    Recolecta:
    - NAT Gateways con su Elastic IP (ruta de salida principal para
      subredes privadas).
    - Elastic IPs sueltas (asociadas y disponibles) no ligadas a NAT.
    - Internet Gateways attachados a VPCs (referencia; la IP pública
      sale por instancia).
    """
    import boto3
    import pandas as pd

    session = boto3.Session(profile_name=account_profile, region_name=region)
    ec2 = session.client('ec2')

    rows = []

    # 1) NAT Gateways
    try:
        paginator = ec2.get_paginator('describe_nat_gateways')
        for page in paginator.paginate():
            for nat in page.get('NatGateways', []):
                tags = {t['Key']: t['Value'] for t in nat.get('Tags', []) or []}
                addresses = nat.get('NatGatewayAddresses', []) or []
                if not addresses:
                    rows.append({
                        'type': 'NAT Gateway',
                        'resource_id': nat.get('NatGatewayId'),
                        'name': tags.get('Name', ''),
                        'vpc_id': nat.get('VpcId'),
                        'subnet_id': nat.get('SubnetId'),
                        'public_ip': '',
                        'private_ip': '',
                        'allocation_id': '',
                        'network_interface_id': '',
                        'state': nat.get('State'),
                        'connectivity_type': nat.get('ConnectivityType', 'public'),
                        'region': region,
                    })
                for addr in addresses:
                    rows.append({
                        'type': 'NAT Gateway',
                        'resource_id': nat.get('NatGatewayId'),
                        'name': tags.get('Name', ''),
                        'vpc_id': nat.get('VpcId'),
                        'subnet_id': nat.get('SubnetId'),
                        'public_ip': addr.get('PublicIp') or '',
                        'private_ip': addr.get('PrivateIp') or '',
                        'allocation_id': addr.get('AllocationId') or '',
                        'network_interface_id': addr.get('NetworkInterfaceId') or '',
                        'state': nat.get('State'),
                        'connectivity_type': nat.get('ConnectivityType', 'public'),
                        'region': region,
                    })
    except Exception as e:
        logger.warning(f"describe_nat_gateways en {region} falló: {e}")

    nat_allocations = {r['allocation_id'] for r in rows if r.get('allocation_id')}

    # 2) Elastic IPs
    try:
        eips = ec2.describe_addresses()
        for addr in eips.get('Addresses', []):
            alloc_id = addr.get('AllocationId') or ''
            if alloc_id and alloc_id in nat_allocations:
                continue
            tags = {t['Key']: t['Value'] for t in addr.get('Tags', []) or []}
            rows.append({
                'type': 'Elastic IP',
                'resource_id': alloc_id or addr.get('PublicIp'),
                'name': tags.get('Name', ''),
                'vpc_id': '',
                'subnet_id': '',
                'public_ip': addr.get('PublicIp') or '',
                'private_ip': addr.get('PrivateIpAddress') or '',
                'allocation_id': alloc_id,
                'network_interface_id': addr.get('NetworkInterfaceId') or '',
                'state': 'associated' if addr.get('AssociationId') else 'available',
                'connectivity_type': 'public',
                'region': region,
            })
    except Exception as e:
        logger.warning(f"describe_addresses en {region} falló: {e}")

    # 3) Internet Gateways
    try:
        igws = ec2.describe_internet_gateways()
        for igw in igws.get('InternetGateways', []):
            tags = {t['Key']: t['Value'] for t in igw.get('Tags', []) or []}
            attachments = igw.get('Attachments', []) or []
            if not attachments:
                rows.append({
                    'type': 'Internet Gateway',
                    'resource_id': igw.get('InternetGatewayId'),
                    'name': tags.get('Name', ''),
                    'vpc_id': '',
                    'subnet_id': '',
                    'public_ip': 'N/A (IP pública por instancia)',
                    'private_ip': '',
                    'allocation_id': '',
                    'network_interface_id': '',
                    'state': 'detached',
                    'connectivity_type': 'public',
                    'region': region,
                })
            for att in attachments:
                rows.append({
                    'type': 'Internet Gateway',
                    'resource_id': igw.get('InternetGatewayId'),
                    'name': tags.get('Name', ''),
                    'vpc_id': att.get('VpcId'),
                    'subnet_id': '',
                    'public_ip': 'N/A (IP pública por instancia)',
                    'private_ip': '',
                    'allocation_id': '',
                    'network_interface_id': '',
                    'state': att.get('State', 'unknown'),
                    'connectivity_type': 'public',
                    'region': region,
                })
    except Exception as e:
        logger.warning(f"describe_internet_gateways en {region} falló: {e}")

    return pd.DataFrame(rows)


def _get_vpc_outbound_ips(account_profile, region):
    """
    Obtiene IPs de salida de VPC delegando a conector_aws.get_vpc_outbound_ips_df
    si está disponible; de lo contrario usa la implementación inline.
    """
    try:
        from conector_aws import get_vpc_outbound_ips_df  # type: ignore
        return get_vpc_outbound_ips_df(account_profile, region)
    except (ImportError, AttributeError):
        return _get_vpc_outbound_ips_inline(account_profile, region)


def _enrich_with_audit(account_profile, region, resource_type, data):
    """Completa metadatos de auditoria antes de guardar en cache."""
    try:
        from conector_aws import add_audit_metadata  # type: ignore
        return add_audit_metadata(account_profile, region, resource_type, data)
    except Exception as e:
        logger.warning(
            f"No se pudo enriquecer auditoria para {resource_type} en {region}: {e}"
        )
        return data


# ═════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE DISCOVERY
# ═════════════════════════════════════════════════════════════════════════════

def discover_regions_and_accounts():
    """
    Descubre qué regiones y cuentas existen.
    Ejecuta una sola vez al startup.
    """
    global _discovery_complete

    discovery = cache_manager.load_discovery()
    if discovery and discovery.get('status') == 'complete':
        logger.info("📍 Discovery cargado del caché")
        _discovery_complete = True
        return discovery

    logger.info("🔍 Iniciando discovery de regiones...")

    try:
        from conector_aws import PERFILES, get_available_regions

        accounts_info = []

        for account_name, account_config in PERFILES.items():
            profile = account_config.get('perfil')

            try:
                regions = get_available_regions(profile)

                accounts_info.append({
                    'name': account_name,
                    'profile': profile,
                    'regions': regions,
                    'status': 'discovered'
                })

                logger.info(f"✅ {account_name}: {len(regions)} regiones encontradas")

            except Exception as e:
                logger.error(f"❌ Error descubriendo {account_name}: {e}")
                accounts_info.append({
                    'name': account_name,
                    'profile': profile,
                    'regions': [],
                    'status': 'failed',
                    'error': str(e)
                })

        discovery_data = {
            'accounts': accounts_info,
            'timestamp': datetime.now().isoformat(),
            'status': 'complete'
        }

        _save_discovery_safely(discovery_data)

        logger.info(f"✅ Discovery completado: {len(accounts_info)} cuentas")
        _discovery_complete = True
        return discovery_data

    except Exception as e:
        logger.error(f"❌ Error en discovery: {e}")
        return {
            'accounts': [],
            'timestamp': datetime.now().isoformat(),
            'status': 'failed',
            'error': str(e)
        }

# ═════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE DESCARGA PARALELA
# ═════════════════════════════════════════════════════════════════════════════

def download_region_account(account_name, account_profile, region):
    """
    Descarga TODOS los componentes de una región-cuenta específica.
    Se ejecuta en paralelo (uno por thread).
    """
    from conector_aws import (
        get_ec2_df, get_rds_df, get_vpc_df, get_s3_df,
        get_iam_users_df, get_lambda_df, get_api_gateway_df, get_api_gateway_routes_df,
        get_cloudformation_df, get_ssm_df, get_kms_df,
        get_dynamodb_df, get_sqs_df
    )

    key = f"{account_name}_{region}"
    result = {
        'key': key,
        'account': account_name,
        'region': region,
        'resources': {},
        'errors': [],
        'started_at': datetime.now().isoformat()
    }

    # Región 'global' donde se descargan S3 / IAM (una sola vez por cuenta)
    global_region = _get_global_region()

    try:
        logger.info(f"⬇️  Descargando {key}...")

        # EC2
        try:
            logger.info(f"  ↳ EC2 para {key}...")
            df_ec2 = get_ec2_df(account_profile, region)
            df_ec2 = _enrich_with_audit(account_profile, region, 'ec2', df_ec2)
            compare_result = cache_manager.compare_and_update(account_name, region, 'ec2', df_ec2)
            result['resources']['ec2'] = {
                'count': len(df_ec2),
                'status': compare_result['status'],
                'saved': compare_result['saved']
            }
            logger.info(f"  ✅ EC2: {compare_result['status']}")
        except Exception as e:
            result['errors'].append(f"EC2: {str(e)}")
            logger.error(f"  ❌ EC2 error: {e}")

        # RDS
        try:
            logger.info(f"  ↳ RDS para {key}...")
            df_rds = get_rds_df(account_profile, region)
            df_rds = _enrich_with_audit(account_profile, region, 'rds', df_rds)
            compare_result = cache_manager.compare_and_update(account_name, region, 'rds', df_rds)
            result['resources']['rds'] = {
                'count': len(df_rds),
                'status': compare_result['status'],
                'saved': compare_result['saved']
            }
            logger.info(f"  ✅ RDS: {compare_result['status']}")
        except Exception as e:
            result['errors'].append(f"RDS: {str(e)}")
            logger.error(f"  ❌ RDS error: {e}")

        # VPC
        try:
            logger.info(f"  ↳ VPC para {key}...")
            df_vpc = get_vpc_df(account_profile, region)
            df_vpc = _enrich_with_audit(account_profile, region, 'vpc', df_vpc)
            compare_result = cache_manager.compare_and_update(account_name, region, 'vpc', df_vpc)
            result['resources']['vpc'] = {
                'count': len(df_vpc),
                'status': compare_result['status'],
                'saved': compare_result['saved']
            }
            logger.info(f"  ✅ VPC: {compare_result['status']}")
        except Exception as e:
            result['errors'].append(f"VPC: {str(e)}")
            logger.error(f"  ❌ VPC error: {e}")

        # VPC Outbound IPs (NUEVO) — regional: NAT GW + EIPs + IGWs
        try:
            logger.info(f"  ↳ VPC Outbound IPs para {key}...")
            df_vpc_out = _get_vpc_outbound_ips(account_profile, region)
            df_vpc_out = _enrich_with_audit(account_profile, region, 'vpc_outbound_ips', df_vpc_out)
            compare_result = cache_manager.compare_and_update(
                account_name, region, 'vpc_outbound_ips', df_vpc_out
            )
            result['resources']['vpc_outbound_ips'] = {
                'count': len(df_vpc_out),
                'status': compare_result['status'],
                'saved': compare_result['saved']
            }
            logger.info(
                f"  ✅ VPC Outbound IPs: {compare_result['status']} "
                f"({len(df_vpc_out)} registros)"
            )
        except Exception as e:
            result['errors'].append(f"VPC Outbound IPs: {str(e)}")
            logger.error(f"  ❌ VPC Outbound IPs error: {e}")

        # S3 (solo en la región 'global' — es servicio global)
        if region == global_region:
            try:
                logger.info(f"  ↳ S3 para {account_name}...")
                df_s3 = get_s3_df(account_profile)
                df_s3 = _enrich_with_audit(account_profile, region, 's3', df_s3)
                compare_result = cache_manager.compare_and_update(account_name, region, 's3', df_s3)
                result['resources']['s3'] = {
                    'count': len(df_s3),
                    'status': compare_result['status'],
                    'saved': compare_result['saved']
                }
                logger.info(f"  ✅ S3: {compare_result['status']}")
            except Exception as e:
                result['errors'].append(f"S3: {str(e)}")
                logger.error(f"  ❌ S3 error: {e}")

        # IAM Users (solo en la región 'global' — es servicio global)
        if region == global_region:
            try:
                logger.info(f"  ↳ IAM Users para {account_name}...")
                df_iam = get_iam_users_df(account_profile)
                df_iam = _enrich_with_audit(account_profile, region, 'iam_users', df_iam)
                compare_result = cache_manager.compare_and_update(account_name, region, 'iam_users', df_iam)
                result['resources']['iam_users'] = {
                    'count': len(df_iam),
                    'status': compare_result['status'],
                    'saved': compare_result['saved']
                }
                logger.info(f"  ✅ IAM Users: {compare_result['status']}")
            except Exception as e:
                result['errors'].append(f"IAM: {str(e)}")
                logger.error(f"  ❌ IAM error: {e}")

        # Lambda
        try:
            logger.info(f"  ↳ Lambda para {key}...")
            df_lambda = get_lambda_df(account_profile, region)
            df_lambda = _enrich_with_audit(account_profile, region, 'lambda', df_lambda)
            compare_result = cache_manager.compare_and_update(account_name, region, 'lambda', df_lambda)
            result['resources']['lambda'] = {
                'count': len(df_lambda),
                'status': compare_result['status'],
                'saved': compare_result['saved']
            }
            logger.info(f"  ✅ Lambda: {compare_result['status']}")
        except Exception as e:
            result['errors'].append(f"Lambda: {str(e)}")
            logger.error(f"  ❌ Lambda error: {e}")

        # API Gateway
        try:
            logger.info(f"  ↳ API Gateway para {key}...")
            df_api = get_api_gateway_df(account_profile, region)
            df_api = _enrich_with_audit(account_profile, region, 'api_gateway', df_api)
            compare_result = cache_manager.compare_and_update(account_name, region, 'api_gateway', df_api)
            result['resources']['api_gateway'] = {
                'count': len(df_api),
                'status': compare_result['status'],
                'saved': compare_result['saved']
            }
            logger.info(f"  ✅ API Gateway: {compare_result['status']}")
        except Exception as e:
            result['errors'].append(f"API Gateway: {str(e)}")
            logger.error(f"  ❌ API Gateway error: {e}")

        # API Gateway Routes / Lambda mappings
        try:
            logger.info(f"  ↳ API Gateway Routes para {key}...")
            df_api_routes = get_api_gateway_routes_df(account_profile, region)
            df_api_routes = _enrich_with_audit(
                account_profile, region, 'api_gateway_routes', df_api_routes
            )
            compare_result = cache_manager.compare_and_update(
                account_name, region, 'api_gateway_routes', df_api_routes
            )
            result['resources']['api_gateway_routes'] = {
                'count': len(df_api_routes),
                'status': compare_result['status'],
                'saved': compare_result['saved']
            }
            logger.info(f"  ✅ API Gateway Routes: {compare_result['status']}")
        except Exception as e:
            result['errors'].append(f"API Gateway Routes: {str(e)}")
            logger.error(f"  ❌ API Gateway Routes error: {e}")

        # CloudFormation
        try:
            logger.info(f"  â†³ CloudFormation para {key}...")
            df_cloudformation = get_cloudformation_df(account_profile, region)
            df_cloudformation = _enrich_with_audit(
                account_profile, region, 'cloudformation', df_cloudformation
            )
            compare_result = cache_manager.compare_and_update(
                account_name, region, 'cloudformation', df_cloudformation
            )
            result['resources']['cloudformation'] = {
                'count': len(df_cloudformation),
                'status': compare_result['status'],
                'saved': compare_result['saved']
            }
            logger.info(f"  âœ… CloudFormation: {compare_result['status']}")
        except Exception as e:
            result['errors'].append(f"CloudFormation: {str(e)}")
            logger.error(f"  âŒ CloudFormation error: {e}")

        # SSM
        try:
            logger.info(f"  â†³ SSM para {key}...")
            df_ssm = get_ssm_df(account_profile, region)
            df_ssm = _enrich_with_audit(account_profile, region, 'ssm', df_ssm)
            compare_result = cache_manager.compare_and_update(
                account_name, region, 'ssm', df_ssm
            )
            result['resources']['ssm'] = {
                'count': len(df_ssm),
                'status': compare_result['status'],
                'saved': compare_result['saved']
            }
            logger.info(f"  âœ… SSM: {compare_result['status']}")
        except Exception as e:
            result['errors'].append(f"SSM: {str(e)}")
            logger.error(f"  âŒ SSM error: {e}")

        # KMS
        try:
            logger.info(f"  â†³ KMS para {key}...")
            df_kms = get_kms_df(account_profile, region)
            df_kms = _enrich_with_audit(account_profile, region, 'kms', df_kms)
            compare_result = cache_manager.compare_and_update(
                account_name, region, 'kms', df_kms
            )
            result['resources']['kms'] = {
                'count': len(df_kms),
                'status': compare_result['status'],
                'saved': compare_result['saved']
            }
            logger.info(f"  âœ… KMS: {compare_result['status']}")
        except Exception as e:
            result['errors'].append(f"KMS: {str(e)}")
            logger.error(f"  âŒ KMS error: {e}")

        # DynamoDB
        try:
            logger.info(f"  â†³ DynamoDB para {key}...")
            df_dynamodb = get_dynamodb_df(account_profile, region)
            df_dynamodb = _enrich_with_audit(account_profile, region, 'dynamodb', df_dynamodb)
            compare_result = cache_manager.compare_and_update(
                account_name, region, 'dynamodb', df_dynamodb
            )
            result['resources']['dynamodb'] = {
                'count': len(df_dynamodb),
                'status': compare_result['status'],
                'saved': compare_result['saved']
            }
            logger.info(f"  âœ… DynamoDB: {compare_result['status']}")
        except Exception as e:
            result['errors'].append(f"DynamoDB: {str(e)}")
            logger.error(f"  âŒ DynamoDB error: {e}")

        # SQS
        try:
            logger.info(f"  â†³ SQS para {key}...")
            df_sqs = get_sqs_df(account_profile, region)
            df_sqs = _enrich_with_audit(account_profile, region, 'sqs', df_sqs)
            compare_result = cache_manager.compare_and_update(
                account_name, region, 'sqs', df_sqs
            )
            result['resources']['sqs'] = {
                'count': len(df_sqs),
                'status': compare_result['status'],
                'saved': compare_result['saved']
            }
            logger.info(f"  âœ… SQS: {compare_result['status']}")
        except Exception as e:
            result['errors'].append(f"SQS: {str(e)}")
            logger.error(f"  âŒ SQS error: {e}")

        result['status'] = 'success' if not result['errors'] else 'partial'
        result['completed_at'] = datetime.now().isoformat()
        logger.info(f"✅ Completado {key}: {result['resources']}")

        return result

    except Exception as e:
        result['status'] = 'failed'
        result['errors'].append(f"General: {str(e)}")
        logger.error(f"❌ Error descargando {key}: {e}")
        return result

def download_all_parallel(max_workers=4):
    """
    Descarga TODO en paralelo usando ThreadPoolExecutor.
    """
    global _download_stats

    discovery = cache_manager.load_discovery()
    if not discovery or discovery.get('status') != 'complete':
        discovery = discover_regions_and_accounts()

    if discovery.get('status') != 'complete' or not discovery.get('accounts'):
        logger.error("❌ Discovery no completado")
        return {'status': 'failed', 'error': 'Discovery incompleto'}

    logger.info(f"⬇️  Iniciando descarga paralela ({max_workers} threads)...")

    tasks = []
    for account in discovery['accounts']:
        account_name = account['name']
        account_profile = account['profile']
        regions = account['regions']

        for region in regions:
            tasks.append((account_name, account_profile, region))

    logger.info(f"📋 Total de descargas: {len(tasks)} (cuentas × regiones)")

    results = {
        'total': len(tasks),
        'completed': 0,
        'failed': 0,
        'partial': 0,
        'details': []
    }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(download_region_account, *task): task
            for task in tasks
        }

        for future in as_completed(futures):
            try:
                result = future.result()
                results['details'].append(result)

                if result['status'] == 'success':
                    results['completed'] += 1
                elif result['status'] == 'partial':
                    results['partial'] += 1
                else:
                    results['failed'] += 1

                logger.info(f"[{results['completed']}/{results['total']}] {result['key']}")

            except Exception as e:
                logger.error(f"Error en tarea: {e}")
                results['failed'] += 1

    results['status'] = 'complete'
    results['timestamp'] = datetime.now().isoformat()

    changes_summary = {
        'new': 0,
        'updated': 0,
        'unchanged': 0,
        'total_saved': 0,
        'resources_changed': []
    }

    for detail in results['details']:
        for resource_type, resource_data in detail.get('resources', {}).items():
            if isinstance(resource_data, dict):
                status = resource_data.get('status', 'unknown')
                saved = resource_data.get('saved', False)

                if status == 'new':
                    changes_summary['new'] += 1
                elif status == 'updated':
                    changes_summary['updated'] += 1
                    changes_summary['resources_changed'].append(
                        f"{detail['account']}:{detail['region']}:{resource_type}"
                    )
                elif status == 'unchanged':
                    changes_summary['unchanged'] += 1

                if saved:
                    changes_summary['total_saved'] += 1

    results['changes_summary'] = changes_summary

    logger.info(f"""
    ✅ DESCARGA COMPLETADA (INTELIGENTE)
    ├─ Exitosas: {results['completed']}
    ├─ Parciales: {results['partial']}
    ├─ Fallidas: {results['failed']}
    ├─ Total: {results['total']}
    │
    ├─ 🆕 Nuevos: {changes_summary['new']}
    ├─ 📈 Actualizados: {changes_summary['updated']}
    ├─ ✅ Sin cambios: {changes_summary['unchanged']}
    └─ 💾 Guardados: {changes_summary['total_saved']}

    {f'Cambios detectados en: {", ".join(changes_summary["resources_changed"][:5])}' if changes_summary['resources_changed'] else 'Sin cambios detectados'}
    """)

    return results

def get_cache_status():
    """Retorna estado del caché actual."""
    stats = cache_manager.get_stats()
    discovery = cache_manager.load_discovery()

    return {
        'cache_size_mb': stats['total_size_mb'],
        'cache_files': stats['total_files'],
        'region_accounts': stats['region_accounts'],
        'discovery_complete': discovery and discovery.get('status') == 'complete',
        'discovery_timestamp': discovery.get('timestamp') if discovery else None
    }

# ═════════════════════════════════════════════════════════════════════════════
# INICIALIZACIÓN
# ═════════════════════════════════════════════════════════════════════════════

@st.cache_resource
def initialize_download_engine():
    """
    Inicializa el motor al startup.
    """
    logger.info("🚀 Inicializando download engine...")

    discovery_result = discover_regions_and_accounts()

    cache_stats = cache_manager.get_stats()

    if cache_stats['total_files'] == 0:
        logger.info("📥 Caché vacío, iniciando descarga automática en background...")

    return {
        'discovery': discovery_result,
        'cache_stats': cache_stats,
        'ready': True
    }
