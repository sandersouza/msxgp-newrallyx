import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from graphics_fixtures import temporary_repo
from scripts.scenes.storage import publish_bundle
from scripts.scenes.storage import seal
from scripts.scenes.bundle import verify_manifest


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.root, _, _ = temporary_repo(self)
        self.output = self.root/'references/scenes/test'

    def test_publishes_and_preserves_existing(self):
        publish_bundle(self.root, self.output, lambda p: (p/'x').write_bytes(b'first'))
        with self.assertRaises(ValueError):
            publish_bundle(self.root, self.output, lambda p: (p/'x').write_bytes(b'other'))
        self.assertEqual((self.output/'x').read_bytes(), b'first')

    def test_rejects_unsafe_paths(self):
        self.output.parent.mkdir(parents=True)
        (self.output.parent/'alias').symlink_to(self.root, target_is_directory=True)
        for dest in [self.root/'outside', self.output.parent, self.output.parent/'alias/x',
                     self.output.parent/'../scenes/foo']:
            with self.subTest(dest=str(dest)), self.assertRaises(ValueError):
                publish_bundle(self.root, dest, lambda p: None)
        (self.root/'.gitignore').write_text('')
        with self.assertRaises(ValueError):
            publish_bundle(self.root, self.output, lambda p: None)

    def test_tracked_output_and_writer_failure(self):
        self.output.mkdir(parents=True)
        (self.output/'x').write_text('tracked')
        subprocess.run(['git','-C',str(self.root),'add','-f',str(self.output/'x')], check=True)
        with self.assertRaises(ValueError):
            publish_bundle(self.root, self.output, lambda p: None)
        def broken(path):
            (path/'partial').write_text('incomplete')
            raise RuntimeError('writer failed')
        other = self.output.with_name('other')
        with self.assertRaises(RuntimeError):
            publish_bundle(self.root, other, broken)
        self.assertFalse(other.exists())
        self.assertFalse(list(other.parent.glob('.other.*')))

    def test_concurrent_publication_refused(self):
        def writer(path):
            with self.assertRaises(ValueError):
                publish_bundle(self.root, self.output, lambda p: None)
            (path/'ok').write_text('ok')
        publish_bundle(self.root, self.output, writer)

    def test_parent_manifest_covers_nested_case_manifest(self):
        def writer(path):
            case=path/'case'; case.mkdir(); (case/'payload').write_text('ok'); seal(case)
        publish_bundle(self.root,self.output,writer)
        manifest=verify_manifest(self.output)
        self.assertIn('case/manifest.json',[r['path'] for r in manifest['outputs']])

    def test_narrow_unignore_blocks_actual_final_and_staged_payloads(self):
        for pattern in ['!/references/scenes/test/reference.png',
                        '!/references/scenes/**/reference.png',
                        '!/references/scenes/test/case/video.bin']:
            with self.subTest(pattern=pattern):
                (self.root/'.gitignore').write_text('/references/**\n!/references/**/\n'+pattern+'\n')
                def writer(stage):
                    (stage/'reference.png').write_bytes(b'synthetic image')
                    (stage/'case').mkdir(); (stage/'case/video.bin').write_bytes(b'synthetic RAM')
                with self.assertRaises(ValueError):
                    publish_bundle(self.root,self.output,writer)
                self.assertFalse(self.output.exists())

    def test_predicted_payloads_fail_before_writer(self):
        (self.root/'.gitignore').write_text('/references/**\n!/references/**/\n!/references/scenes/**/reference.png\n')
        called=[]
        with self.assertRaises(ValueError):
            publish_bundle(self.root,self.output,lambda p: called.append(p),payloads=['reference.png'])
        self.assertEqual(called,[])

    def test_explicit_overwrite_replaces_only_complete_matching_bundles(self):
        publish_bundle(self.root,self.output,lambda p:(p/'x').write_bytes(b'first'),payloads=['x'])
        publish_bundle(self.root,self.output,lambda p:(p/'x').write_bytes(b'second'),
                       payloads=['x'],overwrite=True)
        self.assertEqual((self.output/'x').read_bytes(),b'second')
        verify_manifest(self.output,{'x'})
        for modification in ('modified','unknown','empty-directory','symlink','different-inventory'):
            with self.subTest(modification=modification):
                extra=self.output/'extra'
                if modification=='modified':
                    (self.output/'x').write_bytes(b'edited')
                elif modification=='unknown':
                    extra.write_bytes(b'keep')
                elif modification=='empty-directory':
                    extra.mkdir()
                elif modification=='symlink':
                    extra.symlink_to(self.output/'x')
                called=[]
                with self.assertRaises(ValueError):
                    publish_bundle(self.root,self.output,lambda p:called.append(p),
                                   payloads=['y'] if modification=='different-inventory' else ['x'],
                                   overwrite=True)
                self.assertEqual(called,[])
                self.assertTrue((self.output/'x').is_file())
                if extra.is_dir() and not extra.is_symlink():
                    extra.rmdir()
                elif extra.exists() or extra.is_symlink():
                    extra.unlink()
                (self.output/'x').write_bytes(b'second')

    def test_overwrite_publication_failure_restores_old_bundle(self):
        publish_bundle(self.root,self.output,lambda p:(p/'x').write_bytes(b'first'),payloads=['x'])
        rename=Path.rename
        def fail_install(path,target):
            if '.staging-' in path.name:
                raise OSError('synthetic installation failure')
            return rename(path,target)
        with patch.object(Path,'rename',fail_install), self.assertRaises(OSError):
            publish_bundle(self.root,self.output,lambda p:(p/'x').write_bytes(b'new'),
                           payloads=['x'],overwrite=True)
        self.assertEqual((self.output/'x').read_bytes(),b'first')
        verify_manifest(self.output,{'x'})
        self.assertEqual(list(self.output.parent.iterdir()),[self.output])

    def test_overwrite_still_protects_tracked_files(self):
        publish_bundle(self.root,self.output,lambda p:(p/'x').write_bytes(b'first'),payloads=['x'])
        subprocess.run(['git','-C',str(self.root),'add','-f',str(self.output/'x')],check=True)
        with self.assertRaises(ValueError):
            publish_bundle(self.root,self.output,lambda p:(p/'x').write_bytes(b'new'),
                           payloads=['x'],overwrite=True)
        self.assertEqual((self.output/'x').read_bytes(),b'first')
