#!/bin/sh
set -eu
umask 077
readonly key_path=/run/secrets/sarah_api_key
readonly db=/var/lib/sarah/state.db
test -s "$key_path" || { printf 'Missing Sarah API key file\n' >&2; exit 1; }
python -m bridge.provision_device --db "$db" --device android --token-file "$key_path"
exec python -m bridge.server --db "$db" "$@"
