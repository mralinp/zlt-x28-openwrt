#!/usr/bin/env python3
"""Step 5: read the SoC's boot-security config over the preloader USB port.

Runs `mtk gettargetconfig --skipwdt`: handshake plus read-only preloader commands
(HW code, SBC/SLA/DAA flags, ME_ID). No download agent, no flash access, and the
watchdog register is left alone. Afterwards the modem sits in the preloader until
its power is cycled.

    python3 tools/recovery/target_config.py
"""
import re
import sys

from common import run_mtk

code, out = run_mtk(["gettargetconfig", "--skipwdt"], "target-config.log")
log = (out / "target-config.log").read_text()
flags = dict(re.findall(r"\t(SBC|SLA|DAA) enabled:\t+(True|False)", log))
if flags:
    print("\nsummary:", ", ".join(f"{k}={'on' if v == 'True' else 'off'}" for k, v in flags.items()))
print("cycle the modem's power to boot it normally")
sys.exit(code)
