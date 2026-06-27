FROM python:3.12-slim

# Vremenska zona kontejnera -> cron raspored radi po lokalnom (hrvatskom) vremenu
ENV TZ=Europe/Zagreb
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata ca-certificates curl \
 && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
 && rm -rf /var/lib/apt/lists/*

# supercronic = cron prilagođen kontejnerima (nasljeđuje env varijable, loga na stdout).
# Ako gradiš na ARM64 (npr. Apple Silicon), promijeni SUPERCRONIC_ARCH u arm64.
ENV SUPERCRONIC_VERSION=v0.2.46 \
    SUPERCRONIC_ARCH=amd64
RUN curl -fsSLo /usr/local/bin/supercronic \
      "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${SUPERCRONIC_ARCH}" \
 && chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
