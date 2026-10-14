#!/usr/bin/env python3
"""Create labeled contact sheets from board or stable-scene manifests.

Adapted from event-video-recap 1.0.0's contact-sheet workflow on 2026-10-14.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start", type=float, default=0.0, help="Inclusive start time in seconds")
    parser.add_argument("--end", type=float, default=math.inf, help="Exclusive end time in seconds")
    parser.add_argument("--name", default="sheet")
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--rows", type=int, default=3)
    parser.add_argument("--cell-width", type=int, default=480)
    parser.add_argument("--cell-height", type=int, default=270)
    return parser.parse_args()


def timestamp(seconds: float) -> str:
    whole = max(0, int(round(seconds)))
    return f"{whole // 3600:02d}:{(whole % 3600) // 60:02d}:{whole % 60:02d}"


def load_items(manifest_path: Path) -> list[dict[str, object]]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_items = data.get("shots") or data.get("candidates") or []
    items = []
    for position, item in enumerate(raw_items, start=1):
        seconds = float(item.get("time_sec", item.get("seconds", 0.0)))
        file_path = Path(str(item["file"]))
        if not file_path.is_absolute():
            file_path = manifest_path.parent / file_path
        items.append({
            "number": int(item.get("shot", position)),
            "seconds": seconds,
            "time": str(item.get("time", item.get("timestamp", timestamp(seconds)))),
            "file": file_path,
        })
    return items


def main() -> int:
    args = parse_args()
    if not args.manifest.is_file():
        raise SystemExit(f"Manifest not found: {args.manifest}")
    if args.start < 0 or args.end <= args.start:
        raise SystemExit("--start/--end define an invalid time range")
    if min(args.columns, args.rows, args.cell_width, args.cell_height) <= 0:
        raise SystemExit("Grid and cell dimensions must be positive")

    selected = [
        item for item in load_items(args.manifest)
        if args.start <= float(item["seconds"]) < args.end
    ]
    if not selected:
        print("No candidates found in the requested time range")
        return 0

    missing = [str(item["file"]) for item in selected if not Path(item["file"]).is_file()]
    if missing:
        raise SystemExit(f"Candidate image not found: {missing[0]}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    label_height = 30
    per_page = args.columns * args.rows
    pages = [selected[index:index + per_page] for index in range(0, len(selected), per_page)]
    for page_number, page in enumerate(pages, start=1):
        row_count = math.ceil(len(page) / args.columns)
        sheet = Image.new(
            "RGB",
            (args.columns * args.cell_width, row_count * (args.cell_height + label_height)),
            (18, 18, 18),
        )
        draw = ImageDraw.Draw(sheet)
        for position, item in enumerate(page):
            row, column = divmod(position, args.columns)
            x = column * args.cell_width
            y = row * (args.cell_height + label_height)
            with Image.open(Path(item["file"])) as opened:
                image = ImageOps.contain(
                    ImageOps.exif_transpose(opened).convert("RGB"),
                    (args.cell_width, args.cell_height),
                    Image.Resampling.LANCZOS,
                )
            image_x = x + (args.cell_width - image.width) // 2
            image_y = y + label_height + (args.cell_height - image.height) // 2
            sheet.paste(image, (image_x, image_y))
            draw.rectangle((x, y, x + args.cell_width, y + label_height), fill=(0, 0, 0))
            draw.text(
                (x + 8, y + 8),
                f"#{int(item['number']):03d}  {item['time']}",
                fill=(255, 230, 120),
            )
        output = args.output_dir / f"{args.name}_p{page_number:02d}.jpg"
        sheet.save(output, quality=90)
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
