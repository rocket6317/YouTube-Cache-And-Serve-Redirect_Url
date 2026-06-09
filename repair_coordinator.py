import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError


class RepairCoordinator:
    """Share one background repair per stream and rate-limit failed retries."""

    def __init__(self, repair_func, cooldown_seconds=300, max_workers=4):
        self._repair_func = repair_func
        self._cooldown_seconds = cooldown_seconds
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="stream-repair",
        )
        self._lock = threading.Lock()
        self._states = {}

    def request(self, name, timeout=30):
        now = time.monotonic()
        with self._lock:
            state = self._states.setdefault(
                name,
                {"future": None, "cooldown_until": 0},
            )
            if state["cooldown_until"] > now:
                return "cooldown"

            future = state["future"]
            if future is not None and future.done():
                try:
                    succeeded = bool(future.result())
                except Exception:
                    succeeded = False
                state["future"] = None
                if succeeded:
                    return "redirected"
                state["cooldown_until"] = now + self._cooldown_seconds
                return "cooldown"

            if future is None:
                future = self._executor.submit(self._repair_func, name)
                state["future"] = future

        try:
            succeeded = bool(future.result(timeout=timeout))
        except TimeoutError:
            return "repair_timeout"
        except Exception:
            succeeded = False

        with self._lock:
            state = self._states[name]
            if state["future"] is future:
                state["future"] = None
            if not succeeded:
                state["cooldown_until"] = time.monotonic() + self._cooldown_seconds

        return "redirected" if succeeded else "repair_failed"
