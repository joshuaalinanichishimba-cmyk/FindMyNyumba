import logging
import sys
import os

def setup_logger():
    logger = logging.getLogger("findmynyumba")
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Console output
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # Error file output
    log_file = os.path.join("logs", "error.log")
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.ERROR)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger

logger = setup_logger()
