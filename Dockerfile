# Dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN set -eux; \
    # Modify debian.sources to explicitly include contrib and non-free components
    # This specifically targets lines that start with 'Components: main'
    sed -i -E 's/^(Components: main)$/\1 contrib non-free/' /etc/apt/sources.list.d/debian.sources; \
    \
    # Update package lists after modifying sources
    apt-get update; \
    \
    # Accept EULA for mscorefonts (needs to be before install)
    echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections; \
    \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        supervisor \
        fonts-dejavu-core \
        fonts-liberation2 \
        fonts-roboto-unhinted \
        ttf-mscorefonts-installer \
        imagemagick \
        fontconfig \
        wget \
        cabextract \
        xfonts-utils \
        && apt-get clean && rm -rf /var/lib/apt/lists/*



# Create non-root user
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup appuser

ENV PATH="/home/appuser/.local/bin:${PATH}"

COPY requirements.txt .

RUN mkdir -p /app/static/uploads && \
    mkdir -p /app/static/gifs

RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN chown -R appuser:appgroup /etc/supervisor/conf.d/supervisord.conf
RUN chown -R appuser:appgroup /app


USER appuser

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]