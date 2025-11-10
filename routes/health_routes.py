from flask import Blueprint, jsonify
from models.database import get_db
from services.faiss_index_service import FaissIndexService

health_bp = Blueprint("health", __name__)

@health_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "attendance-system"
    }), 200

@health_bp.route("/readiness", methods=["GET"])
def readiness_check():
    health_status = {
        "status": "ready",
        "checks": {}
    }
    
    all_healthy = True
    
    # Check database connectivity
    try:
        db = get_db()
        db.execute("SELECT 1")
        health_status["checks"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        all_healthy = False
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database error: {str(e)}"
        }
    
    # Check FAISS index
    try:
        faiss_stats = FaissIndexService.get_stats()
        health_status["checks"]["faiss_index"] = {
            "status": "healthy" if faiss_stats["status"] == "active" else "warning",
            "total_embeddings": faiss_stats.get("total_embeddings", 0),
            "message": "FAISS index operational" if faiss_stats["status"] == "active" else "FAISS index not initialized"
        }
    except Exception as e:
        health_status["checks"]["faiss_index"] = {
            "status": "warning",
            "message": f"FAISS index check failed: {str(e)}"
        }
    
    # Set overall status
    if not all_healthy:
        health_status["status"] = "unhealthy"
        return jsonify(health_status), 503
    
    return jsonify(health_status), 200

@health_bp.route("/liveness", methods=["GET"])
def liveness_check():
    return jsonify({
        "status": "alive",
        "service": "attendance-system"
    }), 200