#!/usr/bin/env sh

cd -- "$(dirname "$(readlink -f "$0")")"
python3 -m videoke "$@"
