from __future__ import annotations


def build_detail_panel(*, rabbit, pipeline: str, **_context) -> dict:
    del rabbit, pipeline
    return {
        "panel_id": "spotify",
        "panel_type": "coming_soon",
        "title": "Spotify",
        "message": "Plugin prévu pour piloter un pont Spotify Connect et diffuser un flux audio vers le lapin.",
    }
