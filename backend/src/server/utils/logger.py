import logging
import time

from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path("src/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- Formatters ---
formatter = logging.Formatter(
    fmt="%(asctime)s - %(levelname)s - %(name)s: %(message)s",
    datefmt="%d.%m.%Y  %H:%M:%S"
)
formatter.converter = time.localtime  # Use local time for log timestamps




def attach_fallback_logfile():
    fallback_file = LOG_DIR / "patch_loader.log"
    current_file = LOG_DIR / "load_current.log"
    patch_logger.handlers.clear()
    load_logger.handlers.clear()
    fallback_handler = logging.FileHandler(fallback_file, mode="a", encoding="utf-8")
    fallback_handler.setFormatter(formatter)
    current_handler = logging.FileHandler(current_file, mode="a", encoding="utf-8")
    current_handler.setFormatter(formatter)
    patch_logger.addHandler(fallback_handler)
    load_logger.addHandler(current_handler)



def _attach_patch_logfile(patch_name: str) -> None:
    log_file = LOG_DIR / f"patch_{patch_name}.log"

    patch_logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    patch_logger.addHandler(file_handler)


def _attach_load_logfile(patch_name: str) -> None: 
    log_file = LOG_DIR / f"load_{patch_name}.log"

    load_logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    load_logger.addHandler(file_handler)



def attach_logfile(patch: str, hotfix: datetime | None = None) -> None:
    name = patch.replace(".", "-")
    if hotfix:
        name += f"-hotfix-{hotfix.date().isoformat()}"
    _attach_patch_logfile(name)
    _attach_load_logfile(name)



def finalize_load_logfile(patch: str, hotfix: datetime | None = None) -> None:
    name = patch.replace(".", "-")
    if hotfix:
        name += f"-hotfix-{hotfix.date().isoformat()}"

    current_path = LOG_DIR / "load_current.log"
    final_path = LOG_DIR / f"load_{name}.log"

    try:
        current_data = current_path.read_text()

        with open(final_path, "a", encoding="utf-8") as f:
            f.write(current_data)

        current_path.write_text("")
        patch_logger.info(f"[LOGGING] [COPY] [{final_path.name}] Load log saved")
    except Exception as e:
        patch_logger.error(f"[LOGGING] [COPY] [{final_path.name}] Failed to save load log: {e}")



# --- Handlers ---
def _create_file_handler(filename: str, level=logging.DEBUG) -> logging.Handler:
    handler = TimedRotatingFileHandler(LOG_DIR / filename, when="W0", backupCount=7, encoding="utf-8")
    handler.setFormatter(formatter)
    handler.setLevel(level)
    return handler

def _create_console_handler(level=logging.WARNING) -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(level)
    return handler




# --- Setup Loggers ---
def setup_loggers() -> dict[str, logging.Logger]:
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(name)s: %(message)s",
        datefmt="%d.%m.%Y  %H:%M:%S"
    )

    core_logger = logging.getLogger("liandrys")
    core_logger.setLevel(logging.INFO)


    patch_logger = logging.getLogger("liandrys.patch")
    patch_logger.setLevel(logging.INFO)
    patch_file = LOG_DIR / "patch_loader.log"
    patch_handler = logging.FileHandler(patch_file, mode="a", encoding="utf-8")
    patch_handler.setFormatter(formatter)
    patch_logger.addHandler(patch_handler)

    load_logger = logging.getLogger("liandrys.load")
    load_logger.setLevel(logging.INFO)
    load_file = LOG_DIR / "load_current.log"
    load_handler = logging.FileHandler(load_file, mode="a", encoding="utf-8")
    load_handler.setFormatter(formatter)
    load_logger.addHandler(load_handler)


    # Shared handlers
    core_logger.addHandler(_create_console_handler(level=logging.CRITICAL))
    core_logger.addHandler(_create_file_handler("liandrys_all.log"))

    # Sub-loggers
    alert_logger = logging.getLogger("liandrys.alert")
    alert_logger.setLevel(logging.WARNING)
    alert_logger.addHandler(_create_file_handler("alerts.log"))

    sim_logger = logging.getLogger("liandrys.sim")
    sim_logger.setLevel(logging.INFO)
    sim_logger.addHandler(_create_file_handler("simulation.log"))

    debug_logger = logging.getLogger("liandrys.debug")
    debug_logger.setLevel(logging.DEBUG)
    file = LOG_DIR / "debug.log"
    handler = logging.FileHandler(file, mode="a", encoding="utf-8")
    handler.setFormatter(formatter)
    debug_logger.addHandler(handler)

    return {
        "core": core_logger,
        "patch": patch_logger,
        "load": load_logger,
        "alert": alert_logger,
        "sim": sim_logger,
        "debug": debug_logger
    }


loggers = setup_loggers()

core_logger = loggers["core"]
patch_logger = loggers["patch"]
load_logger = loggers["load"]
alert_logger = loggers["alert"]
sim_logger = loggers["sim"]
debug_logger = loggers["debug"]


attach_fallback_logfile()