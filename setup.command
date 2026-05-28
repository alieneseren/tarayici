#!/bin/bash
set -e
cd "$(dirname "$0")"
./setup_macos.sh

echo
read -r -p "Press Enter to close..." _
