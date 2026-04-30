import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_path = Path(self.temp_dir.name) / "runtime-config.json"

    def create_client(self):
        from sjtusportbooker.web.app import create_app

        app = create_app(self.config_path)
        return app.test_client()

    def test_bootstrap_returns_default_config_and_status(self):
        client = self.create_client()

        response = client.get("/api/bootstrap")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"]["state"], "idle")
        self.assertEqual(payload["status"]["message"], "Ready")
        self.assertIn("account", payload["config"])
        self.assertIn("task", payload["config"])
        self.assertIn("notification", payload["config"])
        self.assertIn("target_date", payload["config"]["task"])
        self.assertTrue(payload["venues"])

    def test_save_config_persists_to_disk(self):
        client = self.create_client()
        payload = {
            "account": {"username": "alice", "password": "secret"},
            "task": {
                "venue": "气膜体育中心",
                "venue_item": "篮球",
                "target_date": "2026-05-05",
                "times": [19, 20],
                "headless": True,
                "pre_poll_ms": 1000,
                "post_poll_ms": 500,
            },
            "notification": {
                "enabled": True,
                "smtp_host": "smtp.example.com",
                "smtp_port": 465,
                "use_ssl": True,
                "sender": "bot@example.com",
                "password": "mail-secret",
                "receiver": "joe@example.com",
            },
        }

        response = client.post("/api/config", json=payload)

        self.assertEqual(response.status_code, 200)
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["account"]["username"], "alice")
        self.assertEqual(saved["task"]["venue_item"], "篮球")
        self.assertEqual(saved["task"]["target_date"], "2026-05-05")
        self.assertTrue(saved["notification"]["enabled"])

    def test_start_rejects_incomplete_config(self):
        client = self.create_client()

        response = client.post(
            "/api/start",
            json={
                "account": {"username": "", "password": ""},
                "task": {"venue": "", "venue_item": "", "target_date": "", "times": []},
                "notification": {"enabled": False},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("账号", response.get_json()["error"])

    def test_start_rejects_missing_target_date(self):
        client = self.create_client()

        response = client.post(
            "/api/start",
            json={
                "account": {"username": "alice", "password": "secret"},
                "task": {
                    "venue": "气膜体育中心",
                    "venue_item": "篮球",
                    "target_date": "",
                    "times": [19, 20],
                },
                "notification": {"enabled": False},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("日期", response.get_json()["error"])

    def test_stream_endpoint_returns_event_stream(self):
        client = self.create_client()

        response = client.get("/api/stream")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")


if __name__ == "__main__":
    unittest.main()
