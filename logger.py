#logger.py
import logging, pathlib #logging for logging to file and console, pathlib for simplifying path handling 
def get_logger(name: str = __name__, env_prefix: str = "") -> logging.Logger:
    logs_dir = pathlib.Path("logs")
    logs_dir.mkdir(exist_ok=True)
    log_suffix = f"_{env_prefix}" if env_prefix else ""
    log_path = logs_dir / f"ess{log_suffix}.log"
    logger_name = f"{name}{log_suffix}" if env_prefix else name
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        ch = logging.StreamHandler()
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )   
#%(asctime)s → timestamp when it happened
#%(levelname)s → log level (INFO, ERROR, etc.)
#datefmt formats the timestamp in ISO 8601 UTC style: 2025-08-18T12:45:33Z should it be changed to est or any other specific time?
        fh.setFormatter(fmt); ch.setFormatter(fmt)
        logger.addHandler(fh); logger.addHandler(ch)
        #formats in above format and logs into console and file
    return logger


#  main block for standalone testing
if __name__ == "__main__":
    log = get_logger("logger_test")
    log.info("Logger is working")
    log.warning("This is a warning")
    log.error("This is an error")