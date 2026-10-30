"""Full-session probes must never silently test the64 KiB ROM on128 KiB."""

from pathlib import Path as _ToolPath
import sys as _tool_sys
for _tool_dir in (_ToolPath(__file__).resolve().parent, _ToolPath(__file__).resolve().parents[3]):
    if str(_tool_dir) not in _tool_sys.path: _tool_sys.path.insert(0, str(_tool_dir))
from source_paths import source_path, RUNTIME
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from session_reference import configure


class ReferenceProfile(unittest.TestCase):
    def test_reads_built_profile_and_rejects_stale_machine_capacity(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle=Path(temporary)
            for ram in (64,128):
                (bundle/'session-build.json').write_text(json.dumps(dict(ram_kib=ram)))
                with self.subTest(ram=ram),patch.dict(os.environ,{},clear=True):
                    self.assertEqual(configure(bundle),ram)
                    self.assertEqual(os.environ['NRX_REFERENCE_RAM_KIB'],str(ram))
                with patch.dict(os.environ,dict(NRX_REFERENCE_RAM_KIB=str(192-ram)),clear=True):
                    with self.assertRaisesRegex(ValueError,'conflicting'):configure(bundle)

    def test_preserved_pre64k_bundle_requires128_and_unknown_profiles_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle=Path(temporary)
            (bundle/'session-build.json').write_text('{}')
            with patch.dict(os.environ,{},clear=True):self.assertEqual(configure(bundle),128)
            (bundle/'session-build.json').write_text('{"ram_kib": 32}')
            with self.assertRaises(ValueError):configure(bundle)
