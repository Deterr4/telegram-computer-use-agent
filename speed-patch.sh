#!/bin/bash
# Cut the hardcoded pause before every screenshot.
#
# computer.py waits _screenshot_delay seconds after each action so the screen
# can settle before it is captured. The shipped 2.0s is conservative: on a
# 23-step task that is ~46 seconds of pure waiting. 0.6s is enough for most
# UI updates; raise it again if the agent starts acting on half-drawn pages.
#
# Re-run this after any `docker pull` - a new image ships the original value.

DELAY="${1:-0.6}"
F=/home/computeruse/computer_use_demo/tools/computer.py

current=$(grep -oP '_screenshot_delay = \K[0-9.]+' "$F" | head -1)
echo "screenshot delay: ${current}s -> ${DELAY}s"

sed -i "s/_screenshot_delay = [0-9.]*/_screenshot_delay = ${DELAY}/" "$F"

grep -n "_screenshot_delay = " "$F"
