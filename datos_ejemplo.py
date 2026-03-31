"""
datos_ejemplo.py
----------------
Datos ficticios que simulan lo que vendrá de AWS cuando conectes tus credenciales.
Cuando tengas el Access Key, este archivo se reemplaza por llamadas reales a boto3.
"""

import pandas as pd
from datetime import datetime, timedelta

# ─── EC2: Servidores ───────────────────────────────────────────────────────────
ec2_data = [
    {"id": "i-0a1b2c3d4e", "nombre": "web-prod-01",     "tipo": "t3.medium",  "estado": "running",  "region": "us-east-1", "ip_privada": "10.0.1.10", "vpc": "vpc-prod",   "version_ami": "ami-ubuntu-22.04", "ultima_actualizacion": "2025-01-15"},
    {"id": "i-0b2c3d4e5f", "nombre": "web-prod-02",     "tipo": "t3.medium",  "estado": "running",  "region": "us-east-1", "ip_privada": "10.0.1.11", "vpc": "vpc-prod",   "version_ami": "ami-ubuntu-22.04", "ultima_actualizacion": "2025-01-15"},
    {"id": "i-0c3d4e5f6a", "nombre": "api-server-01",   "tipo": "t3.large",   "estado": "running",  "region": "us-east-1", "ip_privada": "10.0.2.10", "vpc": "vpc-prod",   "version_ami": "ami-ubuntu-20.04", "ultima_actualizacion": "2024-08-10"},
    {"id": "i-0d4e5f6a7b", "nombre": "worker-01",       "tipo": "t3.small",   "estado": "stopped",  "region": "us-east-1", "ip_privada": "10.0.3.10", "vpc": "vpc-prod",   "version_ami": "ami-amazon-linux-2", "ultima_actualizacion": "2024-06-01"},
    {"id": "i-0e5f6a7b8c", "nombre": "bastion-host",    "tipo": "t2.micro",   "estado": "running",  "region": "us-east-1", "ip_privada": "10.0.0.5",  "vpc": "vpc-prod",   "version_ami": "ami-amazon-linux-2", "ultima_actualizacion": "2024-11-20"},
    {"id": "i-0f6a7b8c9d", "nombre": "staging-web",     "tipo": "t3.small",   "estado": "running",  "region": "us-west-2", "ip_privada": "10.1.1.10", "vpc": "vpc-staging","version_ami": "ami-ubuntu-22.04", "ultima_actualizacion": "2025-02-01"},
    {"id": "i-0a7b8c9d0e", "nombre": "dev-instance",    "tipo": "t2.micro",   "estado": "stopped",  "region": "us-west-2", "ip_privada": "10.1.2.10", "vpc": "vpc-dev",    "version_ami": "ami-ubuntu-20.04", "ultima_actualizacion": "2024-03-15"},
]

# ─── RDS: Bases de datos ───────────────────────────────────────────────────────
rds_data = [
    {"id": "db-prod-main",    "nombre": "prod-postgres",   "motor": "PostgreSQL", "version": "15.3", "estado": "available", "tipo": "db.t3.medium", "region": "us-east-1", "vpc": "vpc-prod",    "multi_az": True,  "almacenamiento_gb": 100, "ultima_actualizacion": "2025-01-20"},
    {"id": "db-prod-replica", "nombre": "prod-replica",    "motor": "PostgreSQL", "version": "15.3", "estado": "available", "tipo": "db.t3.medium", "region": "us-east-1", "vpc": "vpc-prod",    "multi_az": False, "almacenamiento_gb": 100, "ultima_actualizacion": "2025-01-20"},
    {"id": "db-analytics",    "nombre": "analytics-mysql", "motor": "MySQL",      "version": "8.0",  "estado": "available", "tipo": "db.t3.large",  "region": "us-east-1", "vpc": "vpc-prod",    "multi_az": False, "almacenamiento_gb": 500, "ultima_actualizacion": "2024-09-05"},
    {"id": "db-staging",      "nombre": "staging-postgres","motor": "PostgreSQL", "version": "14.8", "estado": "available", "tipo": "db.t3.small",  "region": "us-west-2", "vpc": "vpc-staging", "multi_az": False, "almacenamiento_gb": 50,  "ultima_actualizacion": "2024-07-12"},
]

# ─── Lambda: Funciones ────────────────────────────────────────────────────────
lambda_data = [
    {"nombre": "auth-validator",      "runtime": "Python 3.11", "estado": "Active", "region": "us-east-1", "memoria_mb": 256,  "timeout_s": 30,  "invocaciones_dia": 15420, "errores_dia": 12,  "ultima_actualizacion": "2025-02-10"},
    {"nombre": "payment-processor",   "runtime": "Node.js 20",  "estado": "Active", "region": "us-east-1", "memoria_mb": 512,  "timeout_s": 60,  "invocaciones_dia": 3210,  "errores_dia": 0,   "ultima_actualizacion": "2025-01-28"},
    {"nombre": "email-sender",        "runtime": "Python 3.10", "estado": "Active", "region": "us-east-1", "memoria_mb": 128,  "timeout_s": 15,  "invocaciones_dia": 8900,  "errores_dia": 45,  "ultima_actualizacion": "2024-10-15"},
    {"nombre": "report-generator",    "runtime": "Python 3.9",  "estado": "Active", "region": "us-east-1", "memoria_mb": 1024, "timeout_s": 300, "invocaciones_dia": 240,   "errores_dia": 3,   "ultima_actualizacion": "2024-06-20"},
    {"nombre": "image-resizer",       "runtime": "Node.js 18",  "estado": "Active", "region": "us-west-2", "memoria_mb": 512,  "timeout_s": 30,  "invocaciones_dia": 22100, "errores_dia": 88,  "ultima_actualizacion": "2024-08-05"},
    {"nombre": "data-sync",           "runtime": "Python 3.9",  "estado": "Inactive","region": "us-east-1","memoria_mb": 256,  "timeout_s": 120, "invocaciones_dia": 0,     "errores_dia": 0,   "ultima_actualizacion": "2023-11-30"},
]

# ─── VPC: Redes ───────────────────────────────────────────────────────────────
vpc_data = [
    {"id": "vpc-prod",    "nombre": "Production VPC",  "cidr": "10.0.0.0/16", "region": "us-east-1", "subnets": 6, "estado": "available", "internet_gateway": True},
    {"id": "vpc-staging", "nombre": "Staging VPC",     "cidr": "10.1.0.0/16", "region": "us-west-2", "subnets": 4, "estado": "available", "internet_gateway": True},
    {"id": "vpc-dev",     "nombre": "Development VPC", "cidr": "10.2.0.0/16", "region": "us-west-2", "subnets": 2, "estado": "available", "internet_gateway": False},
]

# ─── API Gateway ──────────────────────────────────────────────────────────────
api_data = [
    {"id": "api-001", "nombre": "REST API v2",       "tipo": "REST",      "estado": "ACTIVE",  "region": "us-east-1", "endpoint": "https://api.ejemplo.com/v2", "llamadas_dia": 48200, "latencia_ms": 145, "version": "2.1.0"},
    {"id": "api-002", "nombre": "Auth API",           "tipo": "REST",      "estado": "ACTIVE",  "region": "us-east-1", "endpoint": "https://auth.ejemplo.com",   "llamadas_dia": 21000, "latencia_ms": 89,  "version": "1.4.2"},
    {"id": "api-003", "nombre": "WebSocket Events",   "tipo": "WebSocket", "estado": "ACTIVE",  "region": "us-east-1", "endpoint": "wss://ws.ejemplo.com",       "llamadas_dia": 5600,  "latencia_ms": 22,  "version": "1.0.1"},
    {"id": "api-004", "nombre": "Internal Admin API", "tipo": "REST",      "estado": "ACTIVE",  "region": "us-west-2", "endpoint": "https://admin.ejemplo.com",  "llamadas_dia": 890,   "latencia_ms": 201, "version": "3.0.0"},
    {"id": "api-005", "nombre": "Legacy API v1",      "tipo": "REST",      "estado": "INACTIVE","region": "us-east-1", "endpoint": "https://api.ejemplo.com/v1", "llamadas_dia": 0,     "latencia_ms": 0,   "version": "1.9.9"},
]

# ─── Alertas ──────────────────────────────────────────────────────────────────
alertas_data = [
    {"severidad": "CRÍTICA", "componente": "email-sender (Lambda)",     "mensaje": "Tasa de errores > 0.5% en últimas 2 horas",            "tiempo": "Hace 25 min"},
    {"severidad": "CRÍTICA", "componente": "image-resizer (Lambda)",    "mensaje": "Tasa de errores elevada (88 errores/día)",             "tiempo": "Hace 1 hora"},
    {"severidad": "AVISO",   "componente": "api-server-01 (EC2)",       "mensaje": "AMI desactualizada: ubuntu-20.04 (disponible 22.04)", "tiempo": "Hace 3 días"},
    {"severidad": "AVISO",   "componente": "worker-01 (EC2)",           "mensaje": "Instancia detenida hace más de 30 días",              "tiempo": "Hace 6 días"},
    {"severidad": "AVISO",   "componente": "report-generator (Lambda)", "mensaje": "Runtime Python 3.9 llega a fin de soporte en 60 días","tiempo": "Hace 2 días"},
    {"severidad": "AVISO",   "componente": "data-sync (Lambda)",        "mensaje": "Función inactiva desde Nov 2023 — posible eliminación","tiempo": "Hace 10 días"},
    {"severidad": "INFO",    "componente": "db-analytics (RDS)",        "mensaje": "Versión MySQL 8.0 — actualización 8.1 disponible",    "tiempo": "Hace 5 días"},
    {"severidad": "INFO",    "componente": "Legacy API v1",             "mensaje": "API inactiva — considerar eliminación",               "tiempo": "Hace 15 días"},
]

# ─── Interrelaciones entre componentes ────────────────────────────────────────
relaciones = [
    ("REST API v2",       "auth-validator",    "Valida tokens JWT"),
    ("REST API v2",       "api-server-01",     "Enruta peticiones"),
    ("REST API v2",       "payment-processor", "Procesa pagos"),
    ("Auth API",          "auth-validator",    "Autenticación"),
    ("Auth API",          "prod-postgres",     "Lee usuarios"),
    ("api-server-01",     "prod-postgres",     "Lectura/escritura"),
    ("api-server-01",     "prod-replica",      "Solo lectura"),
    ("payment-processor", "prod-postgres",     "Registra pagos"),
    ("email-sender",      "analytics-mysql",   "Log de envíos"),
    ("report-generator",  "analytics-mysql",   "Lee métricas"),
    ("web-prod-01",       "REST API v2",       "Consume API"),
    ("web-prod-02",       "REST API v2",       "Consume API"),
    ("image-resizer",     "prod-postgres",     "Metadatos"),
    ("data-sync",         "analytics-mysql",   "Sincronización"),
]

# ─── Funciones helper ─────────────────────────────────────────────────────────
def get_ec2_df():       return pd.DataFrame(ec2_data)
def get_rds_df():       return pd.DataFrame(rds_data)
def get_lambda_df():    return pd.DataFrame(lambda_data)
def get_vpc_df():       return pd.DataFrame(vpc_data)
def get_api_df():       return pd.DataFrame(api_data)
def get_alertas():      return alertas_data
def get_relaciones():   return relaciones

def get_resumen():
    return {
        "ec2_total":       len(ec2_data),
        "ec2_running":     sum(1 for x in ec2_data    if x["estado"] == "running"),
        "rds_total":       len(rds_data),
        "lambda_total":    len(lambda_data),
        "lambda_activas":  sum(1 for x in lambda_data if x["estado"] == "Active"),
        "api_total":       len(api_data),
        "api_activas":     sum(1 for x in api_data    if x["estado"] == "ACTIVE"),
        "alertas_criticas":sum(1 for x in alertas_data if x["severidad"] == "CRÍTICA"),
        "alertas_aviso":   sum(1 for x in alertas_data if x["severidad"] == "AVISO"),
    }
