from __future__ import annotations
import re

_URL = re.compile(r"^https?://\S+", re.IGNORECASE)
_FILE_WIN = re.compile(r"^[a-zA-Z]:\\")
_FILE_UNIX = re.compile(r"^/[\w/]")
_CODE_HINTS = re.compile(r"(def |class |import |function |const |var |let |#include|<\?php|SELECT |INSERT )", re.IGNORECASE)


def detect_type(text: str) -> str:
    t = text.strip()
    if _URL.match(t):
        return "url"
    if _FILE_WIN.match(t) or _FILE_UNIX.match(t):
        return "file_path"
    if "\n" in t and _CODE_HINTS.search(t):
        return "code"
    if t.startswith("<") and t.endswith(">"):
        return "html"
    return "text"
