from __future__ import annotations


def build_detail_panel(*, rabbit, pipeline: str, ztamps: list[dict], **_context) -> dict:
    del rabbit, pipeline
    return {
        "panel_id": "use_cases",
        "panel_type": "use_cases",
        "title": "Laboratoire d'usages",
        "ztamps": ztamps,
    }


def before_performance_queue(*, rabbit, pipeline: str, performance: dict, source: str, mode: str, **_context) -> dict:
    del rabbit, pipeline, performance
    return {"source": source, "mode": mode, "stage": "before"}


def after_performance_queue(*, rabbit, pipeline: str, performance: dict, source: str, mode: str, asset_name: str, **_context) -> dict:
    del rabbit, pipeline, performance
    return {"source": source, "mode": mode, "asset_name": asset_name, "stage": "after"}
