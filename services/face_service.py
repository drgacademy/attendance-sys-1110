import numpy as np

from typing import Dict, Any, Optional, List
from flask import abort
from deepface import DeepFace
from models.database import get_db
from services.people_service import PeopleService
from utils.image_processing import l2_normalize, cosine_similarity
from config import Config

class FaceService:
    _MODEL_CACHE = {"sface": None}
    
    @staticmethod
    def get_model():
        if FaceService._MODEL_CACHE["sface"] is None:
            FaceService._MODEL_CACHE["sface"] = DeepFace.build_model(Config.FACE_MODEL)
        return FaceService._MODEL_CACHE["sface"]
    
    @staticmethod
    def extract_embedding(img: np.ndarray) -> np.ndarray:
        try:
            model = FaceService.get_model()
            reps = DeepFace.represent(
                img_path=img,
                model_name=Config.FACE_MODEL,
                detector_backend=Config.FACE_DETECTOR,
                enforce_detection=True,
                align=True
            )
        except Exception as e:
            abort(400, f"Face detection/feature extraction failed: {e}")
        
        if not reps:
            abort(400, "No face detected")
        
        emb = np.array(reps[0]["embedding"], dtype="float32")
        return l2_normalize(emb), len(reps)
    
    @staticmethod
    def verify(img: np.ndarray, threshold: Optional[float] = None,
              top_k: Optional[int] = None) -> Dict[str, Any]:

        threshold = threshold or Config.FACE_THRESHOLD
        top_k = top_k or Config.FACE_TOP_K
        
        emb, face_count = FaceService.extract_embedding(img)
        
        from services.faiss_index_service import FaissIndexService
        
        candidates = FaissIndexService.search(emb, top_k=top_k)
        
        if not candidates:
            return {
                "match": None,
                "top_matches": [],
                "face_count": face_count,
                "used_model": f"DeepFace-{Config.FACE_MODEL} + FAISS"
            }
        
        best = candidates[0] if candidates else None
        match = best if (best and best["score"] >= threshold) else None
        
        return {
            "match": match,
            "top_matches": candidates,
            "face_count": face_count,
            "used_model": f"DeepFace-{Config.FACE_MODEL} + FAISS"
        }
    
    @staticmethod
    def enroll(img: np.ndarray, ident: str, overwrite: bool = True) -> Dict[str, Any]:
        row = PeopleService.get_by_ident(ident)
        if not row:
            abort(404, "Person with this ident not found")
        
        if (not overwrite) and row["face_embedding"] is not None:
            abort(409, "This person already has face vector, and overwrite=false")
        
        try:
            model = FaceService.get_model()
            reps = DeepFace.represent(
                img_path=img,
                model_name=Config.FACE_MODEL,
                detector_backend=Config.FACE_DETECTOR,
                enforce_detection=True,
                align=True
            )
        except Exception as e:
            abort(400, f"Face detection/feature extraction failed: {e}")
        
        if not reps:
            abort(400, "No face detected")
        if len(reps) != 1:
            abort(400, f"Detected {len(reps)} faces, please ensure only one person in frame")
        
        emb = np.array(reps[0]["embedding"], dtype="float32")
        emb_bytes = emb.tobytes()
        
        db = get_db()
        db.execute(
            "UPDATE people SET face_embedding = %s, updated_at = NOW() WHERE ident = %s",
            (emb_bytes, ident)
        )
        db.commit()
        
        from services.faiss_index_service import FaissIndexService
        if row["face_embedding"] is None:
            FaissIndexService.add_embedding(ident, emb)
        else:
            FaissIndexService.update_embedding(ident, emb)
        
        return {
            "ident": ident,
            "face_count": 1,
            "overwritten": row["face_embedding"] is not None,
            "used_model": f"DeepFace-{Config.FACE_MODEL}"
        }

        