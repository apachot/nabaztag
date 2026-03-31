from __future__ import annotations

from flask import current_app

from .plugins import get_plugin_hooks_for_pipeline, resolve_plugin_handler


PIPELINE_RABBIT_DETAIL_PANELS = "rabbit.detail.panels"
PIPELINE_RABBIT_EVENT_AFTER_RECORDING_UPLOAD = "rabbit.event.after_recording_upload"
PIPELINE_RABBIT_EVENT_AFTER_RFID_DETECTED = "rabbit.event.after_rfid_detected"
PIPELINE_RABBIT_PERFORMANCE_BEFORE_QUEUE = "rabbit.performance.before_queue"
PIPELINE_RABBIT_PERFORMANCE_AFTER_QUEUE = "rabbit.performance.after_queue"


def run_plugin_pipeline(
    pipeline_name: str,
    *,
    rabbit,
    is_enabled,
    **context,
) -> list[dict]:
    results: list[dict] = []
    for plugin, hook in get_plugin_hooks_for_pipeline(pipeline_name):
        if not is_enabled(rabbit, plugin.plugin_id):
            continue
        try:
            handler = resolve_plugin_handler(plugin, hook)
            outcome = handler(rabbit=rabbit, pipeline=pipeline_name, **context)
            if outcome is not None:
                results.append(
                    {
                        "plugin_id": plugin.plugin_id,
                        "pipeline": pipeline_name,
                        "result": outcome,
                    }
                )
        except Exception as exc:
            current_app.logger.exception(
                "plugin pipeline failure plugin=%s pipeline=%s: %s",
                plugin.plugin_id,
                pipeline_name,
                exc,
            )
    return results
