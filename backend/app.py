from flask import Flask, jsonify
from flask_cors import CORS

from backend.db import init_db
from backend.routes.disbursements import disbursements_bp

def create_app():
    app = Flask(__name__)
    CORS(app)

    init_db()
    app.register_blueprint(disbursements_bp)

    @app.get("/")
    def index():
        return jsonify(
            message="Nexus Backend API",
            feature="Disbursements and Payment History",
            status="running",
        )

    @app.get("/health")
    def health():
        return jsonify(status="healthy"), 200

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
