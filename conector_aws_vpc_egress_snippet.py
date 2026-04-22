"""
Snippet para agregar a conector_aws.py
════════════════════════════════════════════════════════════════
Función que obtiene las IPs de salida (egress) de las VPCs.

En AWS, las "IPs de salida" de una VPC son:
- NAT Gateways → IP pública que usan las instancias de subnets PRIVADAS
                 para salir a internet. Es la IP más importante, la que
                 verán los servicios externos a los que tu VPC se conecta.
- Elastic IPs  → IPs públicas asignadas directamente a instancias en
                 subnets públicas (cada instancia sale con SU propia IP).
- Internet Gateways → No tienen IP propia, pero se listan como referencia
                      porque son el componente que habilita el tráfico
                      saliente de las subnets públicas.

NOTA IMPORTANTE sobre whitelisting:
Si necesitas dar a un proveedor externo (ej: un banco, un ERP) las IPs
de tu empresa para que las agregue a su whitelist, las que importan son
las de NAT Gateway (subnets privadas) y las EIP asociadas (subnets
públicas). Esta función las consolida todas.
"""

import boto3
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def get_vpc_egress_ips_df(profile, region):
    """
    Obtiene las IPs públicas de salida de las VPCs.
    
    Consolida tres fuentes:
      1. NAT Gateways (y sus Elastic IPs asociadas)
      2. Elastic IPs (filtrando las que ya son de NAT Gateway)
      3. Internet Gateways (como referencia, no tienen IP propia)
    
    Args:
        profile: Nombre del perfil boto3 (ej: "inventario-b")
        region: Región AWS (ej: "us-east-1")
    
    Returns:
        pd.DataFrame con columnas:
            - VpcId, Type, PublicIp, PrivateIp
            - AllocationId, NetworkInterfaceId, SubnetId
            - State, ResourceId, ConnectivityType
            - AssociatedResource, Region
    """
    session = boto3.Session(profile_name=profile, region_name=region)
    ec2 = session.client('ec2')
    
    rows = []
    nat_allocation_ids = set()  # Para evitar duplicar EIPs de NAT GW
    
    # ─────────────────────────────────────────────────────────────
    # 1) NAT Gateways — la IP de salida de subnets PRIVADAS
    # ─────────────────────────────────────────────────────────────
    try:
        paginator = ec2.get_paginator('describe_nat_gateways')
        for page in paginator.paginate():
            for nat in page.get('NatGateways', []):
                # Ignorar NAT Gateways eliminados
                if nat.get('State') in ('deleted', 'deleting', 'failed'):
                    continue
                
                for addr in nat.get('NatGatewayAddresses', []):
                    alloc_id = addr.get('AllocationId', '')
                    if alloc_id:
                        nat_allocation_ids.add(alloc_id)
                    
                    rows.append({
                        'VpcId': nat.get('VpcId', ''),
                        'Type': 'NAT Gateway',
                        'PublicIp': addr.get('PublicIp', ''),
                        'PrivateIp': addr.get('PrivateIp', ''),
                        'AllocationId': alloc_id,
                        'NetworkInterfaceId': addr.get('NetworkInterfaceId', ''),
                        'SubnetId': nat.get('SubnetId', ''),
                        'State': nat.get('State', ''),
                        'ResourceId': nat.get('NatGatewayId', ''),
                        'ConnectivityType': nat.get('ConnectivityType', 'public'),
                        'AssociatedResource': f"NAT-GW in {nat.get('SubnetId', '')}",
                        'Region': region,
                    })
    except Exception as e:
        logger.warning(f"[{profile}/{region}] No se pudieron obtener NAT Gateways: {e}")
    
    # ─────────────────────────────────────────────────────────────
    # 2) Elastic IPs — IPs públicas asignadas a instancias / ENIs
    #    (filtramos las que ya están en NAT Gateway para no duplicar)
    # ─────────────────────────────────────────────────────────────
    try:
        addresses = ec2.describe_addresses().get('Addresses', [])
        for addr in addresses:
            alloc_id = addr.get('AllocationId', '')
            
            # Omitir EIPs que ya contamos en NAT Gateways
            if alloc_id in nat_allocation_ids:
                continue
            
            # Resolver VPC del recurso asociado
            vpc_id = ''
            associated_resource = 'unassociated'
            subnet_id = ''
            
            if addr.get('InstanceId'):
                associated_resource = f"Instance: {addr['InstanceId']}"
                try:
                    resp = ec2.describe_instances(InstanceIds=[addr['InstanceId']])
                    if resp['Reservations']:
                        inst = resp['Reservations'][0]['Instances'][0]
                        vpc_id = inst.get('VpcId', '')
                        subnet_id = inst.get('SubnetId', '')
                except Exception:
                    pass
            elif addr.get('NetworkInterfaceId'):
                associated_resource = f"ENI: {addr['NetworkInterfaceId']}"
                try:
                    resp = ec2.describe_network_interfaces(
                        NetworkInterfaceIds=[addr['NetworkInterfaceId']]
                    )
                    if resp['NetworkInterfaces']:
                        eni = resp['NetworkInterfaces'][0]
                        vpc_id = eni.get('VpcId', '')
                        subnet_id = eni.get('SubnetId', '')
                except Exception:
                    pass
            
            rows.append({
                'VpcId': vpc_id,
                'Type': 'Elastic IP',
                'PublicIp': addr.get('PublicIp', ''),
                'PrivateIp': addr.get('PrivateIpAddress', ''),
                'AllocationId': alloc_id,
                'NetworkInterfaceId': addr.get('NetworkInterfaceId', ''),
                'SubnetId': subnet_id,
                'State': 'associated' if addr.get('AssociationId') else 'unassociated',
                'ResourceId': alloc_id,
                'ConnectivityType': 'public',
                'AssociatedResource': associated_resource,
                'Region': region,
            })
    except Exception as e:
        logger.warning(f"[{profile}/{region}] No se pudieron obtener Elastic IPs: {e}")
    
    # ─────────────────────────────────────────────────────────────
    # 3) Internet Gateways — referencia (no tienen IP propia)
    # ─────────────────────────────────────────────────────────────
    try:
        igws = ec2.describe_internet_gateways().get('InternetGateways', [])
        for igw in igws:
            for att in igw.get('Attachments', []):
                rows.append({
                    'VpcId': att.get('VpcId', ''),
                    'Type': 'Internet Gateway',
                    'PublicIp': '(IP pública de cada instancia)',
                    'PrivateIp': '',
                    'AllocationId': '',
                    'NetworkInterfaceId': '',
                    'SubnetId': '',
                    'State': att.get('State', ''),
                    'ResourceId': igw.get('InternetGatewayId', ''),
                    'ConnectivityType': 'public',
                    'AssociatedResource': 'Routes public-subnet traffic',
                    'Region': region,
                })
    except Exception as e:
        logger.warning(f"[{profile}/{region}] No se pudieron obtener Internet Gateways: {e}")
    
    # Devolver DataFrame con columnas consistentes aunque esté vacío
    columns = [
        'VpcId', 'Type', 'PublicIp', 'PrivateIp',
        'AllocationId', 'NetworkInterfaceId', 'SubnetId',
        'State', 'ResourceId', 'ConnectivityType',
        'AssociatedResource', 'Region',
    ]
    return pd.DataFrame(rows, columns=columns)
