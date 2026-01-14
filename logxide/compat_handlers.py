"""
Compatibility handler classes for LogXide.

This module provides handler classes that maintain compatibility with
Python's standard logging module, but delegates actual logging to
Rust native handlers for maximum performance.
"""

import re
import string
import sys
import time
import traceback

NOTSET = 0
DEBUG = 10
INFO = 20
WARNING = 30
WARN = WARNING
ERROR = 40
CRITICAL = 50
FATAL = CRITICAL


class PercentStyle:
    default_format = "%(message)s"
    asctime_format = "%(asctime)s"
    asctime_search = "%(asctime)"
    validation_pattern = re.compile(
        r"%\(\w+\)[#0+ -]*(\*|\d+)?(\.(\*|\d+))?[diouxefgcrsa%]", re.I
    )

    def __init__(self, fmt, *, defaults=None):
        self._fmt = fmt or self.default_format
        self._defaults = defaults

    def usesTime(self):
        return self._fmt.find(self.asctime_search) >= 0

    def validate(self):
        pass

    def _format(self, record):
        if self._defaults:
            values = {**self._defaults, **record.__dict__}
        else:
            values = record.__dict__
        return self._fmt % values

    def format(self, record):
        try:
            return self._format(record)
        except KeyError as e:
            raise ValueError(f"Formatting field not found in record: {e}")


class StrFormatStyle(PercentStyle):
    default_format = "{message}"
    asctime_format = "{asctime}"
    asctime_search = "{asctime"
    fmt_spec = re.compile(
        r"^(.?[<>=^])?[+ -]?#?0?(\d+|{\w+})?[,_]?(\.(\d+|{\w+}))?[bcdefgnosx%]?$", re.I
    )
    field_spec = re.compile(r"^(\d+|\w+)(\.\w+|\[[^]]+\])*$")

    def _format(self, record):
        if self._defaults:
            values = {**self._defaults, **record.__dict__}
        else:
            values = record.__dict__
        return self._fmt.format(**values)

    def validate(self):
        pass


class StringTemplateStyle(PercentStyle):
    default_format = "${message}"
    asctime_format = "${asctime}"
    asctime_search = "${asctime}"

    def __init__(self, fmt, *, defaults=None):
        self._fmt = fmt or self.default_format
        self._defaults = defaults
        self._tpl = string.Template(self._fmt)

    def usesTime(self):
        return self._fmt.find("$asctime") >= 0 or self._fmt.find("${asctime}") >= 0

    def _format(self, record):
        if self._defaults:
            values = {**self._defaults, **record.__dict__}
        else:
            values = record.__dict__
        return self._tpl.substitute(**values)

    def validate(self):
        pass


BASIC_FORMAT = "%(levelname)s:%(name)s:%(message)s"

_STYLES = {
    "%": (PercentStyle, BASIC_FORMAT),
    "{": (StrFormatStyle, "{levelname}:{name}:{message}"),
    "$": (StringTemplateStyle, "${levelname}:${name}:${message}"),
}


class NullHandler:
    """A handler that does nothing - compatible with logging.NullHandler

    Note: This is a no-op wrapper for compatibility. LogXide ignores all handlers
    and uses internal Rust handlers for performance.
    """

    def __init__(self):
        pass

    def handle(self, record):
        pass

    def emit(self, record):
        pass

    def setLevel(self, level):
        pass

    def setFormatter(self, formatter):
        pass

    def __call__(self, record):
        """Make it callable for logxide compatibility"""
        pass


class Formatter:
    def __init__(self, fmt=None, datefmt=None, style="%", validate=True, **kwargs):
        self.fmt = fmt if fmt else "%(message)s"
        self.datefmt = datefmt
        self.style = style
        self.validate = validate
        self._kwargs = kwargs

    def format(self, record):
        if isinstance(record, dict):
            record_dict = record.copy()
        elif hasattr(record, "__dict__"):
            record_dict = record.__dict__.copy()
        else:
            record_dict = {}

        if "message" not in record_dict or not record_dict["message"]:
            if hasattr(record, "getMessage"):
                record_dict["message"] = record.getMessage()
            elif "msg" in record_dict:
                record_dict["message"] = record_dict["msg"]
            else:
                record_dict["message"] = getattr(record, "msg", str(record))

        if "asctime" not in record_dict and "%(asctime)" in self.fmt:
            record_dict["asctime"] = self.formatTime(record, self.datefmt)

        try:
            s = self.fmt % record_dict
            return s
        except (KeyError, ValueError, TypeError):
            return record_dict.get("message", str(record))

    def formatTime(self, record, datefmt=None):
        """
        Format the time for a record.

        Args:
            record: LogRecord instance
            datefmt: Date format string (if None, uses default format)

        Returns:
            Formatted time string
        """
        if isinstance(record, dict):
            ct = record.get("created", time.time())
        else:
            ct = getattr(record, "created", time.time())

        if datefmt:
            s = time.strftime(datefmt, time.localtime(ct))
        else:
            t = time.localtime(ct)
            s = time.strftime("%Y-%m-%d %H:%M:%S", t)
            if isinstance(record, dict):
                msecs = record.get("msecs", 0)
            else:
                msecs = getattr(record, "msecs", 0)
            s = f"{s},{int(msecs)}"
        return s

    def formatException(self, ei):
        """
        Format exception information.

        Args:
            ei: Exception info tuple (type, value, traceback)

        Returns:
            Formatted exception string
        """
        import io

        sio = io.StringIO()
        tb = ei[2]
        traceback.print_exception(ei[0], ei[1], tb, None, sio)
        s = sio.getvalue()
        sio.close()
        if s[-1:] == "\n":
            s = s[:-1]
        return s

    def formatStack(self, stack_info):
        """
        Format stack information.

        Args:
            stack_info: Stack info string

        Returns:
            Formatted stack string
        """
        return stack_info


class Handler:
    def __init__(self, level=NOTSET):
        self.formatter = None
        self.level = level
        self.terminator = "\n"
        self._name = None
        self.filters = []

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def handle(self, record):
        rv = self.filter(record)
        if rv:
            self.emit(record)
        return rv

    def emit(self, record):
        raise NotImplementedError("emit must be implemented by Handler subclasses")

    def filter(self, record):
        for f in self.filters:
            if hasattr(f, "filter"):
                if not f.filter(record):
                    return False
            elif not f(record):
                return False
        return True

    def addFilter(self, filter):
        if filter not in self.filters:
            self.filters.append(filter)

    def removeFilter(self, filter):
        if filter in self.filters:
            self.filters.remove(filter)

    def handleError(self, record):
        if sys.stderr:
            sys.stderr.write("--- Logging error ---\n")
            traceback.print_exc(file=sys.stderr)
            sys.stderr.write("--- End of logging error ---\n")

    def setFormatter(self, formatter):
        self.formatter = formatter

    def setLevel(self, level):
        self.level = level

    def format(self, record):
        if self.formatter:
            return self.formatter.format(record)
        else:
            if isinstance(record, dict):
                return record.get("msg", str(record))
            elif hasattr(record, "getMessage"):
                return record.getMessage()
            else:
                return getattr(record, "msg", str(record))

    def flush(self):
        pass

    def close(self):
        pass

    def __repr__(self):
        level = getLevelName(self.level)
        return f"<{self.__class__.__name__} ({level})>"


def getLevelName(level):
    return _level_to_name.get(level, f"Level {level}")


class StreamHandler(Handler):
    def __init__(self, stream=None):
        super().__init__()
        if stream is None:
            stream = sys.stderr
        self._stream = stream
        self._name = None
        self.terminator = "\n"

    @property
    def stream(self):
        return self._stream

    @stream.setter
    def stream(self, value):
        self._stream = value

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)

    def flush(self):
        if self.stream and hasattr(self.stream, "flush"):
            self.stream.flush()

    def close(self):
        self.flush()

    def setStream(self, stream):
        if stream is self.stream:
            return None
        old = self.stream
        self.stream = stream
        return old


class FileHandler(Handler):
    """File handler class - compatibility wrapper

    WARNING: LogXide does not support custom Python handlers for performance
    reasons. Handlers are managed internally by Rust. This class exists only
    for API compatibility.

    To configure file output, use basicConfig() instead:
        logxide.basicConfig(filename='app.log', level=logging.DEBUG)
    """

    def __init__(self, filename, mode="a", encoding=None, delay=False):
        super().__init__()
        self.baseFilename = filename
        self.mode = mode
        self.encoding = encoding
        self.delay = delay

    def close(self):
        """No-op: LogXide uses internal Rust handlers"""
        pass

    def emit(self, record):
        """No-op: LogXide uses internal Rust handlers"""
        pass


class RotatingFileHandler(Handler):
    """Rotating file handler - compatibility wrapper

    WARNING: LogXide does not support custom Python handlers for performance
    reasons. Handlers are managed internally by Rust. This class exists only
    for API compatibility.
    """

    def __init__(
        self,
        filename,
        mode="a",
        maxBytes=0,
        backupCount=0,
        encoding=None,
        delay=False,
    ):
        super().__init__()
        self.baseFilename = filename
        self.mode = mode
        self.maxBytes = maxBytes
        self.backupCount = backupCount
        self.encoding = encoding
        self.delay = delay

    def doRollover(self):
        """No-op: LogXide uses internal Rust handlers"""
        pass

    def emit(self, record):
        """No-op: LogXide uses internal Rust handlers"""
        pass

    def close(self):
        """No-op: LogXide uses internal Rust handlers"""
        pass


class LoggingManager:
    def __init__(self):
        self.disable = 0


class Filter:
    def __init__(self, name=""):
        self.name = name
        self.nlen = len(name)

    def filter(self, record):
        if self.nlen == 0:
            return True
        if isinstance(record, dict):
            record_name = record.get("name", "")
        else:
            record_name = getattr(record, "name", "")
        if self.name == record_name:
            return True
        elif record_name.startswith(self.name + "."):
            return True
        return False


class LogRecord:
    def __init__(
        self,
        name,
        level,
        pathname,
        lineno,
        msg,
        args,
        exc_info,
        func=None,
        sinfo=None,
        **kwargs,
    ):
        self.name = name
        self.levelno = level
        self.levelname = _level_to_name.get(level, f"Level {level}")
        self.pathname = pathname
        self.filename = pathname.rsplit("/", 1)[-1] if pathname else ""
        self.module = self.filename.rsplit(".", 1)[0] if self.filename else ""
        self.lineno = lineno
        self.msg = msg
        self.args = args
        self.exc_info = exc_info
        self.func_name = func or ""
        self.funcName = func or ""
        self.stack_info = sinfo
        self.sinfo = sinfo

        ct = time.time()
        self.created = ct
        self.msecs = (ct - int(ct)) * 1000
        self.relativeCreated = (ct - _start_time) * 1000

        import threading
        import os

        self.thread = threading.current_thread().ident
        self.threadName = threading.current_thread().name
        self.process = os.getpid()
        self.processName = "MainProcess"

        self.message = ""
        self.asctime = ""
        self.exc_text = None
        self.task_name = None
        self.extra = kwargs.get("extra")

        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    def getMessage(self):
        msg = str(self.msg)
        if self.args:
            try:
                msg = msg % self.args
            except (TypeError, ValueError):
                pass
        return msg

    def __repr__(self):
        return f"<LogRecord: {self.name}, {self.levelno}, {self.pathname}, {self.lineno}, {self.msg!r}>"


_start_time = time.time()

_level_to_name = {
    CRITICAL: "CRITICAL",
    ERROR: "ERROR",
    WARNING: "WARNING",
    INFO: "INFO",
    DEBUG: "DEBUG",
    NOTSET: "NOTSET",
}
