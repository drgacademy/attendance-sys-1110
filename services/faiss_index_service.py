import faiss
import numpy as np
import threading

from typing import Dict, List, Optional
from datetime import datetime
from models.database import get_db

class FaissIndexService:
    _index: Optional[faiss.Index] = None
    _id_mapping: List[str] = []
    _last_updated: Optional[datetime] = None
    _embedding_dimension: int = 128
    _lock = threading.RLock()
    
    @staticmethod
    def build_index(force_rebuild: bool = False) -> None:
        with FaissIndexService._lock:
            if FaissIndexService._index is not None and not force_rebuild:
                return
            
            db = get_db()
            rows = db.execute(
                "SELECT ident, face_embedding FROM people WHERE face_embedding IS NOT NULL"
            ).fetchall()
            
            if not rows:
                FaissIndexService._index = None
                FaissIndexService._id_mapping = []
                FaissIndexService._last_updated = None
                return
            
            embeddings = []
            id_mapping = []
            
            for row in rows:
                ident = row["ident"]
                blob = row["face_embedding"]
                try:
                    vec = np.frombuffer(blob, dtype="float32")
                    embeddings.append(vec)
                    id_mapping.append(ident)
                except Exception as e:
                    continue
            
            if not embeddings:
                FaissIndexService._index = None
                FaissIndexService._id_mapping = []
                FaissIndexService._last_updated = None
                return
            
            embedding_matrix = np.array(embeddings, dtype="float32")
            faiss.normalize_L2(embedding_matrix)
            dimension = embedding_matrix.shape[1]
            FaissIndexService._embedding_dimension = dimension
            index = faiss.IndexFlatIP(dimension)
            index.add(embedding_matrix)

            FaissIndexService._index = index
            FaissIndexService._id_mapping = id_mapping
            FaissIndexService._last_updated = datetime.now()
    
    @staticmethod
    def search(query_embedding: np.ndarray, top_k: int = 5) -> List[Dict]:
        with FaissIndexService._lock:
            if FaissIndexService._index is None:
                FaissIndexService.build_index()
            
            if FaissIndexService._index is None:
                return []
            
            try:
                query = query_embedding.reshape(1, -1).astype('float32')
                faiss.normalize_L2(query)
                
                k = min(top_k, FaissIndexService._index.ntotal)
                if k <= 0:
                    return []
                
                scores, indices = FaissIndexService._index.search(query, k)
                
                results = []
                for score, idx in zip(scores[0], indices[0]):
                    if idx >= 0 and idx < len(FaissIndexService._id_mapping):
                        results.append({
                            "ident": FaissIndexService._id_mapping[idx],
                            "score": round(float(score), 6)
                        })
                
                return results
            except Exception as e:
                return []
    
    @staticmethod
    def add_embedding(ident: str, embedding: np.ndarray) -> None:
        with FaissIndexService._lock:
            if FaissIndexService._index is None:
                FaissIndexService.build_index()
                return
            
            try:
                vec = embedding.reshape(1, -1).astype('float32')
                faiss.normalize_L2(vec)
                
                FaissIndexService._index.add(vec)
                FaissIndexService._id_mapping.append(ident)
                FaissIndexService._last_updated = datetime.now()
            except Exception as e:
                FaissIndexService.build_index(force_rebuild=True)
    
    @staticmethod
    def update_embedding(ident: str, embedding: np.ndarray) -> None:
        with FaissIndexService._lock:
            FaissIndexService.build_index(force_rebuild=True)
    
    @staticmethod
    def remove_embedding(ident: str) -> None:
        with FaissIndexService._lock:
            if ident in FaissIndexService._id_mapping:
                FaissIndexService.build_index(force_rebuild=True)
    
    @staticmethod
    def rebuild_if_stale(max_age_minutes: int = 60) -> None:
        with FaissIndexService._lock:
            if FaissIndexService._last_updated is None:
                FaissIndexService.build_index()
                return
            
            age_seconds = (datetime.now() - FaissIndexService._last_updated).total_seconds()
            age_minutes = age_seconds / 60
            
            if age_minutes > max_age_minutes:
                FaissIndexService.build_index(force_rebuild=True)
    
    @staticmethod
    def get_stats() -> Dict:
        with FaissIndexService._lock:
            if FaissIndexService._index is None:
                return {
                    "status": "not_initialized",
                    "total_embeddings": 0,
                    "dimension": 0,
                    "last_updated": None
                }
            
            return {
                "status": "active",
                "total_embeddings": FaissIndexService._index.ntotal,
                "dimension": FaissIndexService._embedding_dimension,
                "last_updated": FaissIndexService._last_updated.isoformat() if FaissIndexService._last_updated else None,
                "id_mapping_length": len(FaissIndexService._id_mapping),
                "index_type": type(FaissIndexService._index).__name__
            }

