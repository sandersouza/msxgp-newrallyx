"""Exercise reference-machine generation without BIOS or game data."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


HELPER = Path(__file__).resolve().parents[1]/'src/toolchain/msx/mapper_reference.tcl'


@unittest.skipUnless(shutil.which('tclsh'), 'Tcl interpreter unavailable')
class MapperReferenceTests(unittest.TestCase):
    def run_helper(self, machine, size, xml,kind='mapper'):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            machines=root/'system/machines'; machines.mkdir(parents=True)
            source=machines/'Panasonic_FS-A1WSX.xml'; source.write_text(xml)
            script=('proc machine {name} {return $name}\n'
                    f'proc debug {{action args}} {{switch $action {{list {{return {{{{Main RAM}}}}}} '
                    f'desc {{return {{{"memory mapper" if kind=="mapper" else "RAM"}}}}} size {{return {size}}}}}}}\n'
                    'source $::env(REFERENCE_HELPER)\n'
                    f'if {{[catch {{nrallyx_reference_machine {machine}}} problem]}} '
                    '{puts stderr $problem; exit 2}\n')
            env=dict(os.environ,REFERENCE_HELPER=str(HELPER),OPENMSX_SYSTEM_DATA=str(root/'system'),OPENMSX_USER_DATA=str(root/'user'))
            if kind=='plain':env.update(NRX_REFERENCE_RAM_KIB='64',NRX_REFERENCE_RAM_KIND='plain')
            result=subprocess.run(['tclsh'],input=script,text=True,capture_output=True,env=env)
            generated=root/'user/machines'/('Panasonic_FS-A1WSX_PLAIN64.xml' if kind=='plain' else 'Panasonic_FS-A1WSX_NR128.xml')
            self.assertEqual(source.read_text(),xml)
            return result, generated.read_text() if generated.exists() else None

    def test_default_machine_uses_private_128kb_config(self):
        xml=('<msxconfig><MapperReadBackBits>2</MapperReadBackBits><devices>'
             '<MemoryMapper id="Main RAM"><size>64</size></MemoryMapper>'
             '</devices></msxconfig>')
        result, generated=self.run_helper('Panasonic_FS-A1WSX',131072,xml)
        self.assertEqual(result.returncode,0,result.stderr)
        config=ET.fromstring(generated)
        self.assertEqual(config.findtext('.//MemoryMapper/size'),'128')
        self.assertEqual(config.findtext('MapperReadBackBits'),'3')

    def test_plain64_has_fixed_ram_and_no_mapper_device_or_ports(self):
        xml=('<msxconfig><MapperReadBackBits>2</MapperReadBackBits><devices>'
             '<MemoryMapper id="Main RAM"><mem base="0x0000" size="0x10000"/>'
             '<size>64</size></MemoryMapper></devices></msxconfig>')
        result,generated=self.run_helper('Panasonic_FS-A1WSX',65536,xml,'plain')
        self.assertEqual(result.returncode,0,result.stderr)
        config=ET.fromstring(generated)
        self.assertIsNone(config.find('.//MemoryMapper'))
        self.assertIsNone(config.find('MapperReadBackBits'))
        self.assertEqual(config.find('.//RAM/mem').attrib,{'base':'0x0000','size':'0x10000'})
        self.assertIn('Reference plain RAM: 65536 bytes; RAM mapper: 0 bytes',result.stderr)

    def test_other_machine_with_small_mapper_is_rejected(self):
        result,generated=self.run_helper('OtherMachine',65536,'<msxconfig/>')
        self.assertEqual(result.returncode,2)
        self.assertIn('requires at least 128 KiB',result.stderr)
        self.assertIsNone(generated)

    def test_unrecognized_machine_xml_is_rejected(self):
        result,generated=self.run_helper('Panasonic_FS-A1WSX',131072,'<msxconfig/>')
        self.assertEqual(result.returncode,2)
        self.assertIn('Cannot identify',result.stderr)
        self.assertIsNone(generated)
