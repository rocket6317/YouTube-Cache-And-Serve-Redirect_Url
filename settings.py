import json
import os
import tempfile

from config import UPDATE_INTERVAL_HOURS
from db import _file_lock


SETTINGS_PATH = os.path.join(os.getenv("DATA_DIR", "."), "settings.json")


def get_global_interval():
    try:
        with _file_lock(SETTINGS_PATH):
            with open(SETTINGS_PATH) as settings_file:
                value = int(json.load(settings_file).get("update_interval_hours"))
        return value if 1 <= value <= 5 else UPDATE_INTERVAL_HOURS
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        return UPDATE_INTERVAL_HOURS


def set_global_interval(value):
    value = int(value)
    if not 1 <= value <= 5:
        raise ValueError("Refresh interval must be between 1 and 5 hours.")
    directory = os.path.dirname(os.path.abspath(SETTINGS_PATH))
    os.makedirs(directory, exist_ok=True)
    with _file_lock(SETTINGS_PATH):
        fd, temp_path = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w") as temp_file:
                json.dump({"update_interval_hours": value}, temp_file, indent=2)
            os.replace(temp_path, SETTINGS_PATH)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


def reset_global_interval():
    with _file_lock(SETTINGS_PATH):
        if os.path.exists(SETTINGS_PATH):
            os.unlink(SETTINGS_PATH)
