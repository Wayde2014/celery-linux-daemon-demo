# coding=utf-8

"""
    支持跨平台、多进程的日志模块
"""

import os
import re
import time
import shutil
import logging
import portalocker
from stat import ST_MTIME
from logging import StreamHandler, FileHandler
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

file_path = os.path.abspath(__file__)
project_dir = file_path[:file_path.rfind('/')]


class LogUtil(object):
    # 默认配置
    conf = {
        'filename': '{dir}/log/app.test.log'.format(dir=project_dir),
        'level': 'DEBUG',
        'rotatetype': 'DATE',
        'when': 'midnight',
        'interval': 1,
        'multiprocess': False,
        'backupcount': 30,
        'maxbytes': 1024 * 1024 * 100,
        'format': '[%(asctime)s][pid:%(process)d][tid:%(thread)d][%(filename)s:%(lineno)d] %(levelname)s: %(message)s',
        'logger': logging.getLogger(),
    }

    def __new__(cls, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(LogUtil, cls).__new__(cls)
        return cls._instance

    def __init__(self, **kwargs):
        self.conf.update((k, v) for k, v in kwargs.items() if v is not None)
        self.mkdir_log()
        self.init_logger()

    @property
    def logger(self):
        return self.conf['logger']

    def mkdir_log(self):
        """
        创建日志目录
        """
        dname = os.path.dirname(self.conf['filename'])
        if dname and not os.path.isdir(dname):
            os.makedirs(dname, 0o755)

    def init_logger(self):
        """
        初始化日志logger
        """
        if self.conf['logger'].handlers:
            return
        if self.conf['rotatetype'] == 'SIZE':
            handler = self.getRotatingFileHandler()
        elif self.conf['rotatetype'] == 'DATE':
            handler = self.getTimedRotatingFileHandler()
        else:
            handler = self.getNoRotatingFileHandler()
        self.conf['logger'].setLevel(getattr(logging, self.conf['level']))
        self.conf['logger'].addHandler(handler)

        if self.conf.get('debug'):
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(
                logging.Formatter(self.conf['format'])
            )
            self.conf['logger'].addHandler(stream_handler)

    def getTimedRotatingFileHandler(self):
        """
        获取时间轮转文件的handler
        """
        if self.conf['multiprocess']:
            handler = TimedRotatingFileHandler_MP(
                filename=self.conf['filename'],
                when=self.conf['when'],
                interval=self.conf['interval'],
                backupCount=self.conf['backupcount'],
            )
        else:
            handler = logging.handlers.TimedRotatingFileHandler(
                filename=self.conf['filename'],
                when=self.conf['when'],
                interval=self.conf['interval'],
                backupCount=self.conf['backupcount'],
            )
        handler.setFormatter(
            logging.Formatter(self.conf['format'])
        )
        return handler

    def getRotatingFileHandler(self):
        """
        获取大小轮转文件的handler
        """
        if self.conf['multiprocess']:
            handler = RotatingFileHandler_MP(
                filename=self.conf['filename'],
                maxBytes=self.conf['maxbytes'],
                backupCount=self.conf['backupcount'],
            )
        else:
            handler = logging.handlers.RotatingFileHandler(
                filename=self.conf['filename'],
                maxBytes=self.conf['maxbytes'],
                backupCount=self.conf['backupcount'],
            )
        handler.setFormatter(
            logging.Formatter(self.conf['format'])
        )
        return handler

    def getNoRotatingFileHandler(self):
        """
        获取无轮转文件的handler
        """
        handler = logging.FileHandler(
            filename=self.conf['filename']
        )
        handler.setFormatter(
            logging.Formatter(self.conf['format'])
        )
        return handler


class StreamHandler_MP(StreamHandler):
    """
    A handler class which writes logging records, appropriately formatted,
    to a stream. Use for multiprocess.
    """

    def emit(self, record):
        """
        Emit a record.
            First seek the end of file for multiprocess to log to the same file
        """
        try:
            if hasattr(self.stream, "seek"):
                self.stream.seek(0, os.SEEK_END)
        except IOError:
            pass

        StreamHandler.emit(self, record)


class FileHandler_MP(FileHandler, StreamHandler_MP):
    """
    A handler class which writes formatted logging records to disk files
        for multiprocess
    """
    def emit(self, record):
        """
        Emit a record.

        If the stream was not opened because 'delay' was specified in the
        constructor, open it before calling the superclass's emit.
        """
        if self.stream is None:
            self.stream = self._open()
        StreamHandler_MP.emit(self, record)


class RotatingFileHandler_MP(RotatingFileHandler, FileHandler_MP):
    """
    Handler for logging to a set of files, which switches from one file
    to the next when the current file reaches a certain size.

    Based on logging.RotatingFileHandler, modified for Multiprocess
    """
    _lock_dir = '.lock'
    if os.path.exists(_lock_dir):
        pass
    else:
        os.mkdir(_lock_dir)

    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        For multiprocess, we use shutil.copy instead of rename.
        """

        self.stream.close()
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = "%s.%d" % (self.baseFilename, i)
                dfn = "%s.%d" % (self.baseFilename, i + 1)
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    shutil.copy(sfn, dfn)
            dfn = self.baseFilename + ".1"
            if os.path.exists(dfn):
                os.remove(dfn)
            if os.path.exists(self.baseFilename):
                shutil.copy(self.baseFilename, dfn)
        self.mode = 'w'
        self.stream = self._open()

    def emit(self, record):
        """
        Emit a record.

        Output the record to the file, catering for rollover as described
        in doRollover().

        For multiprocess, we use file lock. Any better method ?
        """
        try:
            if self.shouldRollover(record):
                self.doRollover()
            FileLock = self._lock_dir + '/' + os.path.basename(self.baseFilename) + '.' + record.levelname
            f = open(FileLock, "w+")
            portalocker.lock(f, portalocker.LOCK_EX | portalocker.LOCK_NB)
            FileHandler_MP.emit(self, record)
            portalocker.unlock(f)
            f.close()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class TimedRotatingFileHandler_MP(TimedRotatingFileHandler, FileHandler_MP):
    """
    Handler for logging to a file, rotating the log file at certain timed
    intervals.

    If backupCount is > 0, when rollover is done, no more than backupCount
    files are kept - the oldest ones are deleted.
    """
    _lock_dir = '.lock'
    if os.path.exists(_lock_dir):
        pass
    else:
        os.mkdir(_lock_dir)

    def __init__(self, filename, when='h', interval=1, backupCount=0, encoding=None, delay=0, utc=0):
        FileHandler_MP.__init__(self, filename, 'a', encoding, delay)
        self.encoding = encoding
        self.when = when.upper()
        self.backupCount = backupCount
        self.utc = utc
        # Calculate the real rollover interval, which is just the number of
        # seconds between rollovers.  Also set the filename suffix used when
        # a rollover occurs.  Current 'when' events supported:
        # S - Seconds
        # M - Minutes
        # H - Hours
        # D - Days
        # midnight - roll over at midnight
        # W{0-6} - roll over on a certain day; 0 - Monday
        #
        # Case of the 'when' specifier is not important; lower or upper case
        # will work.
        if self.when == 'S':
            self.suffix = "%Y-%m-%d_%H-%M-%S"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$"
        elif self.when == 'M':
            self.suffix = "%Y-%m-%d_%H-%M"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}$"
        elif self.when == 'H':
            self.suffix = "%Y-%m-%d_%H"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}_\d{2}$"
        elif self.when == 'D' or self.when == 'MIDNIGHT':
            self.suffix = "%Y-%m-%d"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}$"
        elif self.when.startswith('W'):
            if len(self.when) != 2:
                raise ValueError("You must specify a day for weekly rollover from 0 to 6 (0 is Monday): %s" % self.when)
            if self.when[1] < '0' or self.when[1] > '6':
                raise ValueError("Invalid day specified for weekly rollover: %s" % self.when)
            self.dayOfWeek = int(self.when[1])
            self.suffix = "%Y-%m-%d"
            self.extMatch = r"^\d{4}-\d{2}-\d{2}$"
        else:
            raise ValueError("Invalid rollover interval specified: %s" % self.when)

        self.extMatch = re.compile(self.extMatch)

        if interval != 1:
            raise ValueError("Invalid rollover interval, must be 1")

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        record is not used, as we are just comparing times, but it is needed so
        the method signatures are the same
        """
        if not os.path.exists(self.baseFilename):
            return 0

        cTime = time.localtime(time.time())
        mTime = time.localtime(os.stat(self.baseFilename)[ST_MTIME])
        if self.when == "S" and cTime[5] != mTime[5]:
            return 1
        elif self.when == 'M' and cTime[4] != mTime[4]:
            return 1
        elif self.when == 'H' and cTime[3] != mTime[3]:
            return 1
        elif (self.when == 'MIDNIGHT' or self.when == 'D') and cTime[2] != mTime[2]:
            return 1
        elif self.when == 'W' and cTime[1] != mTime[1]:
            return 1
        else:
            return 0

    def doRollover(self):
        """
        do a rollover; in this case, a date/time stamp is appended to the filename
        when the rollover happens.  However, you want the file to be named for the
        start of the interval, not the current time.  If there is a backup count,
        then we have to get a list of matching filenames, sort them and remove
        the one with the oldest suffix.

        For multiprocess, we use shutil.copy instead of rename.
        """
        if self.stream:
            self.stream.close()
        # get the time that this sequence started at and make it a TimeTuple
        t = int(time.time())
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
        dfn = self.baseFilename + "." + time.strftime(self.suffix, timeTuple)
        if os.path.exists(dfn):
            os.remove(dfn)
        if os.path.exists(self.baseFilename):
            shutil.copy(self.baseFilename, dfn)
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(s)
        self.mode = 'w'
        self.stream = self._open()

    def emit(self, record):
        """
        Emit a record.

        Output the record to the file, catering for rollover as described
        in doRollover().

        For multiprocess, we use file lock. Any better method ?
        """
        try:
            if self.shouldRollover(record):
                self.doRollover()
            FileLock = self._lock_dir + '/' + os.path.basename(self.baseFilename) + '.' + record.levelname
            f = open(FileLock, "w+")
            portalocker.lock(f, portalocker.LOCK_EX | portalocker.LOCK_NB)
            FileHandler_MP.emit(self, record)
            portalocker.unlock(f)
            f.close()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
