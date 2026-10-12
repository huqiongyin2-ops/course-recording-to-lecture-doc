#!/usr/bin/env python3
"""Sample a lecture video and rank frames that may contain visual changes."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageStat


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, nargs="?", help="Input lecture video")
    parser.add_argument("--frames-dir", type=Path, help="Use pre-extracted frames instead")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-every", type=float, default=5.0, help="Seconds between frames")
    parser.add_argument("--min-change", type=float, default=0.035)
    parser.add_argument("--min-gap", type=float, default=20.0, help="Seconds between candidates")
    parser.add_argument("--roi", help="Normalized x,y,width,height; for example 0,0,0.6,1")
    parser.add_argument("--max-candidates", type=int, default=120)
    return parser.parse_args()


def parse_roi(value: str | None) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    try:
        roi = tuple(float(item) for item in value.split(","))
    except ValueError as exc:
        raise SystemExit("--roi requires four numbers: x,y,width,height") from exc
    if len(roi) != 4:
        raise SystemExit("--roi requires four numbers: x,y,width,height")
    x, y, width, height = roi
    if min(roi) < 0 or x + width > 1 or y + height > 1 or width <= 0 or height <= 0:
        raise SystemExit("--roi must fit inside normalized image coordinates")
    return x, y, width, height


def crop_roi(image: Image.Image, roi: tuple[float, float, float, float] | None) -> Image.Image:
    if roi is None:
        return image
    x, y, width, height = roi
    left, top = int(x * image.width), int(y * image.height)
    right, bottom = int((x + width) * image.width), int((y + height) * image.height)
    return image.crop((left, top, right, bottom))


def extract_frames(video: Path, output: Path, sample_every: float) -> None:
    if not video.is_file():
        raise SystemExit(f"Video not found: {video}")
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required to sample video frames")
    output.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
        "-vf", f"fps=1/{sample_every}", "-q:v", "2", str(output / "sample_%06d.jpg"),
    ]
    subprocess.run(command, check=True)


def image_metrics(previous: Image.Image, current: Image.Image) -> tuple[float, float]:
    previous = previous.convert("L").resize((320, 180))
    current = current.convert("L").resize((320, 180))
    difference = ImageChops.difference(previous, current)
    change = ImageStat.Stat(difference).mean[0] / 255.0
    edges = current.filter(ImageFilter.FIND_EDGES)
    edge_score = min(1.0, ImageStat.Stat(edges).mean[0] / 48.0)
    return change, edge_score


def timestamp(seconds: float) -> str:
    whole = int(round(seconds))
    return f"{whole // 3600:02d}:{(whole % 3600) // 60:02d}:{whole % 60:02d}"


def main() -> int:
    args = parse_args()
    if (args.video is None) == (args.frames_dir is None):
        raise SystemExit("Provide exactly one VIDEO or --frames-dir")
    if args.sample_every <= 0 or args.min_gap < 0 or args.max_candidates <= 0:
        raise SystemExit("Sampling values must be positive")
    roi = parse_roi(args.roi)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    selected_dir = args.output_dir / "frames"
    selected_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="lecture-frames-") as temporary:
        frames_dir = args.frames_dir
        if frames_dir is None:
            frames_dir = Path(temporary)
            assert args.video is not None
            extract_frames(args.video, frames_dir, args.sample_every)
        if not frames_dir.is_dir():
            raise SystemExit(f"Frames directory not found: {frames_dir}")
        frame_files = sorted(
            path for path in frames_dir.iterdir()
            if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )
        if len(frame_files) < 2:
            raise SystemExit("At least two sampled frames are required")

        candidates = []
        with Image.open(frame_files[0]) as opened:
            previous = crop_roi(opened.copy(), roi)
        last_selected = -float("inf")
        for index, frame_path in enumerate(frame_files[1:], start=1):
            seconds = index * args.sample_every
            with Image.open(frame_path) as opened:
                current = crop_roi(opened.copy(), roi)
            change, edge_score = image_metrics(previous, current)
            previous = current
            if change < args.min_change or seconds - last_selected < args.min_gap:
                continue
            destination = selected_dir / f"{timestamp(seconds).replace(':', '-')}_{frame_path.name}"
            shutil.copy2(frame_path, destination)
            candidates.append({
                "timestamp": timestamp(seconds),
                "seconds": round(seconds, 3),
                "file": f"frames/{destination.name}",
                "change_score": round(change, 6),
                "edge_score": round(edge_score, 6),
                "rank_score": round(change * 0.75 + edge_score * 0.25, 6),
                "review_status": "pending",
            })
            last_selected = seconds
            if len(candidates) >= args.max_candidates:
                break

    manifest = {
        "source": str(args.video or args.frames_dir),
        "sample_every_seconds": args.sample_every,
        "roi": roi,
        "candidate_count": len(candidates),
        "note": "Candidates require visual review; change detection alone cannot identify board writing.",
        "candidates": candidates,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fields = list(candidates[0].keys()) if candidates else ["timestamp"]
    with (args.output_dir / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(candidates)
    print(f"Selected {len(candidates)} candidate frames in: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
