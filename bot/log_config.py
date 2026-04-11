import logging
import os
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, 'bot.log')


def setup_logging():
    handler = TimedRotatingFileHandler(
        LOG_FILE,
        when='midnight',
        backupCount=7,
        encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler, console_handler]
    )
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
