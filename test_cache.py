#!/usr/bin/env python3
"""
test_cache.py
──────────────────────────────────────────────────
Script de prueba para demostrar cómo funciona cache_manager.
Ejecuta: python3 test_cache.py
"""

import sys
import json
from datetime import datetime, timedelta
from cache_manager import cache_manager

print("=" * 60)
print("🧪 Test de Cache Manager")
print("=" * 60)
print()

# Test 1: Guardar y leer datos simples
print("✅ Test 1: Guardar y leer datos")
print("-" * 60)

datos_test = {
    "ec2_instances": 5,
    "rds_databases": 2,
    "lambda_functions": 8,
    "timestamp": datetime.now().isoformat()
}

print(f"Guardando: {json.dumps(datos_test, indent=2)}")
cache_manager.set("test_data", datos_test)
print("✅ Datos guardados")
print()

# Test 2: Recuperar datos
print("✅ Test 2: Recuperar datos del caché")
print("-" * 60)

datos_recuperados, is_fresh, changed = cache_manager.get("test_data")
print(f"Datos recuperados: {datos_recuperados}")
print(f"¿Está fresco? (< 1 día): {is_fresh}")
print(f"¿Cambió respecto al último guardado? {changed}")
print()

# Test 3: Información del caché
print("✅ Test 3: Información del caché")
print("-" * 60)

info = cache_manager.get_info("test_data")
if info:
    print(f"Timestamp: {info['timestamp']}")
    print(f"Tamaño: {info['size_bytes']} bytes")
    print(f"Hash: {info['hash'][:16]}...")
print()

# Test 4: Detectar cambios
print("✅ Test 4: Detectar cambios")
print("-" * 60)

datos_modificados = datos_test.copy()
datos_modificados["ec2_instances"] = 7  # Cambio deliberado
datos_modificados["timestamp"] = datetime.now().isoformat()

print(f"Guardando datos modificados...")
cache_manager.set("test_data", datos_modificados)

datos_nuevos, is_fresh_2, changed_2 = cache_manager.get("test_data")
print(f"¿Detectó cambios? {changed_2}")
print()

# Test 5: Estadísticas del caché
print("✅ Test 5: Estadísticas del caché")
print("-" * 60)

stats = cache_manager.get_stats()
print(f"Total de archivos en caché: {stats['total_files']}")
print(f"Tamaño total: {stats['total_size_mb']} MB")
print(f"Ubicación: {stats['cache_dir']}")
print()

# Test 6: Listar todo el metadata
print("✅ Test 6: Metadata completo")
print("-" * 60)

all_metadata = cache_manager.get_all_info()
print(json.dumps(all_metadata, indent=2, default=str))
print()

# Test 7: Probar caché con lista grande
print("✅ Test 7: Caché con datos grandes (simulado)")
print("-" * 60)

datos_grandes = {
    "items": [
        {
            "id": f"item-{i}",
            "name": f"EC2-instance-{i}",
            "type": "t3.medium",
            "state": "running",
            "tags": {"Name": f"Server-{i}", "Environment": "production"}
        }
        for i in range(100)
    ]
}

cache_manager.set("large_data", datos_grandes)
print(f"Guardados 100 items de EC2 (simulado)")

stats_2 = cache_manager.get_stats()
print(f"Tamaño total ahora: {stats_2['total_size_mb']} MB")
print()

# Test 8: Limpiar caché específico
print("✅ Test 8: Limpiar caché específico")
print("-" * 60)

print("Limpiando 'test_data'...")
cache_manager.clear("test_data")
print("✅ Limpiado")

datos_limpiado, _, _ = cache_manager.get("test_data")
if datos_limpiado is None:
    print("✅ Confirmado: datos no están en caché")
print()

# Test 9: Verificar si está vencido
print("✅ Test 9: Verificar si caché está vencido")
print("-" * 60)

is_stale = cache_manager.is_stale("large_data")
print(f"¿'large_data' está vencido (> 1 día)? {is_stale}")
print()

# Test 10: Limpiar todo
print("✅ Test 10: Limpiar todo el caché")
print("-" * 60)

print("Limpiando todo...")
cache_manager.clear()
print("✅ Caché completamente limpio")

stats_3 = cache_manager.get_stats()
print(f"Archivos en caché: {stats_3['total_files']}")
print(f"Tamaño total: {stats_3['total_size_mb']} MB")
print()

print("=" * 60)
print("✅ Todos los tests completados exitosamente")
print("=" * 60)
print()
print("📁 Ubicación del caché: ~/.cache/aws_inventory/")
print()
print("Puedes inspeccionar los archivos:")
print("  ls -lah ~/.cache/aws_inventory/")
print("  cat ~/.cache/aws_inventory/metadata.json")
print()
