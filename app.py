import time

from flask import Flask, g
from config import Config
from models.database import close_db, ensure_db_exists
from routes import main_bp, people_bp, attendance_bp, face_bp
from routes.tasks_routes import bp as tasks_bp
from routes.health_routes import health_bp
from services.async_task_service import AsyncTaskService
from services.faiss_index_service import FaissIndexService

def create_app(config_class=Config):
    app = Flask(__name__)

    app.config.from_object(config_class)
    app.teardown_appcontext(close_db)
    
    @app.before_request
    def before_request():
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        return response

    app.register_blueprint(main_bp)
    app.register_blueprint(people_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(face_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(health_bp)

    @app.errorhandler(400)
    def bad_request(e):
        return (str(e.description if hasattr(e, "description") else e)), 400

    @app.errorhandler(404)
    def not_found(e):
        return (str(e.description if hasattr(e, "description") else e)), 404

    @app.errorhandler(409)
    def conflict(e):
        return (str(e.description if hasattr(e, "description") else e)), 409

    @app.errorhandler(500)
    def server_error(e):
        return ("Server Error", 500)

    return app

ensure_db_exists()
AsyncTaskService.initialize(max_workers=3)

app = create_app()

with app.app_context():
    try:
        print("Building FAISS index...")
        FaissIndexService.build_index()
        print("✓ FAISS index built successfully")
    except Exception as exc:
        print(f"✗ Failed to build FAISS index: {exc}")
    
    try:
        from services.face_service import FaceService
        print("Warming up DeepFace model...")
        model = FaceService.get_model()
        print(f"✓ DeepFace model loaded successfully: {Config.FACE_MODEL}")
    except Exception as exc:
        print(f"✗ Failed to warm up DeepFace model: {exc}")