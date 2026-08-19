"""Central logging setup."""
import logging


def setup_logging() -> logging.Logger:
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger("nexuscrm")
