"""
Server local để test frontend + backend mà không cần AWS.

Cách dùng:
    python local_server.py

Rồi mở trình duyệt tại http://localhost:3000 (frontend)
hoặc gọi API tại http://localhost:8000/recommend
"""

import json
import os
import sys
import joblib

# Thêm thư mục backend vào Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Set env vars (cần có trước khi import lambda_function)
os.environ["ARTIFACTS_BUCKET"] = "local"
os.environ["MODEL_PREFIX"] = "model/"

import lambda_function as lf

# ── Patch _load_artifacts để đọc từ local thay vì S3 ──────────────────────
def _local_load_artifacts():
    """Thay thế _load_artifacts() — load từ file local, bỏ qua S3."""
    if lf._vectorizer is not None and lf._movie_vectors is not None and lf._movies is not None:
        return  # đã load rồi, skip

    base = os.path.dirname(os.path.abspath(__file__))
    model_dir = os.path.join(base, "model")

    print("[LOCAL] Loading artifacts từ local filesystem...")
    lf._vectorizer    = joblib.load(os.path.join(model_dir, "vectorizer.pkl"))
    lf._movie_vectors = joblib.load(os.path.join(model_dir, "movie_vectors.pkl"))
    with open(os.path.join(model_dir, "movies_clean.json"), encoding="utf-8") as f:
        lf._movies = json.load(f)
    print(f"[LOCAL] Loaded {len(lf._movies)} movies ✅")

# Thay hàm _load_artifacts trong module bằng bản local
lf._load_artifacts = _local_load_artifacts

# ── Flask app ──────────────────────────────────────────────────────────────
from flask import Flask, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/recommend", methods=["POST", "OPTIONS"])
def recommend():
    if request.method == "OPTIONS":
        return Response(status=200)

    event = {
        "body": request.get_data(as_text=True),
        "requestContext": {"http": {"method": "POST"}},
    }
    result = lf.lambda_handler(event, {})
    return Response(
        response=result["body"],
        status=result["statusCode"],
        mimetype="application/json",
        headers={k: v for k, v in result.get("headers", {}).items()},
    )

if __name__ == "__main__":
    print("=" * 50)
    print("🎬 Movie DSS — Local Development Server")
    print("=" * 50)
    print("  API  : http://localhost:8000/recommend")
    print("  Web  : mở frontend/index.html bằng static server")
    print("         python -m http.server 3000 --directory frontend")
    print("=" * 50)
    app.run(host="0.0.0.0", port=8000, debug=True)
