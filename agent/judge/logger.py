import logging
import sys

def get_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG) 
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | [%(name)s] %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger