# ☁️ Inventario AWS — Guía actualizada

## ✨ Nuevas características (v2.0)

- ✅ **Dashboard** con estado del caché y alertas
- ✅ **Caché local persistente** en `~/.cache/aws_inventory/`
- ✅ **Detección de cambios** automática cada 1 día
- ✅ **Carga rápida** usando datos locales
- ✅ **Fallback inteligente** si falla AWS

## Paso 1 — Instalar dependencias

Abre la terminal y ejecuta:

```bash
pip install streamlit pandas plotly boto3
```

## Paso 2 — Estructura de archivos

Debes tener estos archivos en la misma carpeta:

```
.
├── app_updated.py          # (renombra a app.py)
├── cache_manager.py        # NUEVO - gestión de caché
├── conector_aws.py         # ACTUALIZADO
├── datos_ejemplo.py
├── flujos_interactivos.py
└── requirements.txt
```

## Paso 3 — Configurar AWS (opcional)

Si quieres conectar a una cuenta AWS real:

```bash
aws configure --profile inventario
```

Te pedirá:
- **Access Key ID**: Tu clave de acceso AWS
- **Secret Access Key**: Tu clave secreta
- **Default region**: `us-east-1` (o tu región)
- **Default output format**: `json`

## Paso 4 — Ejecutar la aplicación

```bash
streamlit run app_updated.py
```

La app se abrirá en **http://localhost:8501**

## 🎯 Modo Demo vs Modo Real

### Modo Demo (sin AWS)
```python
# En app_updated.py, línea 17:
MODO_DEMO = True
```

Usa datos de ejemplo. **No requiere credenciales AWS.**

### Modo Real (con AWS)
```python
# En app_updated.py, línea 17:
MODO_DEMO = False
```

**Requiere:** `aws configure --profile inventario`

## 📁 Sistema de Caché

### ¿Dónde se guardan los datos?

```
~/.cache/aws_inventory/
├── metadata.json      # Timestamps y hashes
├── ec2_df.pkl
├── rds_df.pkl
├── lambda_df.pkl
├── vpc_df.pkl
├── s3_df.pkl
└── alertas.pkl
```

### ¿Cómo funciona?

1. **Primera carga**: Descarga datos de AWS y los guarda localmente
2. **Siguientes cargas**: Lee del caché local (⚡ muy rápido)
3. **Después de 1 día**: Verifica cambios en AWS automáticamente
4. **Si detecta cambios**: Actualiza el caché y muestra alerta en Dashboard

### Controles en el Sidebar

- **🔄 Refresh**: Fuerza descarga de AWS ahora
- **🗑️ Limpiar caché**: Borra todos los datos locales

## 📊 Dashboard

La nueva sección **Dashboard** muestra:

1. **Estado del caché**
   - Número de archivos cacheados
   - Tamaño total en MB
   - Última actualización de cada servicio

2. **Resumen de infraestructura**
   - Instancias EC2
   - BD RDS
   - Funciones Lambda
   - VPCs

3. **Alertas activas**
   - Alertas críticas (🔴)
   - Avisos (🟡)
   - Información (ℹ️)

## 🔄 Flujo de datos

```
AWS (boto3)
    ↓
cache_manager (verifica si está fresco)
    ↓
Si fresco: Retorna del caché local ⚡
Si viejo:  Descarga de AWS + actualiza caché
    ↓
Streamlit (muestra en UI)
```

## ⚙️ Configuración avanzada

### Cambiar ubicación del caché

En `cache_manager.py`, línea 7:

```python
CACHE_DIR = os.path.expanduser("~/mi_cache_personalizado")
```

### Cambiar intervalo de actualización (1 día)

En `cache_manager.py`, método `get()`:

```python
is_fresh = (datetime.now() - last_update) < timedelta(hours=6)  # Cada 6 horas
```

### Agregar más cuentas AWS

En `conector_aws.py`, línea 26:

```python
PERFILES = {
    "afex-des":      {...},
    "afex-prod":     {...},
    "afex-peru":     {...},
    "afex-digital":  {...},
    "mi-cuenta":     {"perfil": "inventario-e", "region": "us-east-1", "regiones": ["us-east-1"]},
}
```

Luego: `aws configure --profile inventario-e`

## 🚀 Solución de problemas

### "No se encontraron credenciales AWS"

```bash
# Verifica el perfil
aws configure --profile inventario

# Lista perfiles configurados
aws configure list --profile inventario
```

### El caché está muy viejo

```bash
# Fuerza refresh desde el sidebar (botón 🔄)
# O borra manualmente:
rm -rf ~/.cache/aws_inventory/
```

### La app se demora mucho

1. Asegúrate de estar en modo caché (no fuerces refresh cada vez)
2. Verifica conexión a AWS (si la primera carga es lenta)
3. Reduce el número de regiones/cuentas si es muy grande

## 📝 Cambios desde v1.0

| Característica | v1.0 | v2.0 |
|---|---|---|
| Caché | Solo en memoria | ✅ Persistente local |
| Actualización | Manual | ✅ Automática cada 1 día |
| Detección cambios | No | ✅ Sí, con hashes |
| Dashboard | No | ✅ Nuevo |
| Fallback si falla AWS | No | ✅ Sí |
| Velocidad de carga | Lenta | ⚡ Rápida |

## 📚 Referencias

- [Documentación Streamlit](https://docs.streamlit.io)
- [Boto3 - AWS SDK](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [AWS CLI](https://docs.aws.amazon.com/cli/)

---

**¿Problemas?** Revisa los logs:

```bash
# Ubicación de caché
ls -lah ~/.cache/aws_inventory/

# Ver contenido de metadata
cat ~/.cache/aws_inventory/metadata.json
```
