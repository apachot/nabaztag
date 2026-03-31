from __future__ import annotations


def after_rfid_detected(*, rabbit, pipeline: str, tag_id: str | None = None, **_context) -> dict:
    del rabbit, pipeline
    return {"tag_id": tag_id or "", "stage": "rfid_detected"}
