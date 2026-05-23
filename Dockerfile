# Multi-arch image: linux/amd64 + linux/arm/v7
# Build with: docker buildx build --platform linux/amd64,linux/arm/v7 -t caddy-gui .

FROM python:3.14-alpine

# Non-root user for reduced attack surface
RUN addgroup -S appuser && adduser -S -G appuser appuser

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# The app runs as non-root, but needs access to /var/run/docker.sock
# Handle this by adding the user to the docker group at runtime if needed,
# or by setting the socket permissions via compose.
# Default: run as appuser (override with --user root if socket access fails)
USER appuser

EXPOSE 5000

ENV CADDYFILE_PATH=/caddyfile/Caddyfile \
    CADDY_CONTAINER=caddy \
    CADDY_CONFIG_PATH=/etc/caddy/Caddyfile \
    CADDY_CERT_PATH=/caddydata/pki/authorities/local/root.crt \
    PORT=5000 \
    SELF_HOSTNAME=

CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
