FROM qdrant/qdrant:v1.20.0

# Qdrant runs as root in the pinned official image. Install curl only for the
# Compose readiness probe; do not alter Qdrant binaries or configuration.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
