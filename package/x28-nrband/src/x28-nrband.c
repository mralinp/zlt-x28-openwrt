// SPDX-License-Identifier: GPL-2.0-only
/*
 * 5G (NR) band mask of the X28 modem over MIPC, using only the generic calls libmipc_msg.so exports.
 * GET option 0 = current setting, 1 = what the hardware supports (observed after a restriction).
 * Message and TLV ids come from the vendor ql_ril_service handlers: GET_BAND_MODE 0x431 (TLV 0x100 option),
 * SET_BAND_MODE 0x433, replies and requests carry umts 0x101 (4 B), lte 0x102 (32 B), nr 0x103 (128 B = 32 words);
 * NR band n is bit n-1.
 *   x28-nrband get          support=<w0> <w1> <w2>  current=<w0> <w1> <w2>
 *   x28-nrband set w0 w1 w2 set the NR mask (hex words), must be non-zero and within the supported bands
 *   x28-nrband signal       rat=<hex> (MIPC_NW_GET_PS_REQ 0x40d, reply TLV 0x104: u16 at offset 1; 1000 LTE, 2000 LTE CA, 4000 EN-DC, 8000 NR)
 *                           nr=<rsrp> <rsrq> as positive numbers (MIPC_NW_GET_SIGNAL_REQ 0x411, reply TLV 0x10e, 28 B of int32: the
 *                           NR block; field order inferred from Android's signal structs and the vendor LED code, not yet checked
 *                           against the vendor UI's 5G values). Ids from ql_ril_service (#492).
 *   x28-nrband selftest     decode check against a captured reply, no modem needed
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct mipc_msg mipc_msg_t;
mipc_msg_t *mipc_msg_init(uint16_t id, uint32_t ps);
int mipc_msg_add_tlv(mipc_msg_t *m, uint16_t tlv, uint16_t len, const void *val);
mipc_msg_t *mipc_msg_sync_timeout(mipc_msg_t *m);
void *mipc_msg_get_val_ptr(mipc_msg_t *m, uint16_t tlv, uint16_t *len);
void mipc_msg_deinit(mipc_msg_t *m);
void mipc_msg_set_timeout_once(uint32_t ms);
int mipc_init(const char *name);
void mipc_deinit(void);

#define NR_WORDS 32

static int result(mipc_msg_t *cnf)
{
	uint16_t len = 0;
	uint32_t *r = cnf ? mipc_msg_get_val_ptr(cnf, 0, &len) : NULL;
	return r && len == 4 ? (int)*r : -1;
}

/* 1 to 8 hex digits and nothing else */
static int word(const char *s, uint32_t *w)
{
	char *end;
	size_t n = strlen(s);

	if (n < 1 || n > 8 || strspn(s, "0123456789abcdefABCDEF") != n)
		return -1;
	*w = (uint32_t)strtoul(s, &end, 16);
	return *end ? -1 : 0;
}

static int get_nr(uint8_t option, uint32_t *w)
{
	mipc_msg_t *req = mipc_msg_init(0x431, 0x10), *cnf;
	uint16_t len = 0;
	uint8_t *p;
	int rc = -1;

	if (!req)
		return -1;
	mipc_msg_add_tlv(req, 0x100, 1, &option);
	mipc_msg_set_timeout_once(5000);
	cnf = mipc_msg_sync_timeout(req);
	if (result(cnf) == 0 && (p = mipc_msg_get_val_ptr(cnf, 0x103, &len)) && len == NR_WORDS * 4) {
		memcpy(w, p, NR_WORDS * 4);
		rc = 0;
	}
	if (cnf)
		mipc_msg_deinit(cnf);
	return rc;
}

/* TLV 0x10e of the signal reply: int32 w[0..6] = ?, ss_rsrp, ss_rsrq, ...; 255 or 0 mean no measurement. */
static int nr_decode(const uint8_t *p, uint16_t len, int *rsrp, int *rsrq)
{
	int32_t w[7];

	if (len != sizeof(w))
		return -1;
	memcpy(w, p, sizeof(w));
	if (w[1] <= 0 || w[1] > 140 || w[2] <= 0 || w[2] > 40)
		return -1;
	*rsrp = w[1];
	*rsrq = w[2];
	return 0;
}

static mipc_msg_t *ask(uint16_t id)
{
	mipc_msg_t *req = mipc_msg_init(id, 0x10);

	if (!req)
		return NULL;
	mipc_msg_set_timeout_once(5000);
	return mipc_msg_sync_timeout(req);
}

static int signal_cmd(void)
{
	mipc_msg_t *cnf = ask(0x40d);
	uint16_t len = 0;
	uint8_t *p;
	int rsrp, rsrq, rc = 1;

	if (!cnf)
		return 1;
	if ((p = mipc_msg_get_val_ptr(cnf, 0x104, &len)) && len >= 3) {
		printf("rat=%04x\n", p[1] | p[2] << 8);
		rc = 0;
	}
	mipc_msg_deinit(cnf);
	if (rc || !(cnf = ask(0x411)))
		return rc;
	if ((p = mipc_msg_get_val_ptr(cnf, 0x10e, &len)) && !nr_decode(p, len, &rsrp, &rsrq))
		printf("nr=%d %d\n", rsrp, rsrq);
	mipc_msg_deinit(cnf);
	return rc;
}

static int selftest(void)
{
	/* captured on the old unit (EN-DC, 2026-11-09) */
	static const uint8_t nr[28] = { 0x17, 0, 0, 0, 0x50, 0, 0, 0, 0x0e, 0, 0, 0, 0x01, 0, 0, 0,
					0x01, 0xe0, 0xff, 0xff, 0x01, 0xe0, 0xff, 0xff, 0xff, 0x1f, 0, 0 };
	static const uint8_t none[28] = { 0 };
	int rsrp = 0, rsrq = 0;

	if (nr_decode(nr, 28, &rsrp, &rsrq) || rsrp != 80 || rsrq != 14 || !nr_decode(none, 28, &rsrp, &rsrq) || !nr_decode(nr, 24, &rsrp, &rsrq)) {
		puts("selftest failed");
		return 1;
	}
	puts("selftest ok");
	return 0;
}

int main(int argc, char **argv)
{
	uint32_t support[NR_WORDS], cur[NR_WORDS], want[NR_WORDS];
	int rc = 1;

	setvbuf(stdout, NULL, _IONBF, 0);
	if (argc == 2 && !strcmp(argv[1], "selftest"))
		return selftest();
	if (argc < 2 || mipc_init("mipc_wan_cli"))
		return 2;
	if (argc == 2 && !strcmp(argv[1], "signal")) {
		rc = signal_cmd();
		mipc_deinit();
		return rc;
	}
	if (get_nr(1, support) || get_nr(0, cur)) {
		puts("error=read");
		goto out;
	}
	if (!strcmp(argv[1], "get") && argc == 2) {
		printf("support=%08x %08x %08x\ncurrent=%08x %08x %08x\n", support[0], support[1], support[2], cur[0], cur[1], cur[2]);
		rc = 0;
	} else if (!strcmp(argv[1], "set") && argc == 5) {
		mipc_msg_t *req, *cnf;
		memset(want, 0, sizeof(want));
		for (int i = 0; i < 3; i++)
			if (word(argv[2 + i], &want[i])) {
				puts("error=mask");
				goto out;
			}
		if (!(want[0] | want[1] | want[2]) || (want[0] & ~support[0]) || (want[1] & ~support[1]) || (want[2] & ~support[2])) {
			puts("error=mask");
			goto out;
		}
		req = mipc_msg_init(0x433, 0x10);
		if (!req)
			goto out;
		mipc_msg_add_tlv(req, 0x103, NR_WORDS * 4, want);
		mipc_msg_set_timeout_once(10000);
		cnf = mipc_msg_sync_timeout(req);
		printf("result=%d\n", result(cnf));
		rc = result(cnf) == 0 ? 0 : 1;
		if (cnf)
			mipc_msg_deinit(cnf);
	}
out:
	mipc_deinit();
	return rc;
}
