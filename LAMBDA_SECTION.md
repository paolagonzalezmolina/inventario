# ⚡ Sección Lambda - Documentación

## 📋 Descripción General

Nueva sección **"⚡ Lambda"** que te permite:
- Listar todas las funciones Lambda por región/cuenta
- Detectar problemas de replicación entre regiones
- Verificar etiquetado (CERT/PROD)
- Monitorear configuración y últimas actualizaciones

---

## 🎯 Dos Vistas Principales

### 1️⃣ **Tab: "📋 Lambda por región"**

**Selector:** Dropdown con todas las cuentas y regiones disponibles

**Datos mostrados por Lambda:**
- ✅ **Nombre** — Identificador de la función
- ✅ **Etiqueta** — 🟢 CERT, 🔵 PROD, o ⚪ SIN LABEL
- ✅ **Versión** — Número de versión
- ✅ **Runtime** — Lenguaje (Python, Node.js, etc)
- ✅ **Memoria** — MB asignados
- ✅ **Timeout** — Segundos máximos de ejecución
- ✅ **API Gateway** — Si está asociada a alguna API
- ✅ **Última Actualización** — Fecha de cambio
- ✅ **Estado** — ✅ Activa

**Métricas rápidas:**
```
┌─────────┬──────┬──────┬───────────┐
│ Total   │ CERT │ PROD │ Sin label │
├─────────┼──────┼──────┼───────────┤
│ 42      │ 15   │ 25   │ 2         │
└─────────┴──────┴──────┴───────────┘
```

**Caché:**
- Primera carga: ~20s (AWS)
- Siguientes: ⚡ Instantáneo (local)

---

### 2️⃣ **Tab: "🔄 Comparación Producción (Virginia ↔ Ohio)"**

**Análisis especial para `afex-prod`:**

Compara Lambdas con etiqueta CERT o PROD entre:
- 🟣 **Virginia** (us-east-1)
- 🔷 **Ohio** (us-east-2)

**Métricas mostradas:**

```
┌────────────────┬──────────────┬─────────────┬──────────────┐
│ Virginia CERT+ │ Ohio CERT+   │ Replicación │ Diferencias  │
│ PROD: 40       │ PROD: 40     │ 100% (40)   │ 0 ⚠️ Requiere│
├────────────────┼──────────────┼─────────────┼──────────────┤
│ vs            │ vs            │             │              │
└────────────────┴──────────────┴─────────────┴──────────────┘
```

---

## 🔍 Análisis de Replicación

### ✅ Sincronizado
Si Virginia y Ohio tienen **exactamente** la misma cantidad de Lambda con CERT/PROD:

```
✅ TODAS LAS LAMBDAS REPLICADAS CORRECTAMENTE
Virginia y Ohio están en sincronía
```

### ⚠️ Desincronización
Si hay diferencias:

```
🔴 Solo en Virginia (3):
  - api-handler-v2
  - webhook-processor
  - auth-validator

🔴 Solo en Ohio (1):
  - legacy-migrator

⚠️ DESINCRONIZACIÓN DETECTADA
Se recomienda revisar y replicar las Lambdas faltantes
```

---

## 📊 Tabla Detallada

Muestra todas las Lambdas replicadas en ambas regiones:

```
✅ api-auth
✅ api-gateway-wrapper
✅ event-processor
✅ data-transformer
...
```

---

## 🏷️ Sistema de Etiquetado

**Las Lambdas se clasifican automáticamente:**

1. **🟢 CERT** — Si tiene "CERT" en el nombre o etiquetas
   - Ejemplo: `auth-cert`, `validation-CERT`

2. **🔵 PROD** — Si tiene "PROD" en el nombre o etiquetas
   - Ejemplo: `api-prod`, `PROD-handler`

3. **⚪ SIN LABEL** — Si no tiene ni CERT ni PROD
   - Ejemplo: `test-function`, `dev-processor`

---

## 💾 Caché Local

**Estrategia igual a otras secciones:**

```
Primera carga Lambda (Virginia): ~20s (AWS)
├─ Guarda en caché local
└─ Proxima vez: ⚡ <100ms

Cambiar a Ohio: ~20s (AWS primera vez)
├─ Guarda en caché local
└─ Segunda vez en Ohio: ⚡ <100ms

Comparación Producción: ~30-40s (primero)
├─ Carga Virginia + Ohio
├─ Compara automáticamente
└─ Próxima vez: ⚡ <100ms
```

**Claves de caché:**
- `lambda_df_afex-prod_us-east-1` — Lambdas Virginia PROD
- `lambda_df_afex-prod_us-east-2` — Lambdas Ohio PROD
- `lambda_comparacion_prod` — Comparación PROD

---

## 🚨 Casos de Uso

### Caso 1: Verificar replicación
1. Abre **"⚡ Lambda"**
2. Ve a tab **"🔄 Comparación Producción"**
3. Verifica si está **"100% replicado"** o si hay **diferencias**

### Caso 2: Auditoría de etiquetado
1. Selecciona región en tab **"📋 Lambda por región"**
2. Revisa columna **"Etiqueta"**
3. Busca Lambdas con **"⚪ SIN LABEL"** que deberían tener CERT/PROD

### Caso 3: Investigar Lambda específica
1. En tab **"📋 Lambda por región"**
2. Busca en la tabla por nombre
3. Revisa: Runtime, Memoria, Timeout, API asociada
4. Verifica última actualización

---

## ⚡ Velocidad Esperada

| Acción | Primera Vez | Segunda Vez |
|--------|------------|------------|
| **Ver Lambda Virginia** | ~20s | ⚡ <100ms |
| **Cambiar a Ohio** | ~20s | ⚡ <100ms |
| **Comparación PROD** | ~40s | ⚡ <100ms |
| **Tabla se carga** | ~5s | ⚡ <100ms |

---

## 📥 Instalación

```powershell
Copy-Item app_updated.py app.py -Force
Copy-Item conector_aws.py conector_aws.py -Force
streamlit run app.py
```

---

## 🔧 Información Técnica

**Función principal:** `get_lambda_df(perfil, region)`
- Carga Lambdas con caché local
- Detecta API Gateway asociadas (simplificado)
- Extrae etiquetas y clasifica

**Función especial:** `comparar_lambdas_produccion()`
- Solo para cuenta `afex-prod`
- Compara us-east-1 vs us-east-2
- Solo cuenta CERT + PROD

---

¡Listo para monitorear tus Lambdas! 🚀
