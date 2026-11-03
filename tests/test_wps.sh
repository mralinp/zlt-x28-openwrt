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
echo "PASS: WPS button opens only enabled WPA2-PSK access-point networks"
