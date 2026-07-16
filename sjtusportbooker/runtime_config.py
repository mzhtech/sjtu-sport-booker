import copy
import json
from datetime import datetime, timedelta
from pathlib import Path

from .SJTUVenueTabLists import venueTabLists


DEFAULT_CONFIG = {
    "account": {
        "username": "",
        "password": "",
    },
    "task": {
        "venue": "",
        "venue_item": "",
        "target_dates": [],
        "times": [19, 20, 21],
        "concurrency": 1,
        "headless": True,
        "pre_poll_ms": 1000,
        "post_poll_ms": 500,
    },
    "notification": {
        "enabled": False,
        "smtp_host": "",
        "smtp_port": 465,
        "use_ssl": True,
        "sender": "",
        "password": "",
        "receiver": "",
    },
}


def _default_target_date():
    return (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")


def _deep_merge(defaults, incoming):
    merged = copy.deepcopy(defaults)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize_config(raw_config, fill_target_dates=True):
    config = _deep_merge(DEFAULT_CONFIG, raw_config or {})
    task = config["task"]
    notification = config["notification"]

    target_dates = task.get("target_dates", [])
    if isinstance(target_dates, str):
        target_dates = [target_dates]
    elif not isinstance(target_dates, (list, tuple, set)):
        target_dates = []

    target_dates = {
        str(item).strip()
        for item in target_dates
        if str(item).strip()
    }

    legacy_target_date = task.get("target_date")
    if not target_dates and legacy_target_date:
        target_dates.add(str(legacy_target_date).strip())

    legacy_days = task.get("days", [])
    if not target_dates and legacy_days:
        target_dates.update(
            (datetime.now() + timedelta(days=int(item))).strftime("%Y-%m-%d")
            for item in legacy_days
        )
    if fill_target_dates and not target_dates:
        target_dates.add(_default_target_date())

    task["target_dates"] = sorted(target_dates)
    task.pop("target_date", None)
    task.pop("days", None)
    task["times"] = sorted({int(item) for item in task.get("times", [])})
    task["concurrency"] = int(task.get("concurrency", 1))
    task["headless"] = bool(task.get("headless", True))
    task.pop("start_mode", None)
    task.pop("start_at", None)
    task["pre_poll_ms"] = int(task.get("pre_poll_ms", 1000))
    task["post_poll_ms"] = int(task.get("post_poll_ms", 500))
    notification["enabled"] = bool(notification.get("enabled", False))
    notification["smtp_port"] = int(notification.get("smtp_port", 465))
    notification["use_ssl"] = bool(notification.get("use_ssl", True))
    return config


def load_config(path):
    config_path = Path(path)
    if not config_path.exists():
        defaults = copy.deepcopy(DEFAULT_CONFIG)
        defaults["task"]["target_dates"] = [_default_target_date()]
        return defaults
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return normalize_config(data, fill_target_dates=True)


def save_config(path, config):
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_config(config, fill_target_dates=False)
    config_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return normalized


def list_venues():
    return [
        {
            "name": venue_name,
            "items": sorted(items.keys()),
        }
        for venue_name, items in venueTabLists.items()
    ]


def validate_config(config, require_notification=False):
    errors = []
    if not config["account"].get("username"):
        errors.append("账号不能为空")
    if not config["account"].get("password"):
        errors.append("密码不能为空")
    if not config["task"].get("venue"):
        errors.append("场馆不能为空")
    if not config["task"].get("venue_item"):
        errors.append("项目不能为空")
    target_dates = config["task"].get("target_dates", [])
    if not target_dates:
        errors.append("请选择日期")
    if not config["task"].get("times"):
        errors.append("至少选择一个时间段")
    concurrency = config["task"].get("concurrency", 1)
    if concurrency < 1 or concurrency > 10:
        errors.append("并发度必须在 1 到 10 之间")
    for target_date in target_dates:
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            errors.append("日期格式必须是 YYYY-MM-DD")
            break

    notification = config["notification"]
    if require_notification or notification.get("enabled"):
        required_pairs = [
            ("smtp_host", "SMTP Host"),
            ("sender", "发件邮箱"),
            ("password", "授权码/密码"),
            ("receiver", "收件邮箱"),
        ]
        for key, label in required_pairs:
            if not notification.get(key):
                errors.append(f"{label}不能为空")

    if errors:
        raise ValueError("；".join(errors))


def target_dates_to_offsets(target_dates):
    today = datetime.now().date()
    return sorted(
        {
            (datetime.strptime(target_date, "%Y-%m-%d").date() - today).days
            for target_date in target_dates
        }
    )


def target_date_to_offsets(target_date):
    """Keep compatibility with integrations that still pass one date."""
    return target_dates_to_offsets([target_date])
