import json
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from ..runtime_config import (
    list_venues,
    load_config,
    normalize_config,
    save_config,
    validate_config,
)
from ..task_manager import TaskManager


def create_app(config_path=None, task_manager=None):
    template_dir = Path(__file__).with_name("templates")
    static_dir = Path(__file__).with_name("static")
    app = Flask(__name__, template_folder=str(template_dir), static_folder=str(static_dir))
    app.config["RUNTIME_CONFIG_PATH"] = Path(config_path or "runtime-config.json")
    app.task_manager = task_manager or TaskManager()

    def current_config():
        return load_config(app.config["RUNTIME_CONFIG_PATH"])

    @app.errorhandler(ValueError)
    def handle_value_error(error):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(RuntimeError)
    def handle_runtime_error(error):
        return jsonify({"error": str(error)}), 409

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": str(error)}), 500
        raise error

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/bootstrap")
    def bootstrap():
        return jsonify(
            {
                "config": current_config(),
                "venues": list_venues(),
                "status": app.task_manager.status(),
                "logs": app.task_manager.logs(),
            }
        )

    @app.get("/api/status")
    def status():
        return jsonify({"status": app.task_manager.status(), "logs": app.task_manager.logs()})

    @app.get("/api/stream")
    def stream():
        @stream_with_context
        def event_stream():
            while True:
                payload = {
                    "status": app.task_manager.status(),
                    "logs": app.task_manager.logs(),
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                time.sleep(1)

        return Response(event_stream(), mimetype="text/event-stream")

    @app.post("/api/config")
    def persist_config():
        payload = normalize_config(request.get_json(silent=True) or {})
        saved = save_config(app.config["RUNTIME_CONFIG_PATH"], payload)
        return jsonify({"config": saved, "message": "配置已保存"})

    @app.post("/api/test-login")
    def test_login():
        config = save_config(app.config["RUNTIME_CONFIG_PATH"], request.get_json(silent=True) or {})
        validate_config(config)
        app.task_manager.test_login(config)
        return jsonify({"message": "登录测试成功"})

    @app.post("/api/test-email")
    def test_email():
        config = save_config(app.config["RUNTIME_CONFIG_PATH"], request.get_json(silent=True) or {})
        validate_config(config, require_notification=True)
        app.task_manager.test_notification(config)
        return jsonify({"message": "测试邮件已发送"})

    @app.post("/api/start")
    def start_task():
        config = save_config(app.config["RUNTIME_CONFIG_PATH"], request.get_json(silent=True) or {})
        validate_config(config)
        app.task_manager.start(config)
        return jsonify({"status": app.task_manager.status(), "message": "任务已启动"})

    @app.post("/api/stop")
    def stop_task():
        app.task_manager.stop()
        return jsonify({"status": app.task_manager.status(), "message": "已发送停止指令"})

    return app
