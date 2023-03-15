#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# activate the micromamba environment
export MAMBA_EXE="$HOME/.local/bin/micromamba"
export MAMBA_ROOT_PREFIX="$HOME/micromamba"
eval "$($MAMBA_EXE shell hook --shell=bash --prefix $MAMBA_ROOT_PREFIX)"
micromamba activate streamdeck

$SCRIPT_DIR/../home-assistant-streamdeck-yaml.py
