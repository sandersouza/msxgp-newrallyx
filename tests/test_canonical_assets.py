"""Canonical promotion never discards divergent or corrupted extraction data."""
import unittest
from src.toolchain.graphics.canonical import promote
from src.toolchain.graphics.export import publish_output,write_payload
from graphics_fixtures import synthetic_payload,temporary_repo


class CanonicalAssetsTests(unittest.TestCase):
    def setUp(self):
        self.root,self.inputs,self.temporary=temporary_repo(self)
        self.temporary=self.root/'references/assets/nrallyx'
        pixels,palette,graphics=synthetic_payload()
        self.writer=lambda directory:write_payload(directory,pixels,palette,graphics,[],{'commit':'synthetic'})
        publish_output(self.root,self.inputs,self.temporary,False,self.writer)

    def test_promotion_then_identical_temporary_removal(self):
        target=promote(self.root)
        self.assertTrue((target/'manifest.json').is_file())
        self.assertFalse(self.temporary.exists())
        import shutil
        shutil.copytree(target,self.temporary)
        self.assertEqual(promote(self.root),target)
        self.assertFalse(self.temporary.exists())

    def test_modified_temporary_is_preserved(self):
        path=self.temporary/'tiles/indices.bin';path.write_bytes(b'keep')
        with self.assertRaises(ValueError):promote(self.root)
        self.assertEqual(path.read_bytes(),b'keep')
