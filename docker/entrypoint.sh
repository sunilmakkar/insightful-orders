#!/bin/sh
set -e

# Echo just for debugging
echo "Running entrypoint, command: $@"

# Pass control to whatever CMD/command is given
exec "$@"
