#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# The site-survey line parser of the iwinfo mtwifi backend, compiled alone out of the patch, on lines in the driver's format.
set -e
dir=$(mktemp -d); trap 'rm -rf "$dir"' EXIT
patch="$(dirname "$0")/../package/iwinfo-mtwifi/100-mtwifi-backend.patch"
sed -n '/^+\/\* begin mtwifi_scan_line/,/^+\/\* end mtwifi_scan_line/s/^+//p' "$patch" > "$dir/line.c"
cat > "$dir/t.c" <<'EOF'
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
enum { IWINFO_ESSID_MAX_SIZE = 32, IWINFO_OPMODE_MASTER = 1, IWINFO_OPMODE_ADHOC = 2, IWINFO_BAND_24 = 1, IWINFO_BAND_5 = 4 };
enum { IWINFO_KMGMT_8021x = 2, IWINFO_KMGMT_PSK = 4, IWINFO_KMGMT_SAE = 8, IWINFO_KMGMT_OWE = 16, IWINFO_AUTH_OPEN = 1, IWINFO_AUTH_SHARED = 2 };
enum { IWINFO_CIPHER_WEP40 = 1, IWINFO_CIPHER_TKIP = 2, IWINFO_CIPHER_CCMP = 4, IWINFO_CIPHER_WEP104 = 8, IWINFO_CIPHER_GCMP = 16, IWINFO_CIPHER_GCMP256 = 32, IWINFO_CIPHER_CCMP256 = 64 };
struct iwinfo_scanlist_entry {
	uint8_t mac[6]; char ssid[33]; int mode; uint8_t band, channel; uint32_t mhz; uint8_t signal, quality, quality_max;
	struct { uint8_t enabled, wpa_version; uint16_t group_ciphers, pair_ciphers; uint8_t auth_suites, auth_algs; } crypto;
	struct { uint8_t primary_chan, secondary_chan_off, chan_width; } ht_chan_info;
};
static int mtwifi_ch2mhz(int ch, int five) { return five ? 5000 + ch * 5 : 2407 + ch * 5; }
#include "line.c"
/* The driver's own formats: %-4d%-4d%-33s then BSSID, %-23s, %-9d, %-11s, %-7s, %-3s, " %-8d". */
static const char *row(char *b, int ch, const char *ssid, const char *sec, int pct, const char *ext, int slen)
{
	sprintf(b, "%-4d%-4d%-33s%s   %-23s%-9d%-11s%-7s%-3s %-8d NO  ", 0, ch, ssid, "aa:bb:cc:01:02:03", sec, pct, "11b/g/n", ext, " In", slen);
	return b;
}
int main(void)
{
	struct iwinfo_scanlist_entry e;
	char b[256];
	assert(!mtwifi_scan_line("", 0, &e) && !mtwifi_scan_line("Total=3   ", 0, &e));
	assert(!mtwifi_scan_line("No  Ch  SSID                             BSSID               Security               Siganl(%)W-Mode      ExtCH NT SSID_Len", 0, &e));
	assert(mtwifi_scan_line(row(b, 6, "My Home Net", "WPA2PSK/AES", 76, " ABOVE", 11), 0, &e));
	assert(!strcmp(e.ssid, "My Home Net") && e.channel == 6 && e.mhz == 2437 && e.band == IWINFO_BAND_24 && e.mode == IWINFO_OPMODE_MASTER);
	assert(e.mac[0] == 0xaa && e.mac[5] == 3 && e.signal - 0x100 == -60 && e.quality == 76 && e.quality_max == 100);
	assert(e.crypto.enabled && e.crypto.wpa_version == 2 && e.crypto.auth_suites == IWINFO_KMGMT_PSK && e.crypto.pair_ciphers == IWINFO_CIPHER_CCMP);
	assert(e.ht_chan_info.secondary_chan_off == 1 && e.ht_chan_info.chan_width == 1);
	assert(mtwifi_scan_line(row(b, 149, "open", "OPEN/NONE", 10, " NONE", 4), 1, &e));
	assert(!e.crypto.enabled && e.mhz == 5745 && e.band == IWINFO_BAND_5 && e.signal - 0x100 == -87 && !e.ht_chan_info.chan_width);
	assert(mtwifi_scan_line(row(b, 36, "", "WPA2PSKWPA3PSK/AES", 100, " BELOW", 0), 1, &e));
	assert(!e.ssid[0] && e.crypto.wpa_version == 6 && e.crypto.auth_suites == (IWINFO_KMGMT_PSK | IWINFO_KMGMT_SAE) && e.ht_chan_info.secondary_chan_off == 3);
	/* Too long for its column: the rest shifts, so it has to be read as tokens. */
	assert(mtwifi_scan_line(row(b, 1, "x", "WPA2PSKMIXWPA3PSK/TKIPAES", 50, " NONE", 1), 0, &e));
	assert(e.crypto.wpa_version == 6 && e.crypto.pair_ciphers == (IWINFO_CIPHER_TKIP | IWINFO_CIPHER_CCMP) && e.quality == 50);
	assert(mtwifi_scan_line(row(b, 1, "x", "FT-WPA2PSKWPA3PSK/CCMP256", 76, " NONE", 1), 0, &e));
	assert(e.crypto.pair_ciphers == IWINFO_CIPHER_CCMP256 && e.quality == 76);
	/* Not printable: hex. A printable SSID that looks like hex stays as it is. */
	assert(mtwifi_scan_line(row(b, 1, "0xD8B3D984", "WPA2/AES", 50, " NONE", 4), 0, &e));
	assert(!strcmp(e.ssid, "\xD8\xB3\xD9\x84") && e.crypto.auth_suites == IWINFO_KMGMT_8021x);
	assert(mtwifi_scan_line(row(b, 1, "0xABCD", "SHARED/WEP", 50, " NONE", 6), 0, &e));
	assert(!strcmp(e.ssid, "0xABCD") && e.crypto.enabled && !e.crypto.wpa_version && e.crypto.auth_algs == IWINFO_AUTH_SHARED);
	assert(mtwifi_scan_line(row(b, 1, "33-char-ssid-filling-the-column-", "OWE/AES", 50, " NONE", 32), 0, &e));
	assert(!strcmp(e.ssid, "33-char-ssid-filling-the-column-") && e.crypto.auth_suites == IWINFO_KMGMT_OWE);
	puts("PASS: mtwifi site-survey line parser");
	return 0;
}
EOF
${CC:-cc} -std=gnu99 -Wall -Wextra -Wno-unused-parameter -I"$dir" -o "$dir/t" "$dir/t.c"
"$dir/t"
