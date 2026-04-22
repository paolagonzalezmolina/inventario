# 📊 AWS Inventory - Documentación Completa

**Aplicación Streamlit para inventario AWS multi-cuenta en tiempo real.**

---

## 📋 Tabla de Contenidos

1. [Descripción General](#descripción-general)
2. [Requisitos](#requisitos)
3. [Instalación](#instalación)
4. [Arquitectura](#arquitectura)
5. [Funcionalidades](#funcionalidades)
6. [Uso](#uso)
7. [Estructura de Archivos](#estructura-de-archivos)
8. [Estado Actual](#estado-actual)
9. [Solución de Problemas](#solución-de-problemas)

---

## Descripción General

### ¿Qué hace?
Herramienta de inventario para AWS que descarga en tiempo real:
- **Recursos por región:** EC2, RDS, VPC, Lambda, API Gateway
- **Recursos globales:** S3, IAM Users, CloudFront, Cognito
- **Multi-cuenta:** Gestiona 4 cuentas AWS simultáneamente
- **Caché inteligente:** No redescarga si está fresco (TTL 7 días)
- **Descarga paralela:** ThreadPoolExecutor de 4-8 threads

### Tecnología
```
Frontend: Streamlit (Python)
Backend: AWS boto3 (EC2, RDS, S3, IAM, etc.)
Caché: pickle en ~/.cache/aws_inventory/
Export: Excel con openpyxl
```

---

## Requisitos

### Sistema
- Python 3.9+
- Windows/Mac/Linux
- Credenciales AWS configuradas (boto3)

### Dependencias
```bash
streamlit==1.28.1       # UI web
pandas==2.1.3           # DataFrames
boto3==1.34.45          # AWS SDK
openpyxl==3.1.5         # Excel export
plotly==5.18.0          # Gráficos
python-dateutil==2.8.2  # Manejo de fechas
pytz==2023.3            # Timezones
```

---

## Instalación

### 1️⃣ Clonar/Descargar proyecto
```bash
cd ~/Documents/inventario
```

### 2️⃣ Crear entorno virtual (recomendado)
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3️⃣ Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4️⃣ Configurar AWS
Asegúrate de tener perfiles boto3 configurados:
```bash
# ~/.aws/credentials
[inventario]
aws_access_key_id = ...
aws_secret_access_key = ...

[inventario-b]
aws_access_key_id = ...
aws_secret_access_key = ...
```

### 5️⃣ Ejecutar
```bash
streamlit run app.py
```

Se abrirá en `http://localhost:8501`

---

## Arquitectura

### Flujo de Datos
```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit (UI)                           │
│  - Dashboard (Cuenta Actual / Todas las Cuentas)           │
│  - Infraestructura AWS (dropdown 14 servicios)             │
└────────────────┬────────────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
    ▼                         ▼
┌─────────────┐      ┌──────────────────┐
│  app.py     │      │ download_engine  │
│  (UI)       │      │ (descarga)       │
└─────────────┘      └────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
              ┌─────────────┐   ┌──────────────┐
              │conector_aws │   │cache_manager │
              │(boto3)      │   │(pickle)      │
              └─────────────┘   └──────────────┘
                    │                   │
                    └───────────┬───────┘
                                ▼
                        ~/.cache/aws_inventory/
                        ├── discovery.json
                        ├── metadata.json
                        └── by_region_account/
                            ├── afex-des_us-east-1/
                            ├── afex-prod_us-east-1/
                            └── ...
```

### Módulos

| Archivo | Responsabilidad |
|---------|-----------------|
| `app.py` | UI Streamlit (2 páginas, tabs, métricas) |
| `download_engine.py` | Descarga paralela, orquestación |
| `conector_aws.py` | Conexión a AWS, 7 servicios |
| `cache_manager.py` | Persistencia, hash, compare_and_update |
| `export_to_excel.py` | Generación de Excel |
| `config.py` | PERFILES de cuentas/regiones |
| `debug_aws_data.py` | Script diagnóstico |

---

## Funcionalidades

### 📊 Dashboard Global

#### Pestaña: "Cuenta Actual"
- **Métricas:** 14 servicios en grid 4 columnas
- **Estado:** ✅ Fresco / ⚠️ Viejo / ❌ Sin datos
- **Selectores:** Cuenta AWS + Región (sidebar)

#### Pestaña: "Todas las Cuentas"
- **Tabla comparativa:** EC2, RDS, VPC, S3, Lambda, API, etc.
- **Métricas globales:** 15 servicios
- **Gráfico de barras:** Distribución por tipo
- **Botón Excel:** Descarga inventario completo

### 📈 Infraestructura AWS

**Dropdown con 14 opciones:**
```
EC2 (Servidores)
RDS (Bases de datos)
VPC (Redes)
S3 (Buckets) - Global
IAM Users - Global
⚡ Lambda (Funciones)
🔌 API Gateway
(+ CloudFront, Cognito, etc.)
```

**Por recurso:**
- ✅ Tabla con todos los datos
- ✅ Gráfico específico (ej: EC2 por estado, RDS por motor)
- ✅ Manejo robusto de NoneType

### ⬇️ Descarga Paralela

- **4-8 threads simultáneos**
- **Descarga inteligente:** Compara hash, solo sobrescribe si cambió
- **Velocidad:** ~50s primera vez, ~10-15s sin cambios
- **Logging detallado:** Ve exactamente qué descarga

**Estados:**
- ✅ `new` - Primera descarga
- 📈 `updated` - Datos cambiaron
- ✅ `unchanged` - Sin cambios, no sobrescribe
- ⚠️ `partial` - Algunos servicios fallaron
- ❌ `failed` - Descarga completa falló

### 💾 Caché Inteligente

```
Estructura:
~/.cache/aws_inventory/
├── discovery.json          # Regiones por cuenta
├── metadata.json           # Índice central
└── by_region_account/
    ├── afex-des_us-east-1/
    │   ├── ec2.pkl         # DataFrame comprimido
    │   ├── rds.pkl
    │   ├── ec2_timestamp.json
    │   └── ...
    └── afex-prod_us-east-2/
        ├── s3.pkl         # Global (1 por cuenta)
        └── ...
```

**TTL:** 7 días (luego marca como "viejo")

**Hash:** SHA256 basado en:
- Shape del DataFrame
- Nombres de columnas
- Primeras 100 filas

### 📥 Export a Excel

**Genera:**
- ✅ Pestaña "Resumen" (totales por cuenta)
- ✅ Pestaña "EC2" (todas las instancias)
- ✅ Pestaña "RDS" (todas las BD)
- ✅ Pestaña "VPC" (todas las redes)
- ✅ Pestaña "S3" (todos los buckets)
- ✅ Pestaña "IAM Users" (todos los usuarios)

**Características:**
- Estilos automáticos (colores, bordes)
- Columnas ajustadas al contenido
- Sin timezones (compatible con Excel)
- Nombres de columna ordenados

---

## Uso

### Scenario 1: Descarga Inicial

```
1. Click: "🔄 Descargar Todo"
   └─ Esperar 50 segundos
   └─ Ver: "✅ 8 completadas, 0 fallidas"

2. Verificar:
   └─ Dashboard → Cuenta Actual → Métricas 
   └─ Debe mostrar EC2, RDS, VPC, Lambda, etc.

3. Exportar:
   └─ Dashboard → Todas las Cuentas
   └─ Click: "📥 Descargar Excel"
   └─ Abre diálogo, descarga inventario_aws.xlsx
```

### Scenario 2: Actualización (sin cambios)

```
1. Click: "🔄 Descargar Todo"
   └─ Esperar 10-15 segundos
   └─ Ver: "✅ 8 completadas, 0 fallidas"

2. Nota:
   └─ Datos en caché NO se sobrescribieron
   └─ (hash = hash anterior)
   └─ Métricas dicen "✅ Fresco"
```

### Scenario 3: Limpiar Caché

```
1. Click: "🗑️ Limpiar Caché"
   └─ Esperar a: "✅ Caché limpiado"

2. Click: "🔄 Descargar Todo"
   └─ Descarga nuevamente todo
   └─ Como descarga inicial
```

### Scenario 4: Ver Recurso Específico

```
1. Cambiar Cuenta/Región (sidebar)
2. Click: "📈 Infraestructura AWS"
3. Dropdown: Seleccionar "Lambda (Funciones)"
4. Ver:
   └─ Métrica: "⚡ Lambda: 225 ✅ Fresco"
   └─ Tabla: Todas las funciones Lambda
   └─ (Gráfico si aplica)
```

---

## Estructura de Archivos

```
~/Documents/inventario/
├── app.py                    # UI Streamlit principal
├── download_engine.py        # Descarga paralela
├── conector_aws.py          # Conexión a AWS
├── cache_manager.py         # Caché inteligente
├── config.py                # PERFILES (cuentas/regiones)
├── export_to_excel.py       # Generador Excel
├── debug_aws_data.py        # Script diagnóstico
├── requirements.txt         # Dependencias
├── resumen_aplicacion.md    # Este archivo
└── .aws/
    └── credentials          # Perfiles boto3
```

---

## Estado Actual

### ✅ Completado

- [x] Descarga paralela (ThreadPoolExecutor 4 threads)
- [x] Caché inteligente con hash SHA256
- [x] Dashboard con 2 tabs (Cuenta Actual / Todas)
- [x] 14 servicios AWS (EC2, RDS, VPC, S3, IAM, Lambda, API GW, etc.)
- [x] Página Infraestructura AWS con dropdown
- [x] Export a Excel con estilos
- [x] Eliminación de timezones (Excel compatible)
- [x] Manejo robusto de NoneType/errores
- [x] Método clear() en cache_manager
- [x] Logs detallados

### 📊 Servicios Descargados

| Tipo | Región | Global | Función |
|------|--------|--------|---------|
| EC2 | ✅ | - | get_ec2_df |
| RDS | ✅ | - | get_rds_df |
| VPC | ✅ | - | get_vpc_df |
| Lambda | ✅ | - | get_lambda_df |
| API Gateway | ✅ | - | get_api_gateway_df |
| S3 | - | ✅ | get_s3_df |
| IAM Users | - | ✅ | get_iam_users_df |

### 📋 Servicios No Implementados

- CloudFormation (mencionado pero no en conector_aws)
- SSM, KMS, DynamoDB, SQS (mencionados pero no implementados)
- CloudFront, Cognito (mencionados pero no implementados)

---

## Solución de Problemas

### ❌ "Discovery incompleto"

**Causa:** Función discovery fallaba por conexión AWS

**Solución:** Removida completamente, usa PERFILES directo

**Status:** ✅ Resuelto en v2

---

### ❌ "KeyError: 'completed'"

**Causa:** Estructura de resultado inconsistente en download_all_parallel

**Solución:** Agregada validación en app.py con .get() y valores por defecto

**Status:** ✅ Resuelto

---

### ❌ "NoneType object has no attribute 'replace'"

**Causa:** Datos corrompidos en caché o None en DataFrame

**Solución:** Validación ultra-robusta en infraestructura AWS

**Status:** ✅ Resuelto

---

### ❌ "Excel does not support timezones"

**Causa:** Columnas datetime con tzinfo=UTC

**Solución:** Función _remove_timezones() mejorada en export_to_excel.py

**Status:** ✅ Resuelto

---

### ❌ "ImportError: cannot import name 'get_cloudformation_df'"

**Causa:** Importé funciones que no existen en conector_aws

**Solución:** Eliminar imports de servicios no implementados

**Status:** ✅ Resuelto

---

## Próximos Pasos (Futuro)

- [ ] Implementar CloudFormation, SSM, KMS, DynamoDB, SQS
- [ ] Historial de cambios (quién modificó qué cuándo)
- [ ] APScheduler para sincronización automática (lunes 8am)
- [ ] Visualización de relaciones EC2↔Lambda
- [ ] API REST para acceso programático
- [ ] Alertas por cambios críticos
- [ ] Búsqueda/filtrado avanzado

---

## Contacto / Notas

**Última actualización:** 21 Abril 2026

**Version:** 2.0 (Simplificada, sin Discovery)

**Estado:** Producción (7 servicios AWS funcionales)

---

## Licencia

Propiedad de [Tu Empresa/Nombre]

---

## Apéndice: Comandos Útiles

### Ver caché
```bash
python3 << 'EOF'
from cache_manager import cache_manager
data, fresh, exists = cache_manager.get('afex-prod', 'us-east-1', 'ec2')
print(f"Existe: {exists}")
print(f"Fresco: {fresh}")
print(f"Filas: {len(data) if exists else 0}")
EOF
```

### Limpiar caché desde terminal
```bash
python3 << 'EOF'
from cache_manager import cache_manager
cache_manager.clear()
print("✅ Caché limpiado")
EOF
```

### Verificar AWS
```bash
python debug_aws_data.py
```

### Ejecutar en producción
```bash
streamlit run app.py --logger.level=warning --client.showErrorDetails=false
```

---

**¡Listo para usar!** 🚀
