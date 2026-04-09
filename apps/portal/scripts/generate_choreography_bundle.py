from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


SCENES = [
    ("antenna-hop", "action/Action_A.mp3", 0.0, "Saut d'antenne"),
    ("greenhouse-wink", "action/Action_A.mp3", 9.5, "Clin d'oeil serre"),
    ("tin-parade", "action/Action_A.mp3", 19.0, "Parade de fer-blanc"),
    ("sax-sunbeam", "action/Action_A.mp3", 28.5, "Rayon de cuivre"),
    ("button-spark", "action/Action_B.mp3", 0.0, "Etincelle bouton"),
    ("nes-pirouette", "action/Action_B.mp3", 9.5, "Pirouette mecanique"),
    ("pizza-moon", "action/Action_B.mp3", 19.0, "Lune electrique"),
    ("steel-firefly", "action/Action_B.mp3", 28.5, "Luciole metal"),
    ("sax-bloom", "battle/Battle.mp3", 0.0, "Fleur de bataille"),
    ("tiny-fanfare", "battle/Battle.mp3", 4.8, "Mini fanfare"),
]


PALETTES = [
    ("yellow", "cyan", "white", "blue"),
    ("green", "yellow", "cyan", "white"),
    ("red", "yellow", "white", "off"),
    ("blue", "cyan", "white", "violet"),
    ("white", "red", "yellow", "cyan"),
]


def choreography_steps(index: int) -> list[dict]:
    nose, left, center, right = PALETTES[index % len(PALETTES)]
    complement = PALETTES[(index + 2) % len(PALETTES)]
    ear_frames = [
        (0.0, 4 + (index % 4), 12 - (index % 4)),
        (1.6, 13, 3),
        (3.2, 2, 14),
        (4.8, 8, 8),
        (6.4, 15, 15),
        (8.1, 5, 11),
        (9.6, 8, 8),
    ]
    led_frames = [
        (0.0, "nose", nose),
        (0.2, "left", left),
        (0.4, "center", center),
        (0.6, "right", right),
        (1.8, "bottom", complement[0]),
        (2.2, "nose", complement[1]),
        (3.4, "left", complement[2]),
        (3.6, "center", complement[3]),
        (3.8, "right", complement[2]),
        (5.2, "nose", "white"),
        (6.6, "left", "off"),
        (6.8, "center", "off"),
        (7.0, "right", "off"),
        (7.4, "bottom", right),
        (8.6, "left", left),
        (8.8, "center", center),
        (9.0, "right", right),
        (9.8, "nose", "off"),
        (9.8, "left", "off"),
        (9.8, "center", "off"),
        (9.8, "right", "off"),
        (9.8, "bottom", "off"),
    ]

    steps = [
        {"at": at, "type": "ears", "left": left_position, "right": right_position}
        for at, left_position, right_position in ear_frames
    ]
    steps.extend(
        {"at": at, "type": "led", "target": target, "preset": preset}
        for at, target, preset in led_frames
    )
    return sorted(steps, key=lambda step: (float(step["at"]), step["type"]))


def convert_audio(*, ffmpeg: str, source: Path, destination: Path, start_seconds: float) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-v",
            "error",
            "-ss",
            f"{start_seconds:.3f}",
            "-i",
            str(source),
            "-t",
            "10",
            "-af",
            "afade=t=in:st=0:d=0.08,afade=t=out:st=9.4:d=0.6",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "96k",
            str(destination),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-audio-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--ffmpeg", default="/opt/local/bin/ffmpeg")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, (scene_id, relative_source, start_seconds, title) in enumerate(SCENES):
        source = args.source_audio_root / relative_source
        audio_name = f"{scene_id}.mp3"
        convert_audio(
            ffmpeg=args.ffmpeg,
            source=source,
            destination=args.output_dir / audio_name,
            start_seconds=start_seconds,
        )
        manifest.append(
            {
                "id": scene_id,
                "title": title,
                "duration_seconds": 10,
                "audio_asset": f"bundled-choreographies/{audio_name}",
                "source_audio": f"drakzlin music loops - {relative_source} @ {start_seconds:.1f}s",
                "steps": choreography_steps(index),
            }
        )

    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
