#!/usr/bin/env bash
set -e

# Read options
CONFIG_PATH=/data/options.json
VOICE=$(jq -r '.voice // "af_heart"' ${CONFIG_PATH})
SAMPLE_RATE=$(jq -r '.sample_rate // 24000' ${CONFIG_PATH})
SPEED=$(jq -r '.speed // 1.0' ${CONFIG_PATH})
DEBUG=$(jq -r '.debug // false' ${CONFIG_PATH})

# Set debug flag
DEBUG_FLAG=""
if [ "${DEBUG}" = "true" ]; then
    DEBUG_FLAG="--debug"
fi

echo "=========================================="
echo "AI Hub TTS - Home Assistant Addon v1.0.4"
echo "=========================================="
echo "Voice: ${VOICE}"
echo "Sample Rate: ${SAMPLE_RATE}"
echo "Speed: ${SPEED}"
echo "Debug: ${DEBUG}"
echo "Model: Kokoro Multi-Lang v1.0"
echo "=========================================="

# Ensure model directory exists
mkdir -p /data/tts/models

# Start Wyoming TTS server
exec python3 -m wyoming_cosyvoice \
    --uri tcp://0.0.0.0:10301 \
    --model-path /data/tts/models \
    --voice "${VOICE}" \
    --sample-rate "${SAMPLE_RATE}" \
    --speed "${SPEED}" \
    ${DEBUG_FLAG}
