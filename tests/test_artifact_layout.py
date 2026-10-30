"""Exercise delivery taxonomy and historical cartridge readers."""
from pathlib import Path
import tempfile
import unittest

from src.toolchain.msx.artifacts import cartridge_path, delivery_directory


class ArtifactLayoutTests(unittest.TestCase):
    def test_delivery_names_describe_user_variants(self):
        build=dict(ram_auto=True,turbo=True,banks={})
        self.assertEqual(delivery_directory(Path('/project'),build),Path('/project/dist'))
        build['banks']['SESSION_TEST_MODE']=1
        self.assertEqual(delivery_directory(Path('/project'),build),Path('/project/dist/test'))
        build['turbo']=False
        self.assertEqual(delivery_directory(Path('/project'),build),Path('/project/dist/test/diagnostic/base-cpu'))

    def test_current_and_historical_cartridges_are_readable(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle=Path(temporary)
            (bundle/'fixed-hud.rom').write_bytes(b'historical')
            self.assertEqual(cartridge_path(bundle).read_bytes(),b'historical')
            (bundle/'newrallyx.rom').write_bytes(b'current')
            self.assertEqual(cartridge_path(bundle).read_bytes(),b'current')

