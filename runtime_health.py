import logging
import os
import tempfile

logger = logging.getLogger("health")


def check_readiness(db_loader, data_dir, scheduler_running):
    try:
        db_loader()
        os.makedirs(data_dir, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix=".health-", dir=data_dir)
        os.close(fd)
        os.unlink(path)
        if not scheduler_running():
            raise RuntimeError("scheduler is not running")
        return True
    except Exception as exc:
        logger.error(f"[HEALTH] Readiness check failed: {exc}")
        return False
