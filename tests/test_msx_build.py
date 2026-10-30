"""Build output validation with synthetic local paths."""
from pathlib import Path
import tempfile
import unittest
from src.toolchain.msx.build import destination


class BuildDestinationTests(unittest.TestCase):
    def test_outputs_cannot_escape_ignored_build_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            for target in (root/'src/out',root/'references/build/../out'):
                with self.assertRaises(ValueError): destination(root,target)
            (root/'link').symlink_to(root,target_is_directory=True)
            with self.assertRaises(ValueError): destination(root,root/'link/references/build/out')


if __name__=='__main__': unittest.main()
