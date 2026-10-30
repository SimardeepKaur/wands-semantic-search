#!/bin/bash
# Assemble the Space repository layout into the given directory. Used by the
# deploy workflow and by local test builds, so both build the same thing.
set -e
out=$1
[ -n "$out" ] || { echo "usage: assemble.sh <out-dir>"; exit 1; }
root="$(cd "$(dirname "$0")/../.." && pwd)"

rm -rf "$out"
mkdir -p "$out/eval"
cp "$root/deploy/hf/Dockerfile" "$out/Dockerfile"
cp "$root/deploy/hf/start.sh" "$out/start.sh"
cp "$root/deploy/hf/README.md" "$out/README.md"
cp "$root/requirements-api.txt" "$out/requirements-api.txt"
cp -R "$root/src" "$out/src"
# only what the label export needs; the csvs themselves never enter the image
cp "$root/eval/run_eval.py" "$root/eval/export_demo_labels.py" "$out/eval/"
echo "assembled the Space repo into $out"
