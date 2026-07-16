import threading
import queue
import random
from collections import deque
from datetime import datetime

from .notifications import send_smtp_message
from .runtime_config import list_venues, target_dates_to_offsets
from .sport_booker import SportBooker


def _now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _distribute_target_dates(target_dates, concurrency, rng=None):
    shuffled_dates = list(dict.fromkeys(target_dates))
    if not shuffled_dates:
        return []

    (rng or random.SystemRandom()).shuffle(shuffled_dates)
    worker_count = min(max(int(concurrency), 1), len(shuffled_dates))
    assignments = [[] for _ in range(worker_count)]
    for index, target_date in enumerate(shuffled_dates):
        assignments[index % worker_count].append(target_date)
    return assignments


class _CombinedStopEvent:
    def __init__(self, manual_stop_event, cycle_stop_event):
        self.manual_stop_event = manual_stop_event
        self.cycle_stop_event = cycle_stop_event

    def is_set(self):
        return self.manual_stop_event.is_set() or self.cycle_stop_event.is_set()

    def set(self):
        self.cycle_stop_event.set()


class TaskManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._worker_attempts = {}
        self._attempts_before_cycle = 0
        self.retry_delay_seconds = 3
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
        self._worker_attempts = {}
        self._attempts_before_cycle = 0
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
        cycle_number = 0
        retry_number = 0

        while not self._stop_event.is_set():
            cycle_number += 1
            with self._lock:
                self._attempts_before_cycle = self._status.get("attempts", 0)
                self._worker_attempts = {}

            outcome, error_message = self._run_cycle(config, cycle_number)
            if outcome == "success":
                self._set_status(state="success", message="抢到场地了", task_running=False)
                self._log("抢到场地了，请尽快前往平台确认并支付。")
                self._notify_async(config, True)
                return
            if outcome == "stopped" or self._stop_event.is_set():
                self._set_status(state="stopped", message="Task stopped", task_running=False)
                self._log("Task stopped before booking completed.")
                return

            retry_number += 1
            delay = min(self.retry_delay_seconds * retry_number, 30)
            self._set_status(
                state="recovering",
                message=f"Restarting full flow in {delay} seconds...",
                task_running=True,
            )
            self._log(
                f"Full-flow retry {retry_number}: {error_message}. "
                f"All browsers were closed; login will restart in {delay} seconds."
            )
            if self._stop_event.wait(delay):
                break

        self._set_status(state="stopped", message="Task stopped", task_running=False)
        self._log("Task stopped before booking completed.")

    def _run_cycle(self, config, cycle_number):
        task_config = config["task"]
        concurrency = task_config.get("concurrency", 1)
        date_assignments = _distribute_target_dates(
            task_config["target_dates"], concurrency
        )
        worker_count = len(date_assignments)
        success_event = threading.Event()
        cycle_stop_event = threading.Event()
        worker_stop_event = _CombinedStopEvent(self._stop_event, cycle_stop_event)
        booking_lock = threading.Lock()
        results = queue.Queue()

        if self._stop_event.is_set():
            return "stopped", "任务已取消"

        self._set_status(
            state="running",
            message=f"Cycle {cycle_number}: logging in once...",
            task_running=True,
        )
        self._log(f"Starting full-flow cycle {cycle_number}")
        for worker_id, assigned_dates in enumerate(date_assignments, start=1):
            self._log(
                f"[Worker {worker_id}] Assigned dates: {', '.join(assigned_dates)}"
            )

        def worker_log_for(worker_id):
            label = f"Worker {worker_id}"

            def worker_log(message):
                self._log(f"[{label}] {message}")

            return worker_log

        def create_worker(worker_id):
            worker_log = worker_log_for(worker_id)
            return SportBooker(
                {
                    "venue": task_config["venue"],
                    "venueItem": task_config["venue_item"],
                    "date": target_dates_to_offsets(date_assignments[worker_id - 1]),
                    "time": task_config["times"],
                },
                username=config["account"]["username"] if worker_id == 1 else None,
                password=config["account"]["password"] if worker_id == 1 else None,
                headless=task_config["headless"],
                logger=worker_log,
                stop_event=worker_stop_event,
                poll_interval_ms=task_config["post_poll_ms"],
                status_callback=lambda attempts: self._update_worker_attempts(
                    worker_id, attempts
                ),
                booking_lock=booking_lock,
                success_event=success_event,
            )

        primary_worker = None
        try:
            self._log("[Worker 1] Starting browser for the shared login")
            primary_worker = create_worker(1)
            primary_worker.login()
            if worker_stop_event.is_set():
                raise InterruptedError('任务已取消')
            session_state = primary_worker.export_session()
            self._log("Shared authenticated session captured")
        except InterruptedError as exc:
            if primary_worker is not None:
                primary_worker.close()
            return "stopped", str(exc)
        except Exception as exc:
            if primary_worker is not None:
                primary_worker.close()
            self._log(f"Cycle {cycle_number} shared login failed: {exc}")
            return "retry", f"shared login failed: {exc}"

        self._set_status(
            state="running",
            message=f"Booking venue with {worker_count} worker(s)...",
            task_running=True,
        )

        def run_worker(worker_id, worker=None):
            worker_log = worker_log_for(worker_id)
            try:
                if worker is None:
                    worker_log("Starting browser with the shared session")
                    worker = create_worker(worker_id)
                    worker.restore_session(session_state)
                if worker_stop_event.is_set():
                    raise InterruptedError('任务已取消')
                worker_log("Starting booking scan")
                success = worker.book()
                if success:
                    success_event.set()
                    cycle_stop_event.set()
                    results.put(("success", worker_id, ""))
                elif worker_stop_event.is_set():
                    results.put(("stopped", worker_id, ""))
                else:
                    results.put(("error", worker_id, "未成功预约，任务提前结束"))
                    cycle_stop_event.set()
            except InterruptedError as exc:
                worker_log(str(exc))
                results.put(("stopped", worker_id, str(exc)))
            except Exception as exc:
                worker_log(f"ERROR: {exc}")
                results.put(("error", worker_id, str(exc)))
                cycle_stop_event.set()
            finally:
                if worker is not None:
                    try:
                        worker.close()
                    except Exception as exc:
                        worker_log(f"Browser close failed: {exc}")

        workers = [
            threading.Thread(target=run_worker, args=(worker_id,), daemon=True)
            for worker_id in range(2, worker_count + 1)
        ]
        for worker_thread in workers:
            worker_thread.start()
        run_worker(1, primary_worker)
        for worker_thread in workers:
            worker_thread.join()

        outcomes = []
        while not results.empty():
            outcomes.append(results.get())

        if any(state == "success" for state, _, _ in outcomes):
            return "success", ""

        errors = [message for state, _, message in outcomes if state == "error"]
        if self._stop_event.is_set():
            return "stopped", "任务已取消"

        error_message = errors[0] if errors else "所有并发任务均已停止"
        return "retry", error_message

    def _update_attempts(self, attempts):
        self._set_status(attempts=attempts)

    def _update_worker_attempts(self, worker_id, attempts):
        with self._lock:
            self._worker_attempts[worker_id] = attempts + 1
            self._status["attempts"] = (
                self._attempts_before_cycle + sum(self._worker_attempts.values())
            )
            self._status["updated_at"] = _now_text()

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
                "date": target_dates_to_offsets(config["task"]["target_dates"]),
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
