"""
SNIPPET PARA AGREGAR A conector_aws.py
════════════════════════════════════════════════════════════════
Estas dos funciones obtienen las IPs de salida de las VPCs:

1. get_nat_gateways_df() → IP de salida para subnets PRIVADAS
2. get_elastic_ips_df()  → IPs públicas asignadas (salida directa)

Pégalas al final de tu conector_aws.py, junto a las otras get_*_df().
"""

import boto3
import pandas as pd


def get_nat_gateways_df(profile, region):
    """
    Obtiene los NAT Gateways de una región.
    
    El NAT Gateway es el punto de salida a internet para recursos
    en subnets PRIVADAS. Su Elastic IP es la IP pública que ven
    los servicios externos cuando tus instancias privadas los llaman.
    
    Returns:
        DataFrame con: NatGatewayId, VpcId, SubnetId, State,
                       PublicIp, PrivateIp, AllocationId, ConnectivityType,
                       CreateTime, Tags
    """
    session = boto3.Session(profile_name=profile, region_name=region)
    ec2 = session.client('ec2')
    
    rows = []
    paginator = ec2.get_paginator('describe_nat_gateways')
    
    for page in paginator.paginate():
        for nat in page.get('NatGateways', []):
            # Un NAT GW puede tener múltiples direcciones (aunque normalmente 1)
            addresses = nat.get('NatGatewayAddresses', [])
            
            if not addresses:
                # NAT GW sin direcciones (raro, pero posible en estados transitorios)
                rows.append({
                    'NatGatewayId': nat.get('NatGatewayId'),
                    'VpcId': nat.get('VpcId'),
                    'SubnetId': nat.get('SubnetId'),
                    'State': nat.get('State'),
                    'ConnectivityType': nat.get('ConnectivityType', 'public'),
                    'PublicIp': None,
                    'PrivateIp': None,
                    'AllocationId': None,
                    'NetworkInterfaceId': None,
                    'CreateTime': str(nat.get('CreateTime', '')),
                    'Region': region,
                    'Tags': _format_tags(nat.get('Tags', []))
                })
            else:
                for addr in addresses:
                    rows.append({
                        'NatGatewayId': nat.get('NatGatewayId'),
                        'VpcId': nat.get('VpcId'),
                        'SubnetId': nat.get('SubnetId'),
                        'State': nat.get('State'),
                        'ConnectivityType': nat.get('ConnectivityType', 'public'),
                        'PublicIp': addr.get('PublicIp'),       # ← IP DE SALIDA
                        'PrivateIp': addr.get('PrivateIp'),
                        'AllocationId': addr.get('AllocationId'),
                        'NetworkInterfaceId': addr.get('NetworkInterfaceId'),
                        'CreateTime': str(nat.get('CreateTime', '')),
                        'Region': region,
                        'Tags': _format_tags(nat.get('Tags', []))
                    })
    
    return pd.DataFrame(rows)


def get_elastic_ips_df(profile, region):
    """
    Obtiene las Elastic IPs (direcciones IP públicas asignadas).
    
    Las Elastic IPs son IPs públicas que pueden estar asociadas a:
    - Instancias EC2 (salida directa desde subnet pública)
    - NAT Gateways (salida desde subnet privada)
    - Network Interfaces (ENIs)
    - Load Balancers (vía ENI)
    - Sin asociar (reservadas pero no usadas)
    
    Returns:
        DataFrame con: PublicIp, AllocationId, AssociationId, Domain,
                       InstanceId, NetworkInterfaceId, PrivateIpAddress,
                       AssociatedResource, Tags
    """
    session = boto3.Session(profile_name=profile, region_name=region)
    ec2 = session.client('ec2')
    
    response = ec2.describe_addresses()
    
    rows = []
    for addr in response.get('Addresses', []):
        # Determinar a qué recurso está asociada
        if addr.get('InstanceId'):
            associated = f"EC2:{addr['InstanceId']}"
        elif addr.get('NetworkInterfaceId'):
            # Puede ser NAT GW, ELB, u otros
            ni_id = addr['NetworkInterfaceId']
            associated = f"ENI:{ni_id}"
            # Intentar identificar qué tipo de ENI es
            try:
                ni_detail = ec2.describe_network_interfaces(
                    NetworkInterfaceIds=[ni_id]
                )['NetworkInterfaces'][0]
                description = ni_detail.get('Description', '')
                interface_type = ni_detail.get('InterfaceType', 'interface')
                
                if 'NAT Gateway' in description or interface_type == 'nat_gateway':
                    associated = f"NAT-GW:{description}"
                elif 'ELB' in description or interface_type == 'network_load_balancer':
                    associated = f"LB:{description}"
                elif interface_type != 'interface':
                    associated = f"{interface_type}:{description}"
            except Exception:
                pass
        else:
            associated = 'UNASSOCIATED'  # ⚠️ EIP sin uso = cobro inútil
        
        rows.append({
            'PublicIp': addr.get('PublicIp'),              # ← IP DE SALIDA
            'AllocationId': addr.get('AllocationId'),
            'AssociationId': addr.get('AssociationId'),
            'Domain': addr.get('Domain'),
            'InstanceId': addr.get('InstanceId'),
            'NetworkInterfaceId': addr.get('NetworkInterfaceId'),
            'PrivateIpAddress': addr.get('PrivateIpAddress'),
            'NetworkBorderGroup': addr.get('NetworkBorderGroup'),
            'AssociatedResource': associated,
            'Region': region,
            'Tags': _format_tags(addr.get('Tags', []))
        })
    
    return pd.DataFrame(rows)


def _format_tags(tags_list):
    """Convierte lista de tags AWS a string 'key=value, key=value'."""
    if not tags_list:
        return ''
    return ', '.join([f"{t.get('Key', '')}={t.get('Value', '')}" for t in tags_list])


# ═════════════════════════════════════════════════════════════════════════════
# RECUERDA: no olvides exportar estas funciones si usas __all__
# ═════════════════════════════════════════════════════════════════════════════
# __all__ = [
#     ..., 'get_nat_gateways_df', 'get_elastic_ips_df'
# ]

# ═════════════════════════════════════════════════════════════════════════════
# PERMISOS IAM NECESARIOS (agregar al rol/usuario si aún no los tiene):
# ═════════════════════════════════════════════════════════════════════════════
# ec2:DescribeNatGateways
# ec2:DescribeAddresses
# ec2:DescribeNetworkInterfaces
