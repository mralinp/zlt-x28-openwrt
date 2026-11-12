#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Which networks the WPS button opens; the UCI lookups are replaced with a table, no driver involved.
set -e
here=$(dirname "$0")/../package/x28-wifi/files
MTWIFI_SH=$here/mtwifi.sh X28_WPS_TEST=1 . "$here/x28-wps"
# config_get <var> <section> <option> [default]: reads c_<section>_<option>.
config_get() { eval "$1=\"\${c_$2_$3:-$4}\""; }
net() { wps_net "$1"; }
c_a_wps_pushbutton=1 c_a_encryption=psk2 c_a_device=radio_2g
c_b_wps_pushbutton=1 c_b_encryption=sae-mixed c_b_device=radio_5g
c_c_wps_pushbutton=1 c_c_encryption=sae c_c_device=radio_5g
c_d_wps_pushbutton=0 c_d_encryption=psk2 c_d_device=radio_5g
c_e_wps_pushbutton=1 c_e_encryption=psk2 c_e_device=radio_5g c_e_disabled=1
c_f_wps_pushbutton=1 c_f_encryption=psk2 c_f_device=radio_5g c_radio_5g_disabled=
c_g_wps_pushbutton=1 c_g_encryption=psk2 c_g_device=radio_2g c_g_mode=sta
[ "$(net a)" = ra0 ] && [ "$(net b)" = rai0 ] && [ "$(net f)" = rai0 ] || exit 1
[ -z "$(net c)" ] && [ -z "$(net d)" ] && [ -z "$(net e)" ] && [ -z "$(net g)" ] || exit 1  # WPA3-only, off, disabled, client
c_radio_5g_disabled=1
[ -z "$(net b)" ] || exit 1  # its radio is disabled
# wps_down <event> <key>: only the WPS key-down (the driver also reports key-up, and the reset button as key 1).
wps_down 1 2 && ! wps_down 2 2 && ! wps_down 1 1 && ! wps_down 2 1 || exit 1
# reset_step <event> <key> <ms>: the reset hold (#551). Time is faked: T is "now" in seconds.
T=1100; now() { echo $T; }
down_up() { reset_step "$@" || :; }                      # key-down and key-up only move the state
hold() { T=$(($1 + $3 / 1000)); reset_step 3 "$2" "$3"; }   # a tick read on time, for a hold that began at $1
down_up 1 1 0; ! hold 1100 1 4000 && ! hold 1100 1 9000 && hold 1100 1 10000 || exit 1  # fires at the 10 s tick
! hold 1100 1 11000 || exit 1                                                             # once per hold
T=200; down_up 1 1 0; ! hold 200 1 9000 || exit 1; down_up 2 1 9400; ! hold 200 1 10000 || exit 1  # released before 10 s
T=300; down_up 1 2 0; ! hold 300 2 10000 || exit 1                                    # the WPS key never resets
T=100; down_up 1 1 0; ! hold 100 1 10000 || exit 1                                    # too soon after boot (x28-bootok)
reset_t0=; T=400; ! reset_step 3 1 60000 || exit 1                                       # down since boot: no key-down seen
T=500; down_up 1 1 0; ! reset_step 3 1 40000 || exit 1; T=520; ! reset_step 3 1 60000 || exit 1  # a stale key-down from the queue
echo "PASS: the reset button resets only at 10 s of a hold this service watched from its key-down"
echo "PASS: WPS button opens only enabled WPA2-PSK access-point networks, on its own key-down"
