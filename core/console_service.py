from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Dict


class RingConsole:
    def __init__(self, max_lines: int = 4000):
        self._max_lines = max_lines
        self._lines: deque[Dict[str, Any]] = deque()
        self._lock = threading.Lock()
        self._seq = 0

    def push(self, text: str, stream: str = "stdout") -> None:
        text = text.rstrip("\r\n")
        if not text:
            return
        with self._lock:
            self._seq += 1
            self._lines.append(
                {
                    "id": self._seq,
                    "ts": time.strftime("%H:%M:%S"),
                    "stream": stream,
                    "text": text,
                }
            )
            while len(self._lines) > self._max_lines:
                self._lines.popleft()

    def poll(self, last_id: int = 0, limit: int = 200) -> Dict[str, Any]:
        with self._lock:
            entries = [row for row in self._lines if row["id"] > int(last_id)]
            if limit > 0:
                entries = entries[:limit]
            latest_id = self._seq
        return {"entries": entries, "latest_id": latest_id}

    def clear(self) -> Dict[str, Any]:
        with self._lock:
            self._lines.clear()
            self._seq = 0
        return {"ok": True}


class TeeStream:
    def __init__(self, original, console: RingConsole, stream_name: str):
        self._original = original
        self._console = console
        self._stream_name = stream_name
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, data: str):
        if data is None:
            return 0
        text = str(data)
        with self._lock:
            self._original.write(text)
            self._original.flush()
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                self._console.push(line, self._stream_name)
        return len(text)

    def flush(self):
        with self._lock:
            if self._buffer:
                self._console.push(self._buffer, self._stream_name)
                self._buffer = ""
            self._original.flush()
