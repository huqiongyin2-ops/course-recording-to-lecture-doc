#!/usr/bin/env python3
"""Detect stable slide/demo scenes and save one clear frame per scene.

Reimplemented for the course workflow from event-video-recap 1.0.0 concepts
(integrated 2026-10-14). It uses the existing ffmpeg + Pillow stack and does
not import or call the source skill at runtime.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, nargs="?", help="Input lecture video")
    parser.add_argument("--frames-dir", type=Path, help="Use ordered pre-extracted frames")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between samples")
    parser.add_argument("--threshold", type=float, default=0.055, help="Normalized scene difference")
    parser.add_argument("--min-stable", type=float, default=2.0, help="Minimum scene duration")
    parser.add_argument("--save-width", type=int, default=1600)
    parser.add_argument("--max-shots", type=int, default=300)
    return parser.parse_args()


def timestamp(seconds: float) -> str:
    whole = max(0, int(round(seconds)))
    return f"{whole // 3600:02d}:{(whole % 3600) // 60:02d}:{whole % 60:02d}"


def extract_frames(video: Path, output: Path, interval: float) -> None:
    if not video.is_file():
        raise SystemExit(f"Video not found: {video}")
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required to sample video frames")
    output.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
        "-vf", f"fps=1/{interval}", "-q:v", "2", str(output / "sample_%07d.jpg"),
    ]
    subprocess.run(command, check=True)


def fingerprint(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        return ImageOps.grayscale(opened).resize((64, 36)).copy()


def frame_difference(left: Image.Image, right: Image.Image) -> float:
    difference = ImageChops.difference(left, right)
    return ImageStat.Stat(difference).mean[0] / 255.0


def sharpness(path: Path) -> float:
    with Image.open(path) as opened:
        grayscale = ImageOps.grayscale(opened).resize((640, 360))
        edges = grayscale.filter(ImageFilter.FIND_EDGES)
        return float(ImageStat.Stat(edges).var[0])


def save_frame(source: Path, destination: Path, save_width: int) -> tuple[int, int]:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        if image.width > save_width:
            height = max(1, round(image.height * save_width / image.width))
            image = image.resize((save_width, height), Image.Resampling.LANCZOS)
        image.save(destination, quality=92)
        return image.width, image.height


def main() -> int:
    args = parse_args()
    if (args.video is None) == (args.frames_dir is None):
        raise SystemExit("Provide exactly one VIDEO or --frames-dir")
    if not 0 < args.interval or not 0 < args.threshold <= 1:
        raise SystemExit("--interval must be positive and --threshold must be in (0, 1]")
    if args.min_stable < 0 or args.save_width <= 0 or args.max_shots <= 0:
        raise SystemExit("--min-stable, --save-width and --max-shots must be valid")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    shots_dir = args.output_dir / "frames"
    shots_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="lecture-scenes-") as temporary:
        frames_dir = args.frames_dir
        if frames_dir is None:
            frames_dir = Path(temporary)
            assert args.video is not None
            extract_frames(args.video, frames_dir, args.interval)
        if not frames_dir.is_dir():
            raise SystemExit(f"Frames directory not found: {frames_dir}")
        frame_files = sorted(
            path for path in frames_dir.iterdir()
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
        if not frame_files:
            raise SystemExit("No image frames found")

        fingerprints = [fingerprint(path) for path in frame_files]
        segments: list[tuple[int, int]] = []
        start = 0
        anchor = fingerprints[0]
        for index in range(1, len(frame_files)):
            if frame_difference(anchor, fingerprints[index]) >= args.threshold:
                segments.append((start, index))
                start = index
                anchor = fingerprints[index]
        segments.append((start, len(frame_files)))

        minimum_frames = max(1, round(args.min_stable / args.interval))
        stable_segments = [
            segment for position, segment in enumerate(segments)
            if position == 0 or segment[1] - segment[0] >= minimum_frames
        ][: args.max_shots]

        shots = []
        for number, (first, stop) in enumerate(stable_segments, start=1):
            middle = (first + stop - 1) // 2
            window = range(max(first, middle - 4), min(stop, middle + 5))
            best_index = max(window, key=lambda index: sharpness(frame_files[index]))
            time_seconds = best_index * args.interval
            destination = shots_dir / f"shot_{number:03d}_{timestamp(time_seconds).replace(':', '-')}.jpg"
            width, height = save_frame(frame_files[best_index], destination, args.save_width)
            shots.append({
                "shot": number,
                "file": f"frames/{destination.name}",
                "time_sec": round(time_seconds, 3),
                "time": timestamp(time_seconds),
                "scene_start": timestamp(first * args.interval),
                "scene_end": timestamp(stop * args.interval),
                "duration_sec": round((stop - first) * args.interval, 3),
                "sharpness": round(sharpness(frame_files[best_index]), 3),
                "width": width,
                "height": height,
                "review_status": "pending",
            })

    manifest = {
        "source": str(args.video or args.frames_dir),
        "interval_seconds": args.interval,
        "threshold": args.threshold,
        "min_stable_seconds": args.min_stable,
        "shot_count": len(shots),
        "note": "Stable scenes are candidates and require visual review before use.",
        "shots": shots,
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Saved {len(shots)} stable scene candidates to: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
