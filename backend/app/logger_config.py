import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logger():
    root = Path(__file__).resolve().parent

    handler = RotatingFileHandler(
        f'{root}/app.log', maxBytes=1024*1024, backupCount=3, encoding='utf-8'
    )
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(lineno)s: %(message)s',
        handlers=[handler]
    )

    logging.getLogger("watchfiles").setLevel(logging.WARNING)
