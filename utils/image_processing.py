import base64
import numpy as np
import cv2

from flask import abort
from typing import Tuple


def read_image_from_request(image_file, image_b64: str | None):
    if image_file and image_file.filename:
        bytes_data = image_file.read()
    elif image_b64:
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        bytes_data = base64.b64decode(image_b64)
    else:
        abort(400, "Please provide image file or image_base64")

    arr = np.frombuffer(bytes_data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        abort(400, "Image decoding failed")
    return img


def optimize_image(
    image: np.ndarray, max_width: int = 1024, max_height: int = 1024, quality: int = 85
) -> Tuple[np.ndarray, dict]:
    original_height, original_width = image.shape[:2]
    original_size = image.nbytes

    if original_width <= max_width and original_height <= max_height:
        resized = image
        resize_ratio = 1.0
    else:
        width_ratio = max_width / original_width
        height_ratio = max_height / original_height
        scale = min(width_ratio, height_ratio)

        new_width = int(original_width * scale)
        new_height = int(original_height * scale)

        resized = cv2.resize(
            image, (new_width, new_height), interpolation=cv2.INTER_AREA
        )
        resize_ratio = scale

    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    is_success, buffer = cv2.imencode(".jpg", resized, encode_params)

    if not is_success:
        raise Exception("Failed to encode optimized image")

    optimized = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    compressed_size = buffer.nbytes

    stats = {
        "original_dimensions": (original_width, original_height),
        "optimized_dimensions": (resized.shape[1], resized.shape[0]),
        "original_size_bytes": original_size,
        "compressed_size_bytes": compressed_size,
        "compression_ratio": f"{(1 - compressed_size / original_size) * 100:.1f}%",
        "size_reduction": original_size - compressed_size,
        "resize_ratio": f"{resize_ratio:.2f}x",
    }

    return optimized, stats


def compress_image_to_bytes(image: np.ndarray, quality: int = 85) -> Tuple[bytes, int]:
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    is_success, buffer = cv2.imencode(".jpg", image, encode_params)

    if not is_success:
        raise Exception("Failed to compress image")

    image_bytes = buffer.tobytes()
    return image_bytes, len(image_bytes)


def l2_normalize(v: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = np.linalg.norm(v) + eps
    return v / n


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def captureVideoToDataURL(video_element_data):
    pass
