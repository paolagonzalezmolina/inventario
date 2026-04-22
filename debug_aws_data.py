"""
Script para verificar qué datos realmente existen en AWS
Sin pasar por el caché
"""

import boto3
from conector_aws import PERFILES

def check_aws_resources(account_name, region):
    """Verifica qué recursos existen en AWS para una cuenta/región"""
    
    account_config = PERFILES[account_name]
    profile = account_config['perfil']
    
    print(f"\n{'='*60}")
    print(f"Verificando: {account_name} / {region}")
    print(f"{'='*60}")
    
    try:
        session = boto3.Session(profile_name=profile)
        
        # EC2
        try:
            ec2 = session.client('ec2', region_name=region)
            instances = ec2.describe_instances()
            total = sum(len(r['Instances']) for r in instances['Reservations'])
            print(f"✅ EC2: {total} instancias")
        except Exception as e:
            print(f"❌ EC2: Error - {e}")
        
        # RDS
        try:
            rds = session.client('rds', region_name=region)
            dbs = rds.describe_db_instances()
            print(f"✅ RDS: {len(dbs['DBInstances'])} bases de datos")
        except Exception as e:
            print(f"❌ RDS: Error - {e}")
        
        # SSM Parameters
        try:
            ssm = session.client('ssm', region_name=region)
            params = ssm.describe_parameters()
            print(f"✅ SSM: {len(params['Parameters'])} parámetros")
        except Exception as e:
            print(f"❌ SSM: Error - {e}")
        
        # KMS Keys
        try:
            kms = session.client('kms', region_name=region)
            keys = kms.list_keys()
            print(f"✅ KMS: {len(keys['Keys'])} claves")
        except Exception as e:
            print(f"❌ KMS: Error - {e}")
        
        # DynamoDB
        try:
            ddb = session.client('dynamodb', region_name=region)
            tables = ddb.list_tables()
            print(f"✅ DynamoDB: {len(tables['TableNames'])} tablas")
        except Exception as e:
            print(f"❌ DynamoDB: Error - {e}")
        
        # Lambda
        try:
            lam = session.client('lambda', region_name=region)
            functions = lam.list_functions()
            print(f"✅ Lambda: {len(functions['Functions'])} funciones")
        except Exception as e:
            print(f"❌ Lambda: Error - {e}")
        
        # SQS
        try:
            sqs = session.client('sqs', region_name=region)
            queues = sqs.list_queues()
            queue_count = len(queues.get('QueueUrls', []))
            print(f"✅ SQS: {queue_count} colas")
        except Exception as e:
            print(f"❌ SQS: Error - {e}")
        
    except Exception as e:
        print(f"❌ Error general: {e}")


# Ejecutar para todas las cuentas y regiones
if __name__ == "__main__":
    for account_name in PERFILES.keys():
        regions = PERFILES[account_name]['regiones']
        for region in regions:
            check_aws_resources(account_name, region)
    
    print(f"\n{'='*60}")
    print("✅ Verificación completada")
    print(f"{'='*60}")
