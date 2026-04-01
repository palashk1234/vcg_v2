#!/bin/bash
set -e

# Run the directory setup
bash setup.sh

# Start the Gradio Web UI
echo "Starting Gradio Web UI..."
python webui.py