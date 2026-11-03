"""The SLA patch: check_sla returns without asking the DA when the preloader reports SLA off (#273)."""
import subprocess
import unittest

from common import MTK_HOME, MTKCLIENT_COMMIT
from setup_mtkclient import PATCHES

XML = 'src/mtkclient/Library/DA/xmlflash/xml_lib.py'


def patched():
    text = subprocess.check_output(['git', '-C', str(MTK_HOME / 'src'), 'show', f'{MTKCLIENT_COMMIT}:{XML.removeprefix("src/")}'], text=True)
    for _, old, new, required in PATCHES:
        if old in text:
            assert text.count(old) == 1
            text = text.replace(old, new)
        else:
            assert not required
    return text


@unittest.skipUnless((MTK_HOME / 'src/.git').exists() or (MTK_HOME / 'src').exists(), 'pinned mtkclient checkout not present')
class SlaSkipTests(unittest.TestCase):
    def check_sla(self, sla):
        src = patched()
        body = src[src.index('    def check_sla(self):'):]
        body = body[:body.index('\n    def ', 10)]
        calls = []

        class Cfg:
            target_config = {'sla': sla}

        class Mtk:
            config = Cfg()

        class Obj:
            mtk = Mtk()

            def get_sys_property(self, **kw):
                calls.append(kw)
                return None

            def error(self, *a):
                pass

        ns = {}
        exec('class T:\n' + body.replace('\n    ', '\n    '), ns)
        obj = Obj()
        return ns['T'].check_sla(obj), calls

    def test_sla_off_does_not_ask_the_da(self):
        self.assertEqual(self.check_sla(False), (False, []))

    def test_sla_on_still_asks_the_da(self):
        result, calls = self.check_sla(True)
        self.assertEqual(len(calls), 1)
        self.assertIs(result, False)  # empty reply handled by the earlier patch

    def test_patch_guard_precedes_the_da_call(self):
        src = patched()
        self.assertLess(src.index('target_config.get("sla") is False'), src.index('self.get_sys_property(key="DA.SLA"'))


if __name__ == '__main__':
    unittest.main()
