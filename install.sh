#!/usr/bin/env bash

set -Eeuo pipefail  # exit on any error
trap '>&2 echo "error: line $LINENO, status $?: $BASH_COMMAND"' ERR

slug=videoke

myname="${0##*/}"
mydir=$(dirname "$(readlink -f "$0")")

exec=${mydir}/${slug}.sh
desktop=${slug}.desktop
bindir=${XDG_BIN_HOME:-$HOME/.local/bin}
bin=$bindir/$slug
confdir=${XDG_CONFIG_HOME:-$HOME/.config}/$slug
config=$confdir/${slug}.ini

pip3 install --user --upgrade -r requirements.txt

# Read config or create a default one
if [[ ! -f "$config" ]]; then
	mkdir --parents --mode 700 -- "$confdir"
	cp -- "$mydir"/"$slug".ini.template "$config"
fi

mkdir --parents -- "$bindir"
rm -f -- "$bin"    && ln -s -- "$exec"      "$bin"


for icon in "$mydir"/${slug}*.png ; do
	size=$(identify -format '%w' "$icon" 2>/dev/null || echo 16)
	xdg-icon-resource install --noupdate --novendor --size "$size" "$icon" "videoke"
done
xdg-icon-resource forceupdate

xdg-desktop-menu install --novendor "$desktop"
