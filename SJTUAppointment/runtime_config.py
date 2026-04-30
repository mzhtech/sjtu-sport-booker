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
        "target_date": "",
        "times": [19, 20, 21],
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


def normalize_config(raw_config, fill_target_date=True):
    config = _deep_merge(DEFAULT_CONFIG, raw_config or {})
    task = config["task"]
    notification = config["notification"]
    legacy_days = task.get("days", [])
    if not task.get("target_date") and legacy_days:
        first_offset = min(int(item) for item in legacy_days)
        task["target_date"] = (datetime.now() + timedelta(days=first_offset)).strftime("%Y-%m-%d")
    if fill_target_date:
        task["target_date"] = task.get("target_date") or _default_target_date()
    task.pop("days", None)
    task["times"] = sorted({int(item) for item in task.get("times", [])})
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
        defaults["task"]["target_date"] = _default_target_date()
        return defaults
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return normalize_config(data, fill_target_date=True)


def save_config(path, config):
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_config(config, fill_target_date=False)
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
    if not config["task"].get("target_date"):
        errors.append("请选择日期")
    if not config["task"].get("times"):
        errors.append("至少选择一个时间段")
    else:
        try:
            datetime.strptime(config["task"]["target_date"], "%Y-%m-%d")
        except ValueError:
            errors.append("日期格式必须是 YYYY-MM-DD")

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


def target_date_to_offsets(target_date):
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    today = datetime.now().date()
    return [(target - today).days]
