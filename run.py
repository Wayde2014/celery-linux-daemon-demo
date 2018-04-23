# coding=utf-8

import time
import logging
from datetime import timedelta

from celery import Celery
from celery.signals import setup_logging
from log_util import LogUtil

# 添加日志记录
conf = {
    'filename': 'test.log',
    'level': 'DEBUG',
    'multiprocess': True,
}
LogUtil(**conf)

BROKER_URL = 'redis://127.0.0.1:6379/5'
BACKEND_URL = 'redis://127.0.0.1:6379/6'

app = Celery('tasks', broker=BROKER_URL, backend=BACKEND_URL)

fn = lambda **kwargs: logging.getLogger()
setup_logging.connect(fn)

CELERYBEAT_SCHEDULE = {
    'beat': {
        'task': 'run.is_alive',
        'schedule': timedelta(seconds=5),
    },
}
CELERY_TIMEZONE = 'Asia/Shanghai'


@app.task
def is_alive():
    logging.debug('beat is alive')
    return "OK"


if __name__ == '__main__':
    times = 0
    while times < 5:
        print("go to sleep 1 seconds")
        logging.debug("go to sleep 1 seconds")
        time.sleep(1)
        times += 1

    print("Test Success")
