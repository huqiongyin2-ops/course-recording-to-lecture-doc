#!/usr/bin/env python3
"""Conservatively clean SRT, VTT, or plain-text transcripts."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

TIME_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?[,.]\d{3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?[,.]\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")
NOISE_RE = re.compile(
    r"^\s*(?:\[(?:music|applause|silence|noise|音乐|掌声|静音|噪声)\]|"
    r"(?:嗯+|呃+|额+|啊+|唔+)[，。！？,.!?]*)\s*$",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def normalize_time(value: str) -> str:
    parts = value.replace(",", ".").split(":")
    if len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    else:
        hours, minutes, seconds = parts
    whole_seconds = seconds.split(".")[0]
    return f"{int(hours):02d}:{int(minutes):02d}:{int(whole_seconds):02d}"


def clean_text(value: str) -> str:
    value = html.unescape(TAG_RE.sub("", value))
    value = re.sub(r"\s+", " ", value).strip()
    return "" if NOISE_RE.fullmatch(value) else value


def parse_captions(text: str) -> list[dict[str, str | None]]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text.strip())
    segments: list[dict[str, str | None]] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0].upper() == "WEBVTT":
            continue
        time_index = next((i for i, line in enumerate(lines) if TIME_RE.search(line)), None)
        if time_index is None:
            continue
        match = TIME_RE.search(lines[time_index])
        assert match is not None
        body = clean_text(" ".join(lines[time_index + 1 :]))
        if body:
            segments.append({
                "start": normalize_time(match.group("start")),
                "end": normalize_time(match.group("end")),
                "text": body,
            })
    return segments


def parse_plain(text: str) -> list[dict[str, str | None]]:
    segments = []
    for line in text.splitlines():
        body = clean_text(line)
        if body:
            segments.append({"start": None, "end": None, "text": body})
    return segments


def deduplicate(segments: list[dict[str, str | None]]) -> list[dict[str, str | None]]:
    result = []
    previous = None
    for segment in segments:
        normalized = re.sub(r"[\s，。！？,.!?]+", "", str(segment["text"])).casefold()
        if normalized and normalized != previous:
            result.append(segment)
            previous = normalized
    return result


def main() -> int:
    args = parse_args()
    if not args.transcript.is_file():
        raise SystemExit(f"Transcript not found: {args.transcript}")
    text = args.transcript.read_text(encoding="utf-8-sig")
    segments = parse_captions(text) if "-->" in text else parse_plain(text)
    segments = deduplicate(segments)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "json":
        content = json.dumps(segments, ensure_ascii=False, indent=2) + "\n"
    else:
        lines = [
            f"[{item['start']}] {item['text']}" if item["start"] else str(item["text"])
            for item in segments
        ]
        content = "\n\n".join(lines) + ("\n" if lines else "")
    args.output.write_text(content, encoding="utf-8")
    print(f"Wrote {len(segments)} transcript segments to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
