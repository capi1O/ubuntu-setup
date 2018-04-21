#!/bin/bash

REPO_DIR=$(cd $(dirname $0) && pwd)

# boot menu customization
./grub.sh

# login customization
./gdm.sh

# shell customization (dash, taskbar, top-panel, menubar
./gnome.sh

# disable volume limit
./sound.sh

# fix AD2P bugs
./bluetooth.sh
