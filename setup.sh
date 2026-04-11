#!/bin/bash
"""
setup.sh - Script de instalación rápida
Ejecuta: bash setup.sh
"""

echo "☁️  AWS Inventory Setup v2.0"
echo "===================================="
echo ""

# Detectar SO
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PYTHON_CMD="python3"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    PYTHON_CMD="python3"
elif [[ "$OSTYPE" == "msys" ]]; then
    PYTHON_CMD="python"
else
    PYTHON_CMD="python"
fi

echo "1️⃣  Verificando Python..."
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "❌ Python no encontrado. Por favor instala Python 3.8+"
    exit 1
fi

PY_VERSION=$($PYTHON_CMD --version | awk '{print $2}')
echo "✅ Python $PY_VERSION encontrado"
echo ""

echo "2️⃣  Instalando dependencias..."
$PYTHON_CMD -m pip install --upgrade pip -q
$PYTHON_CMD -m pip install -r requirements.txt -q

if [ $? -eq 0 ]; then
    echo "✅ Dependencias instaladas"
else
    echo "❌ Error instalando dependencias"
    exit 1
fi
echo ""

echo "3️⃣  Creando estructura de directorios..."
mkdir -p ~/.cache/aws_inventory
echo "✅ Directorio ~/.cache/aws_inventory/ creado"
echo ""

echo "4️⃣  Renombrando archivos..."
if [ -f "app_updated.py" ]; then
    cp app_updated.py app.py
    echo "✅ app_updated.py → app.py"
fi
echo ""

echo "5️⃣  Configuración AWS (opcional)"
echo "Si tienes credenciales AWS, ejecuta:"
echo ""
echo "   aws configure --profile inventario"
echo ""
echo "De lo contrario, usa MODO_DEMO = True en app.py"
echo ""

echo "===================================="
echo "✅ Instalación completada"
echo ""
echo "Para ejecutar la aplicación:"
echo ""
echo "   streamlit run app.py"
echo ""
echo "Se abrirá en: http://localhost:8501"
echo ""
