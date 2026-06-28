from typing import Optional


def ok(**kwargs):
    data = {"ok": True}
    data.update(kwargs)
    return data


def fail(message: str, detail: Optional[str] = None):
    data = {"ok": False, "error": message}
    if detail:
        data["detail"] = detail
    return data
