import threading
from collections import deque
from datetime import datetime

from .notifications import send_smtp_message
from .runtime_config import list_venues, target_date_to_offsets
from .sport_booker import SportBooker


def _now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class TaskManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._logs = deque(maxlen=200)
        self._status = {
            "state": "idle",
            "message": "Ready",
            "started_at": None,
            "updated_at": _now_text(),
            "attempts": 0,
            "task_running": False,
        }

    def _set_status(self, **changes):
        with self._lock:
            self._status.update(changes)
            self._status["updated_at"] = _now_text()

    def _log(self, message):
        entry = {"time": _now_text(), "message": message}
        with self._lock:
            self._logs.append(entry)
        return entry

    def status(self):
        with self._lock:
            return dict(self._status)

    def logs(self):
        with self._lock:
            return list(self._logs)

    def clear_logs(self):
        with self._lock:
            self._logs.clear()

    def stop(self):
        thread = self._thread
        if not thread or not thread.is_alive():
            self._set_status(state="idle", message="Ready", task_running=False)
            return False
        self._stop_event.set()
        self._set_status(state="stopping", message="Stopping task...", task_running=True)
        return True

    def start(self, config):
        if self._thread and self._thread.is_alive():
            raise RuntimeError("已有任务在运行中")

        self._stop_event = threading.Event()
        self.clear_logs()
        self._set_status(
            state="starting",
            message="Starting task...",
            started_at=_now_text(),
            attempts=0,
            task_running=True,
        )
        self._thread = threading.Thread(
            target=self._run_task,
            args=(config,),
            daemon=True,
        )
        self._thread.start()

    def _run_task(self, config):
        worker = None
        try:
            task_config = config["task"]
            self._set_status(state="running", message="Logging in...", task_running=True)

            worker = SportBooker(
                {
                    "venue": task_config["venue"],
                    "venueItem": task_config["venue_item"],
                    "date": target_date_to_offsets(task_config["target_date"]),
                    "time": task_config["times"],
                },
                username=config["account"]["username"],
                password=config["account"]["password"],
                headless=task_config["headless"],
                logger=self._log,
                stop_event=self._stop_event,
                poll_interval_ms=task_config["post_poll_ms"],
                status_callback=self._update_attempts,
            )
            worker.login()
            self._set_status(state="running", message="Booking venue...", task_running=True)
            success = worker.book()
            if success:
                self._set_status(state="success", message="抢到场地了", task_running=False)
                self._log("抢到场地了，请尽快前往平台确认并支付。")
                self._notify_async(config, True)
            elif self._stop_event.is_set():
                self._set_status(state="stopped", message="Task stopped", task_running=False)
                self._log("Task stopped before booking completed.")
            else:
                raise RuntimeError("未成功预约，任务提前结束")
        except InterruptedError as exc:
            self._set_status(state="stopped", message=str(exc), task_running=False)
            self._log(str(exc))
        except Exception as exc:
            self._set_status(state="error", message=str(exc), task_running=False)
            self._log(f"ERROR: {exc}")
            self._notify_async(config, False, str(exc))
        finally:
            if worker is not None:
                worker.close()

    def _update_attempts(self, attempts):
        self._set_status(attempts=attempts)

    def _notify_async(self, config, success, error_message=""):
        notification = config.get("notification", {})
        if not notification.get("enabled"):
            return
        threading.Thread(
            target=self._notify,
            args=(config, success, error_message),
            daemon=True,
        ).start()

    def _notify(self, config, success, error_message=""):
        notification = config.get("notification", {})
        if not notification.get("enabled"):
            return
        subject = "SJTU 抢票成功" if success else "SJTU 抢票失败"
        body = "抢票任务已完成。" if success else f"抢票任务失败：{error_message}"
        try:
            send_smtp_message(notification, subject, body)
            self._log("Notification email sent.")
        except Exception as exc:
            self._log(f"Notification failed: {exc}")

    def test_login(self, config):
        default_venue = list_venues()[0]
        worker = SportBooker(
            {
                "venue": config["task"]["venue"] or default_venue["name"],
                "venueItem": config["task"]["venue_item"] or default_venue["items"][0],
                "date": target_date_to_offsets(config["task"]["target_date"]),
                "time": config["task"]["times"],
            },
            username=config["account"]["username"],
            password=config["account"]["password"],
            headless=config["task"]["headless"],
            logger=self._log,
            stop_event=threading.Event(),
            poll_interval_ms=config["task"]["post_poll_ms"],
        )
        try:
            worker.login()
        finally:
            worker.close()

    def test_notification(self, config):
        send_smtp_message(
            config["notification"],
            "SportBooker 测试邮件",
            "这是一封来自本地控制台的测试邮件。",
        )
