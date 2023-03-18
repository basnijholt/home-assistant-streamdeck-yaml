#!/bin/bash

# activate the micromamba environment
export MAMBA_EXE="$HOME/.local/bin/micromamba"
export MAMBA_ROOT_PREFIX="$HOME/micromamba"
eval "$($MAMBA_EXE shell hook --shell=bash --prefix $MAMBA_ROOT_PREFIX)"
micromamba activate streamdeck

home-assistant-streamdeck-yaml
