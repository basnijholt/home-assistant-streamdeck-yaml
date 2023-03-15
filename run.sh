#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# activate the micromamba environment
eval "$(~/.local/bin/micromamba shell hook -s posix)"
micromamba activate streamdeck

$SCRIPT_DIR/home-assistant-streamdeck-yaml.py
