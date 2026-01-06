import hashlib
import os
import json
import pickle
from typing import Dict, List, Any, Optional, Tuple
from pdf_processor import PDFProcessor
from vector_store import VectorStore
from presentation_generator import PresentationGenerator
import logging

logger = logging.getLogger(__name__)

class PDFCacheManager:
    def __init__(self, cache_dir: str = "pdf_cache"):
        self.cache_dir = cache_dir
        self.cache_index_file = os.path.join(cache_dir, "cache_index.json")
        self.ensure_cache_dir()
        self.cache_index = self.load_cache_index()
        
    def ensure_cache_dir(self):
        """Ensure cache directory exists"""
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(os.path.join(self.cache_dir, "processed_data"), exist_ok=True)
        os.makedirs(os.path.join(self.cache_dir, "vector_stores"), exist_ok=True)
        os.makedirs(os.path.join(self.cache_dir, "presentations"), exist_ok=True)
        
    def load_cache_index(self) -> Dict[str, Any]:
        """Load cache index from file"""
        if os.path.exists(self.cache_index_file):
            try:
                with open(self.cache_index_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache index: {e}")
        return {}
    
    def save_cache_index(self):
        """Save cache index to file"""
        try:
            with open(self.cache_index_file, 'w') as f:
                json.dump(self.cache_index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")
    
    def get_file_hash(self, file_path: str) -> str:
        """Get SHA256 hash of file content"""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            file_hash = sha256_hash.hexdigest()
            logger.info(f"Hashed file {os.path.basename(file_path)}: {file_hash[:16]}...")
            return file_hash
        except Exception as e:
            logger.error(f"Failed to hash file {file_path}: {e}")
            return ""
    
    def get_files_hash(self, file_paths: List[str]) -> str:
        """Get combined hash for multiple files"""
        individual_hashes = []
        for file_path in sorted(file_paths):  # Sort for consistent ordering
            file_hash = self.get_file_hash(file_path)
            # Don't include filename in hash for temp files, only content hash
            individual_hashes.append(file_hash)
        
        # Create combined hash based only on file contents
        combined_string = "|".join(individual_hashes)
        return hashlib.sha256(combined_string.encode()).hexdigest()
    
    def is_cached(self, file_paths: List[str]) -> Tuple[bool, str]:
        """Check if PDFs are already cached"""
        files_hash = self.get_files_hash(file_paths)
        logger.info(f"Checking cache for combined hash: {files_hash[:16]}...")
        
        if files_hash in self.cache_index:
            cache_entry = self.cache_index[files_hash]
            logger.info(f"Found cache entry for files: {cache_entry.get('files', [])}")
            
            # Verify all cached files still exist
            required_files = [
                cache_entry.get('processed_data_path'),
                cache_entry.get('vector_store_index'),
                cache_entry.get('vector_store_pkl'),
                cache_entry.get('presentation_path')
            ]
            
            missing_files = [f for f in required_files if f and not os.path.exists(f)]
            
            if not missing_files:
                logger.info(f"✅ All cache files exist - using cached data")
                return True, files_hash
            else:
                # Cache entry exists but files are missing, remove entry
                logger.warning(f"Cache files missing: {missing_files}")
                del self.cache_index[files_hash]
                self.save_cache_index()
        else:
            logger.info(f"❌ No cache entry found for hash {files_hash[:16]}...")
        
        return False, files_hash
    
    def cache_processing_results(self, 
                                file_paths: List[str], 
                                pages_data: List[Dict[str, Any]], 
                                vector_store: VectorStore, 
                                presentation_data: Dict[str, Any],
                                presentation_generator: PresentationGenerator,
                                original_filenames: List[str] = None) -> str:
        """Cache all processing results"""
        files_hash = self.get_files_hash(file_paths)
        
        try:
            # Save processed pages data
            processed_data_path = os.path.join(self.cache_dir, "processed_data", f"{files_hash}.pkl")
            with open(processed_data_path, 'wb') as f:
                pickle.dump(pages_data, f)
            
            # Save vector store
            vector_store_path = os.path.join(self.cache_dir, "vector_stores", files_hash)
            vector_store.save_index(vector_store_path)
            
            # Save presentation data and generator state
            presentation_path = os.path.join(self.cache_dir, "presentations", f"{files_hash}.pkl")
            presentation_cache_data = {
                'presentation_data': presentation_data,
                'segments': [
                    {
                        'id': seg.id,
                        'text': seg.text,
                        'images': seg.images,
                        'duration_seconds': seg.duration_seconds,
                        'pdf_page': seg.pdf_page,
                        'pdf_name': seg.pdf_name,
                        'category': getattr(seg, 'category', 'general'),
                        'image_strategy': getattr(seg, 'image_strategy', 'show_multiple'),
                        'image_timing': getattr(seg, 'image_timing', None)
                    } for seg in presentation_generator.segments
                ],
                'pages_data': presentation_generator.pages_data
            }
            
            with open(presentation_path, 'wb') as f:
                pickle.dump(presentation_cache_data, f)
            
            # Update cache index
            # Use original filenames if provided, otherwise extract from temp paths
            if original_filenames:
                file_names = original_filenames
            else:
                file_names = [os.path.basename(fp) for fp in file_paths]
            
            self.cache_index[files_hash] = {
                'files': file_names,
                'file_paths': file_paths,
                'files_hash': files_hash,
                'processed_data_path': processed_data_path,
                'vector_store_index': f"{vector_store_path}.index",
                'vector_store_pkl': f"{vector_store_path}.pkl",
                'presentation_path': presentation_path,
                'pages_count': len(pages_data),
                'cached_at': __import__('time').time()
            }
            
            self.save_cache_index()
            logger.info(f"Cached processing results for hash {files_hash}")
            return files_hash
            
        except Exception as e:
            logger.error(f"Failed to cache processing results: {e}")
            return ""
    
    def load_cached_results(self, files_hash: str) -> Optional[Tuple[List[Dict[str, Any]], VectorStore, Dict[str, Any], PresentationGenerator]]:
        """Load cached processing results"""
        if files_hash not in self.cache_index:
            return None
        
        cache_entry = self.cache_index[files_hash]
        
        try:
            # Load processed pages data
            with open(cache_entry['processed_data_path'], 'rb') as f:
                pages_data = pickle.load(f)
            
            # Load vector store
            vector_store = VectorStore()
            vector_store_path = os.path.join(self.cache_dir, "vector_stores", files_hash)
            if not vector_store.load_index(vector_store_path):
                raise Exception("Failed to load vector store")
            
            # Load presentation data
            with open(cache_entry['presentation_path'], 'rb') as f:
                presentation_cache_data = pickle.load(f)
            
            presentation_data = presentation_cache_data['presentation_data']
            
            # Reconstruct presentation generator
            presentation_generator = PresentationGenerator()
            presentation_generator.pages_data = presentation_cache_data['pages_data']
            
            # Reconstruct segments
            from models import PresentationSegment
            presentation_generator.segments = []
            for seg_data in presentation_cache_data['segments']:
                segment = PresentationSegment(
                    id=seg_data['id'],
                    text=seg_data['text'],
                    images=seg_data['images'],
                    duration_seconds=seg_data['duration_seconds'],
                    pdf_page=seg_data['pdf_page'],
                    pdf_name=seg_data['pdf_name'],
                    category=seg_data.get('category', 'general'),
                    image_strategy=seg_data.get('image_strategy', 'show_multiple'),
                    image_timing=seg_data.get('image_timing')
                )
                presentation_generator.segments.append(segment)
            
            logger.info(f"Loaded cached results for hash {files_hash}: {len(pages_data)} pages, {len(presentation_generator.segments)} segments")
            return pages_data, vector_store, presentation_data, presentation_generator
            
        except Exception as e:
            logger.error(f"Failed to load cached results for hash {files_hash}: {e}")
            # Remove corrupted cache entry
            if files_hash in self.cache_index:
                del self.cache_index[files_hash]
                self.save_cache_index()
            return None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_entries = len(self.cache_index)
        total_pages = sum(entry.get('pages_count', 0) for entry in self.cache_index.values())
        
        # Calculate cache size
        cache_size = 0
        for root, dirs, files in os.walk(self.cache_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    cache_size += os.path.getsize(file_path)
                except OSError:
                    pass
        
        return {
            'total_entries': total_entries,
            'total_pages': total_pages,
            'cache_size_mb': round(cache_size / (1024 * 1024), 2),
            'entries': [
                {
                    'files': entry['files'],
                    'pages_count': entry['pages_count'],
                    'cached_at': entry['cached_at']
                }
                for entry in self.cache_index.values()
            ]
        }
    
    def clear_cache(self) -> bool:
        """Clear all cached data"""
        try:
            import shutil
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
            self.ensure_cache_dir()
            self.cache_index = {}
            logger.info("Cache cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
    
    def remove_cache_entry(self, files_hash: str) -> bool:
        """Remove specific cache entry"""
        if files_hash not in self.cache_index:
            return False
        
        try:
            cache_entry = self.cache_index[files_hash]
            
            # Remove files
            files_to_remove = [
                cache_entry.get('processed_data_path'),
                cache_entry.get('vector_store_index'),
                cache_entry.get('vector_store_pkl'),
                cache_entry.get('presentation_path')
            ]
            
            for file_path in files_to_remove:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            
            # Remove from index
            del self.cache_index[files_hash]
            self.save_cache_index()
            
            logger.info(f"Removed cache entry {files_hash}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove cache entry {files_hash}: {e}")
            return False