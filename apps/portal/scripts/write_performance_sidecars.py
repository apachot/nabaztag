from __future__ import annotations

import argparse
import json
from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parent.parent / "portal_app" / "static"


def _performance_sidecar_path(audio_path: Path) -> Path:
    return audio_path.with_name(f"{audio_path.name}.performance.json")


def _write_sidecars(directory: Path) -> int:
    manifest_path = directory / "manifest.json"
    raw_entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw_entries, list):
        raise RuntimeError(f"{manifest_path} must contain a JSON list.")

    written = 0
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        asset_name = " ".join(str(entry.get("asset_name") or "").split()).strip()
        payload = entry.get("payload")
        if not asset_name or not isinstance(payload, dict):
            continue

        audio_path = directory / asset_name
        if not audio_path.exists():
            continue

        sidecar = {
            "schema": "nabaztag.performance.v1",
            "asset_name": asset_name,
            "source": directory.name,
            "payload": payload,
        }
        _performance_sidecar_path(audio_path).write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written += 1
    return written


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write performance JSON sidecars next to bundled MP3 assets.")
    parser.add_argument(
        "directories",
        nargs="*",
        default=["bundled-auto", "bundled-birth"],
        help="Static bundle directories containing a manifest.json.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    total = 0
    for directory_name in args.directories:
        directory = STATIC_DIR / directory_name
        written = _write_sidecars(directory)
        total += written
        print(f"{directory}: wrote {written} sidecars")
    print(f"wrote {total} sidecars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
