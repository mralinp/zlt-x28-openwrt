#!/usr/bin/env python3
"""Step 6b: read a partition over USB *by name* and compare it with the backup.

The download agent mtkclient bundles for this chip rejects READ-FLASH (raw offset)
and READ-PARTITION-TABLE as unsupported, so this asks for one partition by name
(READ-PARTITION) first, then for the partition table. Both are read-only DA
commands; nothing is written or erased. Results go to private/usb-probe/<date>/.

The modem must be unpowered when this starts; plug it in once it says it is waiting.

    python3 tools/recovery/read_by_name.py [lk_b] [--backup DIR]
"""
import argparse
import logging
import os
import re
import sys
from pathlib import Path

from common import DEFAULT_BACKUP, MTK, VENDOR_DA, backup_partition, probe_dir, sha256_file

# mtkclient lives in the private venv; re-run there if started with another interpreter
VENV_PY = MTK.with_name("python")
if os.path.realpath(sys.executable) != os.path.realpath(VENV_PY):
    if not VENV_PY.exists():
        sys.exit("mtkclient not installed: run tools/recovery/setup_mtkclient.py")
    os.execv(VENV_PY, [str(VENV_PY), *sys.argv])

from mtkclient.config.mtk_config import MtkConfig  # noqa: E402
from mtkclient.Library.DA.mtk_da_handler import DaHandler  # noqa: E402
from mtkclient.Library.DA.xmlflash.xml_lib import UpFile  # noqa: E402
from mtkclient.Library.Partitions.gpt import GptSettings  # noqa: E402
from mtkclient.Library.mtk_class import Mtk  # noqa: E402


def connect(out, loader):
    """Preloader handshake (watchdog untouched) and DA upload, as `mtk` does for DA commands."""
    config = MtkConfig(loglevel=logging.INFO, gui=None, guiprogress=None)
    config.skipwdt = True
    if loader:
        config.loader = str(loader.resolve())
    config.gpt_settings = GptSettings(0, 0, 0)
    mtk = Mtk(config=config, loglevel=logging.INFO)
    config.set_peek(mtk.daloader.peek)
    handler = DaHandler(mtk, logging.INFO)
    print("modem power must be OFF now; plug it in when mtkclient is waiting", flush=True)
    mtk = handler.connect(mtk, str(out))
    mtk = mtk and handler.configure_da(mtk)
    if mtk is None:
        sys.exit("could not reach the download agent")
    return mtk


def read_partition(da, name):
    """READ-PARTITION <name>; returns the bytes, or None if the DA refuses."""
    reply = da.send_command(da.cmd.cmd_read_partition(name), noack=True)
    if reply is not True:  # a refusal comes back as the DA's XML reply text; False = no reply
        print(f"READ-PARTITION {name}: {'no reply from DA' if reply is False else f'refused: {reply!r}'}")
        return None
    _, result = da.get_command_result()
    if type(result) is not UpFile:
        print(f"READ-PARTITION {name}: no data offered: {result!r}")
        return None
    data = da.download_raw(result=result, display=True)
    da.get_command_result()  # CMD:END / CMD:START
    return bytes(data) if data else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("partition", nargs="?", default="lk_b")
    ap.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)
    ap.add_argument("--loader", type=Path, default=VENDOR_DA if VENDOR_DA.is_file() else None,
                    help="download agent file (default: the vendor DA in private/, if present)")
    args = ap.parse_args()
    part, expected = backup_partition(args.backup, args.partition)

    loader = args.loader and args.loader.resolve()  # before chdir below
    out = probe_dir()
    os.chdir(out)  # mtkclient drops its hwparam/state files in the working directory
    mtk = connect(out, loader)
    da = mtk.daloader.da
    try:
        # READ-PARTITION goes first: after a refused command this DA stops answering
        data = read_partition(da, args.partition)
        table, _ = da.read_partition_table()
        if table:
            text = table.decode(errors="replace") if isinstance(table, bytes) else table
            (out / "da-partition-table.xml").write_text(text)
            rows = re.findall(r"<name>(.*?)</name><start>(.*?)</start><size>(.*?)</size>", text)
            print(f"READ-PARTITION-TABLE: {len(rows)} entries (saved da-partition-table.xml)")
            for name, start, size in rows:
                print(f"  {name:<18} start {start:>12} size {size}")
        else:
            print("READ-PARTITION-TABLE: no data")
    finally:
        print("cycle the modem's power to boot it normally")
        mtk.port.close()

    if data is None:
        sys.exit(1)
    path = out / f"{args.partition}-usb-by-name.bin"
    path.write_bytes(data)
    actual = sha256_file(path)
    print(f"read     {len(data):#x} bytes, sha256 {actual}")
    print(f"backup   {part['size']:#x} bytes, sha256 {expected}")
    print("MATCH" if actual == expected else "MISMATCH")
    sys.exit(0 if actual == expected else 1)


if __name__ == "__main__":
    main()
