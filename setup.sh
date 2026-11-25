#!/bin/bash
# Recreate the working layout used by the engine: /home/claude/dua_videos and /home/claude/opendua
set -e
E=$(cd "$(dirname "$0")" && pwd)
mkdir -p /home/claude/dua_videos /home/claude/opendua
ln -sfn "$E/assets/opendua/audio" /home/claude/opendua/audio
ln -sfn "$E/assets/opendua/catalogue.json" /home/claude/opendua/catalogue.json
ln -sfn "$E/assets/nature" /home/claude/dua_videos/nature
ln -sfn "$E/assets/sfx" /home/claude/dua_videos/sfx_loops
ln -sfn "$E/assets/fonts" /home/claude/dua_videos/fonts
for f in "$E"/engine/*.py; do ln -sfn "$f" /home/claude/dua_videos/; done
ln -sfn "$E/state.json" /home/claude/dua_videos/state.json
ln -sfn "$E/RUNBOOK.md" /home/claude/dua_videos/RUNBOOK.md
echo "ready: cd /home/claude/dua_videos"
