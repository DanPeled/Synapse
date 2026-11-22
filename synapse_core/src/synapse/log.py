# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import atexit
import datetime
import os
import queue
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from io import TextIOWrapper
from typing import Any, Callable, Deque, Dict, Hashable, Optional, Tuple, Union

import synapse_net.generated.messages.v1 as v1
from synapse_net.socketServer import WebSocketServer, createMessage

from .alert import alert
from .bcolors import (  # noqa: F401 - kept as re-exports for existing callers
    MarkupColors,
    TextTarget,
    parseTextStyle,
)

# Flag to control printing to the console
PRINTS = True

# Only known style tags are removed for the console; using a plain write avoids
# rich's markup parser while keeping level prefixes such as [ERROR] intact.
_CONSOLE_MARKUP = re.compile(r"\[/?(?:red|green|yellow|blue|cyan|bold|underline)\]")

# Repeated records are emitted once per interval, followed by a single summary.
# The intervals are deliberately slow so a hot loop cannot produce per-frame
# log traffic.
DEFAULT_SUMMARY_INTERVAL_SECONDS: float = 30.0
DEFAULT_EXCEPTION_SUMMARY_INTERVAL_SECONDS: float = 30.0
MAX_QUEUED_RECORDS = 1000

# Create a logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Generate a new log file name based on the current date and time
LOG_FILE = f"logs/logfile_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
LOG_HANDLE: Optional[TextIOWrapper] = None


def getLogFile() -> str:
    global LOG_FILE

    if LOG_FILE is None:
        os.makedirs("logs", exist_ok=True)
        LOG_FILE = (
            f"logs/logfile_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
        )

    return LOG_FILE


def getLogHandle():
    global LOG_HANDLE

    if LOG_HANDLE is None:
        LOG_HANDLE = open(getLogFile(), "a", buffering=1)

    return LOG_HANDLE


def closeLogHandle():
    global LOG_HANDLE, LOG_FILE

    if LOG_HANDLE is not None:
        LOG_HANDLE.close()

    LOG_HANDLE = None
    LOG_FILE = None


@dataclass(frozen=True)
class LogRecord:
    """A log message waiting to be written and sent."""

    level: v1.LogLevelProto
    message: str
    alertType: Optional[v1.AlertTypeProto] = None
    timestamp: Optional[float] = None
    isSummary: bool = False


LogSink = Callable[[LogRecord, str], None]


@dataclass
class _DedupeState:
    firstSeen: float
    count: int = 0


@dataclass
class _FlushCommand:
    event: threading.Event


@dataclass
class _StopCommand:
    event: threading.Event


_QueueItem = Union[LogRecord, _FlushCommand, _StopCommand]


class LogDispatcher:
    """Queue log records and emit bounded output from a background thread.

    The clock and sink are injectable so throttling can be tested without
    sleeping or touching the filesystem/websocket.
    """

    def __init__(
        self,
        sink: Optional[LogSink] = None,
        *,
        clock: Optional[Callable[[], float]] = None,
        wallClock: Optional[Callable[[], float]] = None,
        summaryInterval: float = DEFAULT_SUMMARY_INTERVAL_SECONDS,
        maxQueueSize: int = MAX_QUEUED_RECORDS,
        autostart: bool = True,
    ):
        self._sink: LogSink = sink if sink is not None else _defaultLogSink
        self._clock = clock if clock is not None else time.monotonic
        self._wallClock = wallClock if wallClock is not None else time.time
        self._summaryInterval = summaryInterval
        self._queue: "queue.Queue[_QueueItem]" = queue.Queue(maxsize=maxQueueSize)
        self._lock = threading.Lock()
        self._states: Dict[
            Tuple[v1.LogLevelProto, str, Optional[v1.AlertTypeProto]], _DedupeState
        ] = {}
        self._dropped = 0
        self._stopped = False
        self._worker = threading.Thread(
            target=self._run, name="synapse-log-writer", daemon=True
        )
        if autostart:
            self.start()

    def start(self) -> None:
        with self._lock:
            if self._stopped or self._worker.is_alive():
                return
            self._worker.start()

    @property
    def droppedRecords(self) -> int:
        with self._lock:
            return self._dropped

    def submit(
        self,
        level: v1.LogLevelProto,
        message: str,
        alertType: Optional[v1.AlertTypeProto] = None,
    ) -> None:
        """Accept a record, suppressing exact duplicates until the next summary."""
        with self._lock:
            if self._stopped:
                return

        # Keep alerts separate so a later alerting record with the same text is
        # not swallowed by a previously non-alerting record.
        key = (level, message, alertType)
        now = self._clock()
        summary: Optional[LogRecord] = None
        emitCurrent = False

        with self._lock:
            state = self._states.get(key)
            if state is None:
                self._states[key] = _DedupeState(firstSeen=now)
                emitCurrent = True
            elif now - state.firstSeen >= self._summaryInterval:
                elapsed = now - state.firstSeen
                suppressed = state.count
                state.firstSeen = now
                state.count = 0
                if suppressed:
                    summary = self._makeSummary(level, message, suppressed, elapsed)
                else:
                    # A fresh occurrence after a quiet interval gets its own
                    # report instead of being silently discarded.
                    emitCurrent = True
            else:
                state.count += 1
                return

        if summary is not None:
            self._enqueue(summary)
        elif emitCurrent:
            self._enqueue(
                LogRecord(
                    level=level,
                    message=message,
                    alertType=alertType,
                    timestamp=self._wallClock(),
                )
            )

    def flush(self, timeout: float = 5.0) -> None:
        """Wait for all previously submitted records to reach the sink."""
        self._emitPendingSummaries()
        event = threading.Event()
        try:
            self._queue.put(_FlushCommand(event), timeout=timeout)
        except queue.Full:
            return
        event.wait(timeout)

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            if self._stopped:
                return
            self._stopped = True

        self.flush(timeout)
        event = threading.Event()
        try:
            self._queue.put(_StopCommand(event), timeout=timeout)
        except queue.Full:
            return
        event.wait(timeout)

    def _makeSummary(
        self,
        level: v1.LogLevelProto,
        message: str,
        suppressed: int,
        elapsed: float,
    ) -> LogRecord:
        return LogRecord(
            level=level,
            message=(
                f"{message} [suppressed {suppressed} duplicate(s) over {elapsed:.1f}s]"
            ),
            timestamp=self._wallClock(),
            isSummary=True,
        )

    def _emitPendingSummaries(self) -> None:
        """Flush counts that became stale without another duplicate arriving."""
        now = self._clock()
        expired = []
        with self._lock:
            for key, state in list(self._states.items()):
                if state.count and now - state.firstSeen >= self._summaryInterval:
                    elapsed = now - state.firstSeen
                    suppressed = state.count
                    state.firstSeen = now
                    state.count = 0
                    expired.append((key, suppressed, elapsed))

        for (level, message, _), suppressed, elapsed in expired:
            self._enqueue(self._makeSummary(level, message, suppressed, elapsed))

    def _enqueue(self, record: LogRecord) -> None:
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            # Never block a camera thread on logging. Dropped records are
            # counted instead of generating more traffic.
            with self._lock:
                self._dropped += 1

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if isinstance(item, _StopCommand):
                    item.event.set()
                    return
                if isinstance(item, _FlushCommand):
                    item.event.set()
                    continue

                formatted = _addTimeAt(
                    item.message,
                    item.timestamp if item.timestamp is not None else self._wallClock(),
                )
                self._sink(item, formatted)
            except Exception:
                # Logging must never kill the writer thread.
                pass
            finally:
                self._queue.task_done()


@dataclass
class _ExceptionState:
    firstSeen: float
    count: int
    lastError: str


class ExceptionThrottle:
    """Report an exception fully once, then only periodic counts per key."""

    def __init__(
        self,
        interval: float = DEFAULT_EXCEPTION_SUMMARY_INTERVAL_SECONDS,
        clock: Optional[Callable[[], float]] = None,
    ):
        self._interval = interval
        self._clock = clock if clock is not None else time.monotonic
        self._states: Dict[Hashable, _ExceptionState] = {}
        self._lock = threading.Lock()

    def exceptionDetail(
        self,
        key: Hashable,
        error: BaseException,
        formatTraceback: Callable[[], str],
    ) -> Optional[str]:
        """Return the text to log, or None when this occurrence is suppressed.

        ``formatTraceback`` is only called for a first report or a new episode,
        so a failing pipeline does not format a traceback on every frame.
        """
        now = self._clock()
        errorText = _describeError(error)

        with self._lock:
            state = self._states.get(key)
            if state is None:
                self._states[key] = _ExceptionState(now, 0, errorText)
                return formatTraceback()

            elapsed = now - state.firstSeen
            if elapsed < self._interval:
                state.count += 1
                state.lastError = errorText
                return None

            suppressed = state.count
            self._states[key] = _ExceptionState(now, 0, errorText)
            if suppressed:
                return (
                    f"{suppressed} additional exception(s) suppressed "
                    f"over {elapsed:.1f}s; latest: {errorText}"
                )
            return formatTraceback()

    def clear(self, key: Optional[Hashable] = None) -> None:
        with self._lock:
            if key is None:
                self._states.clear()
            else:
                self._states.pop(key, None)


def _describeError(error: BaseException) -> str:
    try:
        return f"{type(error).__name__}: {error}"
    except Exception:
        return type(error).__name__


class ErrorWriter(object):
    def write(self, data: Any):
        print(MarkupColors.fail(data), end="")


# sys.stderr = ErrorWriter()

logs: Deque[v1.LogMessageProto] = deque(maxlen=1000)


def _appendLogMessage(
    text: str, msgType: v1.LogLevelProto, timestamp: Optional[float] = None
) -> v1.LogMessageProto:
    if timestamp is None:
        timestamp = time.time()
    logMessage = v1.LogMessageProto(
        message=text, level=msgType, timestamp=int(timestamp * 1_000)
    )
    logs.append(logMessage)
    return logMessage


def socketLog(
    text: str, msgType: v1.LogLevelProto, socket: Optional[WebSocketServer]
) -> None:
    _sendSocketLog(text, msgType, socket, time.time())


def _sendSocketLog(
    text: str,
    msgType: v1.LogLevelProto,
    socket: Optional[WebSocketServer],
    timestamp: float,
) -> None:
    logMessage = _appendLogMessage(text, msgType, timestamp)

    if socket is not None:

        def buildMessage() -> bytes:
            return createMessage(v1.MessageTypeProto.LOG, logMessage)

        socket.sendToAllSync(buildMessage, coalesce_key=("log", msgType))


def _addTimeAt(text: str, timestamp: float) -> str:
    current_time = datetime.datetime.fromtimestamp(timestamp)
    formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    return f"[{formatted_time}]: {text}"


def addTime(text: str) -> str:
    return _addTimeAt(text, time.time())


def _writeLogLine(text: str) -> None:
    if PRINTS:
        # Plain stdout writes keep logging off rich's markup parser without
        # blocking the caller (this runs on the writer thread).
        print(_CONSOLE_MARKUP.sub("", text))
    getLogHandle().write(text + "\n")


def logInternal(text: str):
    _writeLogLine(text)


def _defaultLogSink(record: LogRecord, formatted: str) -> None:
    _writeLogLine(formatted)
    timestamp = record.timestamp if record.timestamp is not None else time.time()

    if record.alertType is not None:
        # The alert already notifies the UI. Sending a LOG message with the
        # same text would be a second websocket message for one event, so keep
        # the record in the local log only.
        _appendLogMessage(formatted, record.level, timestamp)
        alert(record.alertType, formatted)
    else:
        _sendSocketLog(formatted, record.level, WebSocketServer.kInstance, timestamp)


_dispatcher = LogDispatcher()


def flushLogs(timeout: float = 5.0) -> None:
    """Wait for queued log records to be written and sent."""
    _dispatcher.flush(timeout)


def info(text: str, shouldAlert=False):
    _dispatcher.submit(
        v1.LogLevelProto.INFO,
        text,
        v1.AlertTypeProto.INFO if shouldAlert else None,
    )


def err(text: str):
    """
    Logs an error message with the current timestamp by prepending '[ERROR]' to the message.

    Args:
        text (str): The error message to log.

    This function calls the `log` function and formats the message to indicate an error.
    """
    text = MarkupColors.fail(f"[ERROR]: {text}")
    _dispatcher.submit(v1.LogLevelProto.ERROR, text, v1.AlertTypeProto.ERROR)


def warn(text: str):
    """
    Logs a warning message with the current timestamp by prepending '[WARNING]' to the message.

    Args:
        text (str): The warning message to log.

    This function calls the `log` function and formats the message to indicate an warning.
    """
    text = MarkupColors.warning(f"[WARNING]: {text}")
    _dispatcher.submit(v1.LogLevelProto.WARNING, text, v1.AlertTypeProto.WARNING)


def missingFeature(text: str) -> None:
    err(
        f"{text}\nIf you'd like to see this feature added, feel free to open an issue on GitHub — or even better, contribute by submitting a pull request!\nGitHub repo: https://github.com/DanPeled/Synapse"
    )


def _shutdownLogging() -> None:
    try:
        _dispatcher.stop()
    finally:
        closeLogHandle()


atexit.register(_shutdownLogging)
