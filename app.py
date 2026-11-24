"""Harbor - a small task board for Docker practice.

Routes
    /               the web page (index.html)
    /health         returns {"status": "ok"}  (use it for a Docker HEALTHCHECK)
    /api/info       container hostname, Python version, app version, data file path
    /api/tasks      GET list, POST add
    /api/tasks/<id> PATCH toggle done, DELETE remove

Environment variables
    PORT         port used by `python app.py` (default 5000)
    DATA_DIR     folder where tasks.json is stored (default ./data)
    APP_VERSION  shown on the page footer (default 1.0.0)
"""
import json
import os
import platform
import socket
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DATA_FILE = DATA_DIR / "tasks.json"

app = Flask(__name__)
lock = threading.Lock()


def load_tasks():
    if not DATA_FILE.exists():
        return []
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_tasks(tasks):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_file = DATA_FILE.with_suffix(".tmp")
    tmp_file.write_text(json.dumps(tasks, indent=2), encoding="utf-8")
    tmp_file.replace(DATA_FILE)


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/api/info")
def info():
    return jsonify(
        hostname=socket.gethostname(),
        python=platform.python_version(),
        app_version=os.environ.get("APP_VERSION", "1.0.0"),
        data_file=str(DATA_FILE),
    )


@app.get("/api/tasks")
def list_tasks():
    with lock:
        return jsonify(load_tasks())


@app.post("/api/tasks")
def add_task():
    body = request.get_json(silent=True) or {}
    title = str(body.get("title", "")).strip()
    if not title:
        return jsonify(error="title is required"), 400

    task = {"id": uuid.uuid4().hex[:8], "title": title[:200], "done": False}
    with lock:
        tasks = load_tasks()
        tasks.append(task)
        save_tasks(tasks)
    return jsonify(task), 201


@app.patch("/api/tasks/<task_id>")
def toggle_task(task_id):
    with lock:
        tasks = load_tasks()
        for task in tasks:
            if task["id"] == task_id:
                task["done"] = not task["done"]
                save_tasks(tasks)
                return jsonify(task)
    return jsonify(error="task not found"), 404


@app.delete("/api/tasks/<task_id>")
def delete_task(task_id):
    with lock:
        tasks = load_tasks()
        remaining = [t for t in tasks if t["id"] != task_id]
        if len(remaining) == len(tasks):
            return jsonify(error="task not found"), 404
        save_tasks(remaining)
    return "", 204


if __name__ == "__main__":
    # Handy for running without Docker. In a container, use gunicorn instead.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
