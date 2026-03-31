from __future__ import annotations


def after_recording_upload(*, rabbit, pipeline: str, transcript_text: str | None = None, **_context) -> dict:
    del rabbit, pipeline
    return {"transcript_text": transcript_text or "", "stage": "recording_uploaded"}
