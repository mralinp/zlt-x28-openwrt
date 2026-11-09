#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Runs package/x28-sysupgrade against simulated NAND (nandsim: 4 KiB pages, 256 KiB blocks, SLC) with the real UBI, mtd-utils and
# busybox, in QEMU inside Docker (arm64, TCG; a few minutes). Not part of CI. The vendor dd-nand is replaced by flash_erase + nandwrite.
# Needs Docker. Usage: sh tests/qemu-sysupgrade/run.sh
set -e
here=$(cd "$(dirname "$0")" && pwd)
w=$(mktemp -d); trap 'rm -rf "$w"' EXIT
cp "$here"/build.sh "$here"/init "$here"/test_guest.sh "$here/../../package/x28-sysupgrade/files/lib/upgrade/x28.sh" "$w/"
docker run --rm --platform linux/arm64 -v "$w:/x28:ro" ubuntu:22.04 bash /x28/build.sh
