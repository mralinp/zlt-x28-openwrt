#!/bin/sh
set -eu

SSH_PORT=2222
HOST_KEY=/etc/dropbear/dropbear_ed25519_host_key
AUTHORIZED_KEYS=/etc/dropbear/authorized_keys

mkdir -p /etc/dropbear
chmod 700 /etc/dropbear

if [ ! -s "$HOST_KEY" ]; then
    dropbearkey -t ed25519 -f "$HOST_KEY"
fi

chmod 600 "$HOST_KEY"

if [ ! -s "$AUTHORIZED_KEYS" ]; then
    echo "ERROR: Install your SSH public key in $AUTHORIZED_KEYS first." >&2
    exit 1
fi

chmod 600 "$AUTHORIZED_KEYS"

if ! netstat -lnt 2>/dev/null | grep -q ":${SSH_PORT} "; then
    /usr/sbin/dropbear \
        -r "$HOST_KEY" \
        -p "192.168.70.1:${SSH_PORT}" \
        -s \
        -j \
        -k
fi

echo "Dropbear startup attempted on 192.168.70.1:${SSH_PORT}"