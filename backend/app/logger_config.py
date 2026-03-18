import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logger():
    root = Path(__file__).resolve().parent

    handler1 = RotatingFileHandler(
        f'{root}/app.log', maxBytes=1024*1024, backupCount=3, encoding='utf-8'
    )
    
    handler2 = logging.StreamHandler()  
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(lineno)s: %(message)s',
        handlers=[handler1, handler2]  
    )

    logging.getLogger("watchfiles").setLevel(logging.WARNING)
