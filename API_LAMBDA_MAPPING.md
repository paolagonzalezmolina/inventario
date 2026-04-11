# 🔗 Mapeo API ↔ Lambda - Documentación

## 📋 ¿Qué es el mapeo API ↔ Lambda?

Es una visualización que te muestra **exactamente** qué APIs están integradas con qué Lambdas.

Por cada integración, ves:
- **API Gateway** — Nombre de la API
- **Método HTTP** — GET, POST, PUT, DELETE, etc
- **Ruta** — Path de la API (ej: `/users`, `/orders/{id}`)
- **Función Lambda** — Nombre de la Lambda conectada
- **Tipo Integración** — AWS_PROXY, AWS, HTTP, etc
- **Estado** — ✅ Conectada

---

## 🎯 Uso Típico

### Caso 1: "¿Qué Lambda ejecuta mi API?"
1. Abre **🔌 API Gateway**
2. Ve a tab **"🔗 Conexiones API ↔ Lambda"**
3. Busca tu API en la tabla
4. Ves exactamente qué Lambda se ejecuta

**Ejemplo:**
```
API: order-api
├─ POST /orders     → order-handler
├─ GET /orders      → order-getter
└─ DELETE /orders   → order-deleter
```

### Caso 2: "¿Qué APIs usan mi Lambda?"
1. Ve la tabla detallada
2. Busca tu Lambda en columna "Función Lambda"
3. Ves todas las rutas que la llaman

**Ejemplo:**
```
Lambda: auth-validator
↑
├─ auth-api:     POST /login
├─ user-api:     POST /register
└─ admin-api:    GET /verify
```

---

## 📊 Tres Tablas Disponibles

### 1️⃣ Tabla de Integraciones (Detallada)
```
API Gateway  | Método | Ruta           | Función Lambda    | Tipo Integración | Estado
─────────────┼────────┼────────────────┼───────────────────┼──────────────────┼────────
order-api    | POST   | /orders        | order-handler     | AWS_PROXY        | ✅
user-api     | GET    | /users/{id}    | user-getter       | AWS_PROXY        | ✅
auth-api     | POST   | /login         | auth-validator    | AWS              | ✅
```

**Qué ves:**
- Todas las conexiones API → Lambda
- Método HTTP específico
- Ruta exacta
- Tipo de integración

---

### 2️⃣ Resumen por API
```
API Gateway  | Lambdas Conectadas           | Métodos
─────────────┼──────────────────────────────┼────────
order-api    | order-handler, order-getter  | 3
user-api     | user-getter, user-creator    | 2
auth-api     | auth-validator               | 1
```

**Qué ves:**
- Cuántas Lambdas usa cada API
- Todas las Lambdas listadas
- Cantidad total de métodos

---

### 3️⃣ Resumen por Lambda
```
Función Lambda     | APIs que la usan        | Métodos
───────────────────┼─────────────────────────┼────────
order-handler      | order-api               | 2
auth-validator     | auth-api, user-api      | 3
user-getter        | user-api, admin-api     | 2
```

**Qué ves:**
- Cuántas APIs llaman a cada Lambda
- Todas las APIs listadas
- Cantidad total de métodos

---

## ⚡ Velocidad

| Escenario | Velocidad |
|-----------|-----------|
| **Primera carga** | ~10-15s (analiza todas las integraciones) |
| **Siguiente carga (caché)** | ⚡ <100ms |
| **Cambiar región** | ~10-15s (primera), ⚡ <100ms (luego) |

---

## 🔍 Ejemplo Real

Supongamos que tienes esto en AWS:

```
📦 API Gateway: customer-api
├─ GET /customers        → GetCustomerList (Lambda)
├─ GET /customers/{id}   → GetCustomer (Lambda)
├─ POST /customers       → CreateCustomer (Lambda)
└─ PUT /customers/{id}   → UpdateCustomer (Lambda)

📦 API Gateway: order-api
├─ GET /orders           → GetOrders (Lambda)
├─ POST /orders          → CreateOrder (Lambda) ← Llama a GetCustomer internamente
└─ DELETE /orders/{id}   → DeleteOrder (Lambda)
```

Al abrir la sección, verás:

**Tabla de Integraciones:**
```
customer-api | GET    | /customers        | GetCustomerList   | ✅
customer-api | GET    | /customers/{id}   | GetCustomer       | ✅
customer-api | POST   | /customers        | CreateCustomer    | ✅
customer-api | PUT    | /customers/{id}   | UpdateCustomer    | ✅
order-api    | GET    | /orders           | GetOrders         | ✅
order-api    | POST   | /orders           | CreateOrder       | ✅
order-api    | DELETE | /orders/{id}      | DeleteOrder       | ✅
```

**Resumen por API:**
```
customer-api | GetCustomerList, GetCustomer, CreateCustomer, UpdateCustomer | 4
order-api    | GetOrders, CreateOrder, DeleteOrder                          | 3
```

**Resumen por Lambda:**
```
GetCustomerList  | customer-api      | 1
GetCustomer      | customer-api      | 1
CreateCustomer   | customer-api      | 1
UpdateCustomer   | customer-api      | 1
GetOrders        | order-api         | 1
CreateOrder      | order-api         | 1
DeleteOrder      | order-api         | 1
```

---

## 🛠️ Detalles Técnicos

**Función usada:** `get_api_lambda_mapping(perfil, region)`

**Lo que hace:**
1. Lista todas las APIs REST
2. Por cada API, obtiene sus recursos
3. Por cada recurso, obtiene los métodos HTTP
4. Por cada método, obtiene la integración
5. Extrae si está conectada a Lambda
6. Retorna un DataFrame con todas las conexiones

**Extracción de nombre Lambda:**
- Analiza el URI de la integración
- Busca el patrón `arn:aws:lambda:...function:NOMBRE`
- Extrae solo el nombre

---

## 📥 Instalación

```powershell
Copy-Item app_updated.py app.py -Force
Copy-Item conector_aws.py conector_aws.py -Force
streamlit run app.py
```

---

## ✨ Casos de Uso Avanzados

### Auditoría de Dependencias
¿Cuántas APIs dependen de una Lambda crítica?
→ Ve "Resumen por Lambda" y busca tu Lambda crítica

### Impacto de Cambios
¿Qué APIs se rompen si actualizo una Lambda?
→ Ve "Resumen por Lambda" para saber el alcance

### Documentación Automática
Necesitas documentar qué Lambda ejecuta cada endpoint?
→ Exporta la tabla de integraciones

### Refactoring de APIs
¿Puedo eliminar esta integración sin romper nada?
→ Busca en "Resumen por Lambda" si algo más depende de ella

---

¡Listo para auditar tus integraciones! 🔗⚡
