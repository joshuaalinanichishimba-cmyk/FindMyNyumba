import logging
import logging.handlers
import os

def setup_logging() -> None:
    """Sets up three rotating log files and console output."""
    os.makedirs('logs', exist_ok=True)
    fmt = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    app_logger = logging.getLogger('findmynyumba')
    app_logger.setLevel(logging.DEBUG)

    # INFO handler - rotates at midnight, keeps 30 days
    info_handler = logging.handlers.TimedRotatingFileHandler(
        filename='logs/info.log', when='midnight', backupCount=30, encoding='utf-8'
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(fmt)

    # ERROR handler - errors only, kept 60 days
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename='logs/error.log', when='midnight', backupCount=60, encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(fmt)

    app_logger.addHandler(info_handler)
    app_logger.addHandler(error_handler)
    app_logger.addHandler(logging.StreamHandler())
    app_logger.info('Logging system initialised')
