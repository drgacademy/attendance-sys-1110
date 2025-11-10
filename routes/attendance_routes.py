from flask import Blueprint, request, jsonify
from services.attendance_service import AttendanceService
from utils.image_processing import read_image_from_request

attendance_bp = Blueprint("attendance", __name__, url_prefix="/api")


@attendance_bp.route("/punch", methods=["POST"])
def punch():
    data = request.get_json(silent=True) or request.form.to_dict()
    ident = data.get("ident")

    if not ident:
        from flask import abort

        abort(400, "ident is required (in practice, obtained from face recognition)")

    face_image = None
    try:
        image_file = request.files.get("image")
        image_b64 = data.get("image_base64")

        if image_file or image_b64:
            face_image = read_image_from_request(image_file, image_b64)
    except Exception as e:
        print(f"Failed to read face image: {e}")

    result = AttendanceService.punch(ident, face_image)
    return jsonify(result)
