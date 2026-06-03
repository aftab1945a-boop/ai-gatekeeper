import logging
import json
import sys

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        return json.dumps(log_record)

def setup_logger():
    logger = logging.getLogger("ai_gatekeeper")
    logger.setLevel(logging.INFO)
    
    # Console par dikhane ke liye
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    return logger

logger = setup_logger()