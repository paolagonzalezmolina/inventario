"""
cache_manager.py
────────────────────────────────────────────────────────────────
Maneja caché local persistente con detección de cambios.
Almacena datos en ~/.cache/aws_inventory/ y detecta cambios cada 1 día.
"""

import json
import os
import hashlib
from datetime import datetime, timedelta
import pickle

CACHE_DIR = os.path.expanduser("~/.cache/aws_inventory")

# Crear directorio si no existe
os.makedirs(CACHE_DIR, exist_ok=True)

class CacheManager:
    """Gestor de caché local con detección de cambios."""
    
    def __init__(self, cache_dir=CACHE_DIR):
        self.cache_dir = cache_dir
        self.metadata_file = os.path.join(cache_dir, "metadata.json")
        self.metadata = self._load_metadata()
    
    def _load_metadata(self):
        """Carga metadatos del caché (timestamps y hashes)."""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_metadata(self):
        """Guarda metadatos actualizados."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving metadata: {e}")
    
    def _get_hash(self, data):
        """Genera hash SHA256 de datos."""
        if isinstance(data, (dict, list)):
            json_str = json.dumps(data, sort_keys=True, default=str)
            return hashlib.sha256(json_str.encode()).hexdigest()
        return hashlib.sha256(str(data).encode()).hexdigest()
    
    def get(self, key):
        """
        Obtiene datos del caché local.
        Retorna: (data, is_fresh, changed)
        - data: los datos cacheados
        - is_fresh: True si el caché está dentro de 1 día
        - changed: True si los datos cambiaron respecto al último guardado
        """
        cache_file = os.path.join(self.cache_dir, f"{key}.pkl")
        
        if not os.path.exists(cache_file):
            return None, False, False
        
        try:
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
            
            meta = self.metadata.get(key, {})
            timestamp = meta.get('timestamp')
            last_hash = meta.get('hash')
            
            # Verificar si está "fresco" (menos de 1 día)
            if timestamp:
                last_update = datetime.fromisoformat(timestamp)
                is_fresh = (datetime.now() - last_update) < timedelta(days=1)
            else:
                is_fresh = False
            
            # Detectar cambios
            current_hash = self._get_hash(data)
            changed = (current_hash != last_hash) if last_hash else False
            
            return data, is_fresh, changed
        
        except Exception as e:
            print(f"Error loading cache {key}: {e}")
            return None, False, False
    
    def set(self, key, data):
        """Guarda datos en caché local y actualiza metadatos."""
        try:
            cache_file = os.path.join(self.cache_dir, f"{key}.pkl")
            
            # Guardar datos
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
            
            # Actualizar metadatos
            current_hash = self._get_hash(data)
            self.metadata[key] = {
                'timestamp': datetime.now().isoformat(),
                'hash': current_hash,
                'size_bytes': os.path.getsize(cache_file)
            }
            self._save_metadata()
            
            return True
        except Exception as e:
            print(f"Error saving cache {key}: {e}")
            return False
    
    def is_stale(self, key):
        """Verifica si el caché está vencido (>1 día)."""
        meta = self.metadata.get(key, {})
        timestamp = meta.get('timestamp')
        
        if not timestamp:
            return True
        
        last_update = datetime.fromisoformat(timestamp)
        return (datetime.now() - last_update) > timedelta(days=1)
    
    def get_info(self, key):
        """Obtiene información del caché (timestamp, tamaño, hash)."""
        return self.metadata.get(key, None)
    
    def get_all_info(self):
        """Obtiene info de todos los cachés."""
        return self.metadata
    
    def clear(self, key=None):
        """Limpia caché específico o todo."""
        try:
            if key:
                cache_file = os.path.join(self.cache_dir, f"{key}.pkl")
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                if key in self.metadata:
                    del self.metadata[key]
                    self._save_metadata()
            else:
                # Limpiar todo
                for file in os.listdir(self.cache_dir):
                    if file.endswith('.pkl'):
                        os.remove(os.path.join(self.cache_dir, file))
                self.metadata = {}
                self._save_metadata()
            return True
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False
    
    def get_stats(self):
        """Retorna estadísticas del caché."""
        total_size = 0
        cache_count = 0
        
        for key, info in self.metadata.items():
            cache_count += 1
            total_size += info.get('size_bytes', 0)
        
        return {
            'total_files': cache_count,
            'total_size_mb': round(total_size / (1024*1024), 2),
            'cache_dir': self.cache_dir
        }


# Instancia global
cache_manager = CacheManager()
