#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: extract_audio.sh INPUT_VIDEO OUTPUT_AUDIO [--overwrite]

Extract a mono 16 kHz AAC audio track for speech transcription.
The source video is never modified.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ $# -lt 2 || $# -gt 3 ]]; then
  usage >&2
  exit 2
fi

input_video=$1
output_audio=$2
overwrite_flag=${3:-}
if [[ ! -f "$input_video" ]]; then
  echo "Input video not found: $input_video" >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required but was not found in PATH." >&2
  exit 1
fi
if [[ -e "$output_audio" && "$overwrite_flag" != "--overwrite" ]]; then
  echo "Output already exists; pass --overwrite to replace it: $output_audio" >&2
  exit 1
fi

mkdir -p "$(dirname "$output_audio")"
overwrite_args=(-n)
if [[ "$overwrite_flag" == "--overwrite" ]]; then
  overwrite_args=(-y)
fi
ffmpeg -hide_banner -loglevel error "${overwrite_args[@]}" \
  -i "$input_video" -map 0:a:0 -vn -ac 1 -ar 16000 \
  -c:a aac -b:a 64k "$output_audio"
echo "Audio written to: $output_audio"
