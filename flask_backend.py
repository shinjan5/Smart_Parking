from flask import Flask, request, jsonify
from agentic import entry_recognition_agent
from sqlite_helper import init_db
import os
init_db()
app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status":"ok"})

@app.route("/trigger_entry", methods=["POST"])
def trigger_entry():
    payload = request.get_json() or {}
    if not payload.get("plate"):
        return jsonify({"status":"error","message":"plate required"}), 400
    result = entry_recognition_agent(payload)
    return jsonify(result)

if __name__=="__main__":
    host = os.environ.get("FLASK_HOST","0.0.0.0")
    port = int(os.environ.get("FLASK_PORT",5000))
    app.run(host=host, port=port, debug=True)
