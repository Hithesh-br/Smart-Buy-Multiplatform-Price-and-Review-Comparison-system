from flask import Flask, jsonify

try:
    from app import app
except Exception as exc:
    app = Flask(__name__)
    startup_error = f"{type(exc).__name__}: {exc}"

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def startup_failure(path):
        return jsonify({"status": "startup_error", "error": startup_error}), 500
