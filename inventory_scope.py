"""
Alcance compartido para Dashboard y export Excel.

Centraliza cuentas, regiones descubiertas, servicios contables y reglas de
servicios globales para evitar descuadres entre pantalla y workbook.
"""

import pandas as pd

ALL_ACCOUNTS_OPTION = "__all_accounts__"
ALL_REGIONS_OPTION = "__all_regions__"
GLOBAL_SERVICES = {"s3", "iam_users"}
PRIORITY_REGIONS = ["us-east-1", "us-east-2"]

DASHBOARD_SERVICE_CONFIG = [
    {"cache_key": "ec2", "label": "EC2", "global_service": False},
    {"cache_key": "rds", "label": "RDS", "global_service": False},
    {"cache_key": "vpc", "label": "VPC", "global_service": False},
    {"cache_key": "vpc_outbound_ips", "label": "NAT/IPs salida", "global_service": False},
    {"cache_key": "ebs_volumes", "label": "EBS Volumes", "global_service": False},
    {"cache_key": "ebs_snapshots", "label": "EBS Snapshots", "global_service": False},
    {"cache_key": "s3", "label": "S3", "global_service": True},
    {"cache_key": "iam_users", "label": "IAM", "global_service": True},
    {"cache_key": "lambda", "label": "Lambda", "global_service": False},
    {"cache_key": "api_gateway", "label": "API GW", "global_service": False},
    {"cache_key": "cloudformation", "label": "CloudFormation", "global_service": False},
    {"cache_key": "ssm", "label": "SSM", "global_service": False},
    {"cache_key": "kms", "label": "KMS", "global_service": False},
    {"cache_key": "dynamodb", "label": "DynamoDB", "global_service": False},
    {"cache_key": "sqs", "label": "SQS", "global_service": False},
]


def _dedupe(values):
    return list(dict.fromkeys(value for value in values if value))


def get_selected_account_names(perfiles, account_name=ALL_ACCOUNTS_OPTION):
    """Expande la opcion global a nombres reales de cuenta."""
    if account_name == ALL_ACCOUNTS_OPTION:
        return list(perfiles.keys())
    return [account_name]


def get_account_regions(perfiles, discovery, account_name):
    """Retorna regiones descubiertas para una cuenta con fallback a PERFILES."""
    discovery = discovery or {}
    for account in discovery.get("accounts", []):
        if account.get("name") == account_name:
            regions = _dedupe(account.get("regions") or [])
            if regions:
                return regions
    return perfiles.get(account_name, {}).get("regiones") or ["us-east-1"]


def get_global_region(perfiles, account_name):
    """Retorna la region base donde se guardan servicios globales."""
    return perfiles.get(account_name, {}).get("region") or "us-east-1"


def get_prioritized_regions(perfiles, discovery, account_name):
    """Ordena regiones priorizando Virginia/Ohio y luego el resto alfabeticamente."""
    regions = []
    for real_account in get_selected_account_names(perfiles, account_name):
        regions.extend(get_account_regions(perfiles, discovery, real_account))
    regions = _dedupe(regions)
    prioritized = [region for region in PRIORITY_REGIONS if region in regions]
    remaining = sorted(region for region in regions if region not in prioritized)
    return prioritized + remaining


def resolve_inventory_scope(
    perfiles,
    discovery=None,
    account_name=ALL_ACCOUNTS_OPTION,
    selected_region=ALL_REGIONS_OPTION,
    services=None,
):
    """Construye el alcance concreto que deben compartir Dashboard y Excel."""
    service_config = list(services or DASHBOARD_SERVICE_CONFIG)
    accounts = get_selected_account_names(perfiles, account_name)
    account_regions = {}
    service_regions = {}

    for account in accounts:
        selected_regions = (
            get_prioritized_regions(perfiles, discovery, account)
            if selected_region == ALL_REGIONS_OPTION
            else [selected_region]
        )
        account_regions[account] = selected_regions
        service_regions[account] = {}

        for service in service_config:
            cache_key = service["cache_key"]
            if service.get("global_service") or cache_key in GLOBAL_SERVICES:
                service_regions[account][cache_key] = [get_global_region(perfiles, account)]
            else:
                service_regions[account][cache_key] = selected_regions

    return {
        "accounts": accounts,
        "selected_region": selected_region,
        "account_regions": account_regions,
        "service_regions": service_regions,
        "services": service_config,
    }


def summarize_cache_state(states):
    """Resume frescura de una coleccion de caches."""
    existing_states = [is_fresh for is_fresh, exists in states if exists]
    if not existing_states:
        return "Sin datos"
    if all(existing_states):
        return "Fresco"
    if any(existing_states):
        return "Mixto"
    return "Viejo"


def build_dashboard_count_rows(cache_getter, scope):
    """Cuenta recursos por servicio usando exactamente el alcance resuelto."""
    rows = []

    for service in scope["services"]:
        service_count = 0
        states = []
        cache_key = service["cache_key"]

        for account in scope["accounts"]:
            for region in scope["service_regions"][account][cache_key]:
                data, is_fresh, exists = cache_getter(account, region, cache_key)
                states.append((is_fresh, exists))
                if exists and isinstance(data, pd.DataFrame):
                    service_count += len(data)

        rows.append(
            {
                "Servicio": service["label"],
                "cache_key": cache_key,
                "Conteo Dashboard": service_count,
                "Estado cache": summarize_cache_state(states),
            }
        )

    return rows
