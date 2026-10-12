#!/usr/bin/env python3
"""Render a PDF into numbered PNG pages and a small manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Input PDF")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--first-page", type=int, default=1)
    parser.add_argument("--last-page", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.pdf.is_file():
        raise SystemExit(f"PDF not found: {args.pdf}")
    if args.dpi < 72 or args.dpi > 600:
        raise SystemExit("--dpi must be between 72 and 600")
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError as exc:
            raise SystemExit("PyMuPDF is required: pip install PyMuPDF") from exc

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    with pymupdf.open(args.pdf) as document:
        first = max(1, args.first_page)
        last = min(len(document), args.last_page or len(document))
        if first > last:
            raise SystemExit("Selected page range is empty")
        matrix = pymupdf.Matrix(args.dpi / 72.0, args.dpi / 72.0)
        width = max(3, len(str(len(document))))
        for page_number in range(first, last + 1):
            page = document[page_number - 1]
            output = args.output_dir / f"page_{page_number:0{width}d}.png"
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pixmap.save(output)
            manifest.append({
                "page": page_number,
                "file": output.name,
                "width": pixmap.width,
                "height": pixmap.height,
            })

    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Rendered {len(manifest)} pages to: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
