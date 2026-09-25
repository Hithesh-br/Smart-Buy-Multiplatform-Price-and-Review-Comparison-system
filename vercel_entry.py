from flask import Flask, jsonify

app = Flask(__name__)

try:
    from app import app as flask_app
    app = flask_app
except Exception as exc:
    startup_error = f"{type(exc).__name__}: {exc}"

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def startup_failure(path):
        return jsonify({"status": "startup_error", "error": startup_error}), 500
