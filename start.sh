#!/bin/sh

set -e

echo "=== install deno ==="

curl -fsSL https://deno.land/install.sh | sh

export PATH="/root/.deno/bin:$PATH"

echo "=== cek deno ==="
which deno
deno --version

echo "=== jalankan bot ==="
exec python bot.py
