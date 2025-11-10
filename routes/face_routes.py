from flask import Blueprint, request, jsonify
from services.face_service import FaceService
from utils.image_processing import read_image_from_request

face_bp = Blueprint("face", __name__, url_prefix="/api/face")


@face_bp.route("/verify", methods=["POST"])
def face_verify():
    payload = request.get_json(silent=True) or {}
    threshold = float(payload.get("threshold", request.args.get("threshold", 0.50)))
    top_k = int(payload.get("top_k", request.args.get("top_k", 5)))

    img = read_image_from_request(
        request.files.get("image"), payload.get("image_base64")
    )

    result = FaceService.verify(img, threshold=threshold, top_k=top_k)

    if result.get("match"):
        result["ident"] = result["match"]["ident"]
        result["score"] = result["match"]["score"]

    return jsonify(result)


@face_bp.route("/enroll", methods=["POST"])
def face_enroll():
    payload = request.get_json(silent=True) or {}
    form = request.form.to_dict()

    ident = (payload.get("ident") or form.get("ident") or "").strip()
    if not ident:
        from flask import abort

        abort(400, "ident is required")

    overwrite_param = payload.get("overwrite", form.get("overwrite"))
    overwrite = (
        True
        if overwrite_param is None
        else str(overwrite_param).lower() in ("1", "true", "yes", "y")
    )

    img = read_image_from_request(
        request.files.get("image"), payload.get("image_base64")
    )

    result = FaceService.enroll(img, ident, overwrite)
    return jsonify(result)
