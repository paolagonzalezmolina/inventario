# ☁️ Inventario AWS — Guía de instalación

## Paso 1 — Instalar dependencias
Abre la terminal (o símbolo del sistema en Windows) y ejecuta:

```
pip install streamlit pandas plotly boto3
```

## Paso 2 — Correr la aplicación
Desde la carpeta donde están los archivos:

```
streamlit run app.py
```

Se abrirá automáticamente en tu navegador en http://localhost:8501

---

## ¿Cuáles son los archivos?

| Archivo | Para qué sirve |
|---|---|
| `app.py` | La aplicación principal |
| `datos_ejemplo.py` | Datos de ejemplo (sin AWS) |
| `requirements.txt` | Lista de librerías a instalar |

---

## Paso 3 (cuando tengas credenciales AWS)

1. En `app.py`, busca la línea:
   ```python
   MODO_DEMO = True
   ```
   y cámbiala a:
   ```python
   MODO_DEMO = False
   ```

2. Configura tus credenciales:
   ```
   aws configure
   ```
   Te pedirá: Access Key ID, Secret Access Key, región (ej: us-east-1)

¡Eso es todo! La app se conectará automáticamente a tu cuenta AWS.
