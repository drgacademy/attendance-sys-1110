from flask import Blueprint, jsonify
from services.async_task_service import AsyncTaskService

bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


@bp.route("/stats", methods=["GET"])
def get_task_stats():
    stats = AsyncTaskService.get_stats()
    return jsonify({"success": True, "stats": stats})


@bp.route("/<task_id>", methods=["GET"])
def get_task_status(task_id: str):
    status = AsyncTaskService.get_task_status(task_id)

    if status is None:
        return jsonify({"success": False, "error": "Task not found"}), 404

    return jsonify({"success": True, "task": status})
