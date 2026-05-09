#!/bin/sh
set -e

CERT_DIR="/etc/nginx/certs"
CERT_PATH="$CERT_DIR/server.crt"
KEY_PATH="$CERT_DIR/server.key"
CERT_CN="${CERT_CN:-skydaddy.local}"
CERT_DAYS="${CERT_DAYS:-365}"

if [ ! -s "$CERT_PATH" ] || [ ! -s "$KEY_PATH" ]; then
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -newkey rsa:2048 \
        -keyout "$KEY_PATH" \
        -out "$CERT_PATH" \
        -days "$CERT_DAYS" \
        -subj "/CN=$CERT_CN"
fi

exec nginx -g "daemon off;"

