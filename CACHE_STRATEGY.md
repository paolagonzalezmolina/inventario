# 🚀 Estrategia de Caché Local - Dashboard Optimizado

## ¿Cómo funciona ahora?

El Dashboard está optimizado para usar **caché local persistente** en lugar de llamar a AWS cada vez.

---

## 📊 Estrategia por Sección

### 1️⃣ **Dashboard - "Todas las cuentas"**
```
Primera carga: 
  → Sin datos en caché
  → Muestra: "No hay datos cacheados"
  → Usuario hace click en 🔄 Refresh
  
Refresh (AWS):
  → Carga 4 cuentas desde AWS (~60s)
  → Guarda en caché local
  
Siguientes cargas:
  → Trae del caché local ⚡ INSTANTÁNEO
```

### 2️⃣ **Dashboard - "Cuenta actual"**
```
Primera carga:
  → Intenta caché local
  → Si no existe → carga de AWS (~30s)
  → Guarda en caché local
  
Siguientes cargas:
  → Trae del caché local ⚡ INSTANTÁNEO
```

### 3️⃣ **Infraestructura AWS**
```
Primera selección de región:
  → Intenta caché local
  → Si no existe → carga de AWS (~10-20s)
  → Guarda en caché local
  
Cambiar a otra región y volver:
  → Trae del caché local ⚡ INSTANTÁNEO
```

### 4️⃣ **S3 Buckets, IAM, Multi-región, Multi-cuenta**
```
Misma estrategia:
  → Caché local primero (instantáneo)
  → AWS solo si no hay caché
  → Guarda resultado en caché
```

---

## ⚡ Velocidad Esperada

| Acción | Primera Vez | Segunda Vez |
|--------|------------|------------|
| Acceder Dashboard | ~60s (AWS) | <100ms ⚡ |
| Cambiar vista | <5ms | <5ms ⚡ |
| Cambiar región | ~10-20s (AWS) | <100ms ⚡ |
| Scroll/Interacción | <5ms | <5ms ⚡ |

---

## 🔄 ¿Cuándo se actualiza?

**Automáticamente:**
- El caché vence después de **1 día**
- Luego de 1 día, la siguiente carga traerá de AWS nuevamente

**Manualmente:**
- Botón 🔄 **Refresh** (sidebar) → Recarga de AWS todas las cuentas
- Botón 🗑️ **Limpiar caché** (sidebar) → Borra todo el caché local

---

## 📁 Dónde se guarda el caché

**Windows:**
```
C:\Users\[TuUsuario]\.cache\aws_inventory\
```

**Linux/Mac:**
```
~/.cache/aws_inventory/
```

Archivos:
- `resumen_afex-des.pkl` → Datos de afex-des
- `resumen_afex-prod.pkl` → Datos de afex-prod
- `resumen_afex-peru.pkl` → Datos de afex-peru
- `resumen_afex-digital.pkl` → Datos de afex-digital
- `df_ec2_afex-prod_us-east-1.pkl` → Tablas por tipo/región
- `metadata.json` → Información de timestamps/estado

---

## 💾 Ejemplo de Flujo

### **Primera ejecución (sin datos)**

```
1. Abro el app
   ↓
2. Voy a Dashboard → "Todas las cuentas"
   ↓
3. Veo: "No hay datos cacheados"
   ↓
4. Hago click en 🔄 Refresh
   ↓
5. Carga desde AWS (~60 segundos)
   ↓
6. Guarda en caché local
   ↓
7. Muestra datos en pantalla
```

### **Segunda ejecución (con caché)**

```
1. Abro el app
   ↓
2. Voy a Dashboard → "Todas las cuentas"
   ↓
3. Instantáneamente muestra datos (del caché local) ⚡
   ↓
4. No espera a AWS
   ↓
5. Si el caché expira (>1 día), buscará en AWS nuevamente
```

### **Cambio de región**

```
1. Estoy en "Cuenta actual" - Virginia
   ↓
2. Cambio selector a "Ohio"
   ↓
3. Primera vez Ohio:
      → Intenta caché local
      → No existe
      → Carga de AWS (~10-20s)
      → Guarda en caché
   ↓
4. Vuelvo a cambiar a "Ohio" después:
      → Trae del caché local
      → INSTANTÁNEO ⚡
```

---

## 🎯 Resumen

✅ **Objetivo logrado:**
- Cada click en la página usa datos **locales o en caché**
- NO hay llamadas a AWS innecesarias
- Solo llama a AWS si:
  - Es la primera vez que accedes a esos datos
  - El caché expiró (>1 día)
  - Haces click en 🔄 **Refresh** voluntariamente

---

## 🚀 Instalación

```powershell
# Descarga el archivo
# Reemplaza el anterior
Copy-Item app_updated.py app.py -Force

# Ejecuta
streamlit run app.py
```

**Primera carga:** Espera el Refresh (~60s)  
**Siguientes cargas:** ⚡⚡⚡ LIGHTNING FAST

---

## 📝 Notas

- El caché local se guarda en `.cache/aws_inventory/` (carpeta oculta)
- Puedes limpiar manualmente con 🗑️ en el sidebar
- El caché es **persistente** entre sesiones (no se borra al cerrar la app)
- Cada componente nuevo que agregues en AWS aparecerá después del próximo Refresh

¡Disfruta la velocidad! ⚡
