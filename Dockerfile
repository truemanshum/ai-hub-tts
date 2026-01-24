ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tts

# Install Python dependencies
COPY requirements.txt /tts/
RUN pip3 install --no-cache-dir -r /tts/requirements.txt && \
    rm -rf /root/.cache/pip

# Copy application code
COPY wyoming_cosyvoice /tts/wyoming_cosyvoice
COPY run.sh /tts/

# Set permissions
RUN chmod +x /tts/run.sh

# Set environment variables for memory optimization
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MALLOC_ARENA_MAX=2

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import socket; s=socket.socket(); s.settimeout(5); s.connect(('localhost',10301)); s.close()" || exit 1

CMD ["/tts/run.sh"]
