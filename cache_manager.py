"""
cache_manager.py - Sistema de caché local mejorado
════════════════════════════════════════════════════════════════
Maneja caché persistente separado por región y cuenta AWS.

Estructura:
~/.cache/aws_inventory/
├── discovery.json              ← Qué regiones/cuentas existen
├── metadata.json               ← Índice central
└── by_region_account/
    ├── afex-des_us-east-1/
    │   ├── ec2.pkl
    │   ├── rds.pkl
    │   ├── vpc.pkl
    │   ├── s3.pkl
    │   ├── iam_users.pkl
    │   └── timestamp.json
    ├── afex-prod_us-east-1/
    └── ...
"""

import json
import os
import hashlib
import pickle
import gzip
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_DIR = os.path.expanduser("~/.cache/aws_inventory")
CACHE_TTL_DAYS = 7  # Datos frescos por 7 días

# Crear directorio si no existe
os.makedirs(CACHE_DIR, exist_ok=True)


class CacheManager:
    """Gestor de caché local por región-cuenta."""
    
    def __init__(self, cache_dir=CACHE_DIR):
        self.cache_dir = cache_dir
        self.metadata_file = os.path.join(cache_dir, "metadata.json")
        self.discovery_file = os.path.join(cache_dir, "discovery.json")
        self.metadata = self._load_metadata()
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Crea estructura de directorios."""
        by_region_dir = os.path.join(self.cache_dir, "by_region_account")
        os.makedirs(by_region_dir, exist_ok=True)
        
        aggregated_dir = os.path.join(self.cache_dir, "aggregated")
        os.makedirs(aggregated_dir, exist_ok=True)
    
    def _get_region_account_dir(self, account, region):
        """Obtiene ruta de carpeta para región-cuenta."""
        dir_name = f"{account}_{region}"
        path = os.path.join(self.cache_dir, "by_region_account", dir_name)
        os.makedirs(path, exist_ok=True)
        return path
    
    def _load_metadata(self):
        """Carga metadatos del caché."""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando metadata: {e}")
                return {}
        return {}
    
    def _save_metadata(self):
        """Guarda metadatos."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error guardando metadata: {e}")
    
    def _get_hash(self, data):
        """Genera hash SHA256 de datos."""
        try:
            import pandas as pd
            
            if isinstance(data, pd.DataFrame):
                # Para DataFrames: hash del contenido + shape
                json_str = json.dumps({
                    'shape': data.shape,
                    'columns': list(data.columns),
                    'dtypes': {col: str(dtype) for col, dtype in data.dtypes.items()},
                    'sample': data.head(100).to_dict(orient='records')
                }, sort_keys=True, default=str)
            elif isinstance(data, (dict, list)):
                json_str = json.dumps(data, sort_keys=True, default=str)
            else:
                json_str = str(data)
            
            return hashlib.sha256(json_str.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Error calculando hash: {e}")
            return "unknown"
    
    def get(self, account, region, resource_type):
        """
        Obtiene datos del caché.
        
        Args:
            account: Nombre de cuenta AWS (ej: "afex-prod")
            region: Región AWS (ej: "us-east-1")
            resource_type: Tipo de recurso (ej: "ec2", "rds", "vpc")
        
        Returns:
            (data, is_fresh, exists)
            - data: Los datos cacheados o None
            - is_fresh: True si está dentro de TTL
            - exists: True si el archivo existe
        """
        cache_key = f"{account}_{region}_{resource_type}"
        region_dir = self._get_region_account_dir(account, region)
        cache_file = os.path.join(region_dir, f"{resource_type}.pkl")
        timestamp_file = os.path.join(region_dir, f"{resource_type}_timestamp.json")
        
        if not os.path.exists(cache_file):
            return None, False, False
        
        try:
            # Cargar datos
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
            
            # Verificar si está fresco
            is_fresh = True
            if os.path.exists(timestamp_file):
                try:
                    with open(timestamp_file, 'r') as f:
                        ts_info = json.load(f)
                        timestamp_str = ts_info.get('timestamp')
                        if timestamp_str:
                            last_update = datetime.fromisoformat(timestamp_str)
                            is_fresh = (datetime.now() - last_update) < timedelta(days=CACHE_TTL_DAYS)
                except:
                    is_fresh = False
            
            logger.info(f"✅ Caché cargado: {account}/{region}/{resource_type} (fresco={is_fresh})")
            return data, is_fresh, True
        
        except Exception as e:
            logger.error(f"Error cargando caché {cache_key}: {e}")
            return None, False, True
    
    def set(self, account, region, resource_type, data):
        """
        Guarda datos en caché.
        
        Args:
            account: Nombre de cuenta AWS
            region: Región AWS
            resource_type: Tipo de recurso
            data: Datos a guardar (DataFrame o dict)
        """
        try:
            region_dir = self._get_region_account_dir(account, region)
            cache_file = os.path.join(region_dir, f"{resource_type}.pkl")
            timestamp_file = os.path.join(region_dir, f"{resource_type}_timestamp.json")
            
            # Guardar datos
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
            
            # Guardar timestamp
            timestamp_info = {
                'timestamp': datetime.now().isoformat(),
                'size_bytes': os.path.getsize(cache_file),
                'type': type(data).__name__
            }
            
            with open(timestamp_file, 'w') as f:
                json.dump(timestamp_info, f, indent=2)
            
            # Actualizar metadata central
            cache_key = f"{account}_{region}_{resource_type}"
            self.metadata[cache_key] = {
                'account': account,
                'region': region,
                'resource_type': resource_type,
                'timestamp': datetime.now().isoformat(),
                'size_bytes': os.path.getsize(cache_file)
            }
            self._save_metadata()
            
            logger.info(f"💾 Caché guardado: {account}/{region}/{resource_type}")
            return True
        
        except Exception as e:
            logger.error(f"Error guardando caché: {e}")
            return False
    
    def is_fresh(self, account, region, resource_type):
        """Verifica si el caché está fresco."""
        _, is_fresh, exists = self.get(account, region, resource_type)
        return is_fresh if exists else False
    
    def is_stale(self, account, region, resource_type):
        """Verifica si el caché está vencido."""
        _, is_fresh, exists = self.get(account, region, resource_type)
        return not is_fresh if exists else True
    
    def clear_region_account(self, account, region):
        """Limpia caché de una región-cuenta específica."""
        try:
            region_dir = self._get_region_account_dir(account, region)
            if os.path.exists(region_dir):
                for file in os.listdir(region_dir):
                    file_path = os.path.join(region_dir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                logger.info(f"🗑️  Caché limpiado: {account}/{region}")
            return True
        except Exception as e:
            logger.error(f"Error limpiando caché: {e}")
            return False
    
    def clear_all(self):
        """Limpia TODO el caché."""
        try:
            by_region_dir = os.path.join(self.cache_dir, "by_region_account")
            if os.path.exists(by_region_dir):
                for account_region in os.listdir(by_region_dir):
                    path = os.path.join(by_region_dir, account_region)
                    if os.path.isdir(path):
                        for file in os.listdir(path):
                            file_path = os.path.join(path, file)
                            if os.path.isfile(file_path):
                                os.remove(file_path)
            self.metadata = {}
            self._save_metadata()
            logger.info("🗑️  Caché completamente limpiado")
            return True
        except Exception as e:
            logger.error(f"Error limpiando caché: {e}")
            return False
    
    def get_stats(self):
        """Retorna estadísticas del caché."""
        total_size = 0
        cache_count = 0
        region_accounts = set()
        
        try:
            by_region_dir = os.path.join(self.cache_dir, "by_region_account")
            for account_region in os.listdir(by_region_dir):
                path = os.path.join(by_region_dir, account_region)
                if os.path.isdir(path):
                    region_accounts.add(account_region)
                    for file in os.listdir(path):
                        if file.endswith('.pkl'):
                            file_path = os.path.join(path, file)
                            cache_count += 1
                            total_size += os.path.getsize(file_path)
        except:
            pass
        
        return {
            'total_files': cache_count,
            'total_size_mb': round(total_size / (1024*1024), 2),
            'region_accounts': len(region_accounts),
            'cache_dir': self.cache_dir
        }
    
    def get_all_info(self):
        """Retorna info de todos los cachés."""
        return self.metadata
    
    def compare_and_update(self, account, region, resource_type, new_data):
        """
        Compara datos nuevos con caché existente.
        Solo actualiza si hay cambios (descarga inteligente).
        
        Args:
            account: Nombre de cuenta
            region: Región AWS
            resource_type: Tipo de recurso (ec2, rds, etc)
            new_data: Nuevos datos a guardar
        
        Returns:
            dict con info: {
                'updated': bool (fue actualizado?),
                'hash_old': hash anterior,
                'hash_new': hash nuevo,
                'count_old': cantidad anterior,
                'count_new': cantidad nueva,
                'status': 'updated' | 'unchanged' | 'new'
            }
        """
        try:
            # Obtener datos viejos
            old_data, _, exists = self.get(account, region, resource_type)
            
            # Calcular hashes
            hash_new = self._get_hash(new_data)
            hash_old = self._get_hash(old_data) if exists and old_data is not None else None
            
            # Contar registros
            import pandas as pd
            count_new = len(new_data) if isinstance(new_data, pd.DataFrame) else 0
            count_old = len(old_data) if exists and isinstance(old_data, pd.DataFrame) else 0
            
            # Comparar
            result = {
                'resource_type': resource_type,
                'hash_old': hash_old,
                'hash_new': hash_new,
                'count_old': count_old,
                'count_new': count_new,
                'changed': False,
                'status': 'new'
            }
            
            if not exists:
                # Primer descarga
                result['status'] = 'new'
                result['changed'] = True
                logger.info(f"🆕 {account}/{region}/{resource_type}: NUEVA descarga ({count_new} items)")
            
            elif hash_new == hash_old:
                # Sin cambios
                result['status'] = 'unchanged'
                result['changed'] = False
                logger.info(f"✅ {account}/{region}/{resource_type}: SIN CAMBIOS ({count_new} items, hash igual)")
                return result  # NO actualizar
            
            else:
                # Cambios detectados
                result['status'] = 'updated'
                result['changed'] = True
                
                if count_new > count_old:
                    delta = count_new - count_old
                    logger.info(f"📈 {account}/{region}/{resource_type}: +{delta} items ({count_old} → {count_new})")
                elif count_new < count_old:
                    delta = count_old - count_new
                    logger.info(f"📉 {account}/{region}/{resource_type}: -{delta} items ({count_old} → {count_new})")
                else:
                    logger.info(f"🔄 {account}/{region}/{resource_type}: CONTENIDO CAMBIÓ ({count_new} items, hash distinto)")
            
            # Guardar si hay cambios o es nuevo
            if result['changed']:
                self.set(account, region, resource_type, new_data)
                result['saved'] = True
            else:
                result['saved'] = False
            
            return result
        
        except Exception as e:
            logger.error(f"Error en compare_and_update: {e}")
            # En caso de error, actualizar conservadoramente
            self.set(account, region, resource_type, new_data)
            return {
                'resource_type': resource_type,
                'status': 'error',
                'changed': True,
                'saved': True,
                'error': str(e)
            }
        """Guarda información de discovery (qué regiones-cuentas existen)."""
        try:
            with open(self.discovery_file, 'w') as f:
                json.dump(discovery_data, f, indent=2, default=str)
            logger.info("📍 Discovery guardado")
            return True
        except Exception as e:
            logger.error(f"Error guardando discovery: {e}")
            return False
    
    def load_discovery(self):
        """Carga información de discovery."""
        if os.path.exists(self.discovery_file):
            try:
                with open(self.discovery_file, 'r') as f:
                    return json.load(f)
            except:
                return None
        return None
    
    def clear(self):
        """Limpia TODO el caché (borra todos los archivos)."""
        try:
            import shutil
            
            # Listar directorios de región-cuenta
            by_region_dir = os.path.join(self.cache_dir, "by_region_account")
            
            if os.path.exists(by_region_dir):
                shutil.rmtree(by_region_dir)
                logger.info("🗑️ Directorio by_region_account eliminado")
            
            # Eliminar metadata
            if os.path.exists(self.metadata_file):
                os.remove(self.metadata_file)
                logger.info("🗑️ Metadata eliminada")
            
            # Eliminar discovery
            if os.path.exists(self.discovery_file):
                os.remove(self.discovery_file)
                logger.info("🗑️ Discovery eliminado")
            
            # Recrear directorios
            os.makedirs(by_region_dir, exist_ok=True)
            self.metadata = {}
            
            logger.info("✅ Caché completamente limpiado")
            return True
        except Exception as e:
            logger.error(f"❌ Error limpiando caché: {e}")
            return False


# Instancia global
cache_manager = CacheManager()
