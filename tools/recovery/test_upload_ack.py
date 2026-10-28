#!/usr/bin/env python3
"""Host-only upload completion regression; optionally exercise a pinned xml_lib.py."""
import ast
from pathlib import Path
from types import SimpleNamespace
import sys
import textwrap
import unittest

from setup_mtkclient import PATCHES

# Authored completion fixture: END requires one ACK; START is ACKed by its reader.
FIXTURE = '''def upload(self, result, data, display=True, raw=False):
    if True:
        if True:
            if True:
                if raw:
                    self.ack()
                cmd, result = self.get_command_result()
                self.ack()
                if cmd == "CMD:END" and result == "OK":
                    cmd, result = self.get_command_result()
                    return cmd == "CMD:START"
'''


class Peer:
    def __init__(self):
        self.state = 'end_pending'
        self.mtk = SimpleNamespace(config=SimpleNamespace(guiprogress=None))

    def ack(self):
        if self.state == 'end_read':
            self.state = 'start_pending'
        elif self.state == 'start_read':
            self.state = 'ready'
        else:
            raise AssertionError('unsolicited ACK where XML command is required')

    def get_command_result(self):
        if self.state == 'end_pending':
            self.state = 'end_read'
            return 'CMD:END', 'OK'
        assert self.state == 'start_pending'
        self.state = 'start_read'
        self.ack()  # The real command reader acknowledges START itself.
        return 'CMD:START', None

    def ack_value(self, value):
        pass

    def get_response(self):
        return 'OK'

    def xsend(self, **kwargs):
        pass


def patched(source):
    for _, old, new, _ in PATCHES:
        if old in source:
            assert source.count(old) == 1
            source = source.replace(old, new)
    return source


def exercise(source, raw):
    class DwnFile:
        source_file = ''
        packet_length = 4
    ns = {'DwnFile': DwnFile, 'progress': lambda **kw: None}
    exec(source, ns)
    peer = Peer()
    assert ns['upload'](peer, DwnFile(), b'test', display=False, raw=raw)
    assert peer.state == 'ready'  # A following READ can now be sent as XML.


class CompletionTests(unittest.TestCase):
    def test_original_raw_upload_reproduces_unsolicited_ack(self):
        with self.assertRaisesRegex(AssertionError, 'unsolicited ACK'):
            exercise(FIXTURE, True)

    def test_patched_raw_and_normal_upload_leave_peer_ready(self):
        for raw in (True, False):
            exercise(patched(FIXTURE), raw)

    def test_patch_is_idempotent(self):
        self.assertEqual(patched(FIXTURE), patched(patched(FIXTURE)))


if __name__ == '__main__':
    if len(sys.argv) == 2:
        path = Path(sys.argv.pop())
        contents = path.read_text()
        tree = ast.parse(contents)
        method = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and n.name == 'upload')
        source = ''.join(contents.splitlines(keepends=True)[method.lineno-1:method.end_lineno])
        with unittest.TestCase().assertRaisesRegex(AssertionError, 'unsolicited ACK'):
            exercise(textwrap.dedent(source), True)
        for raw in (True, False):
            exercise(textwrap.dedent(patched(source)), raw)
        print('Pinned upload method: original failure reproduced; patched raw/normal PASS')
    unittest.main()
