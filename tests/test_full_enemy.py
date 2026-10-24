"""Hardware allocation tests for complete-car population rendering."""
import unittest
from scripts.msx.full_enemy import pattern_plan,registration_table,indexed_records,validate_extension_space


class FullEnemyTests(unittest.TestCase):
    def test_seven_complete_car_caches_fit_with_both_radar_phases_and_player(self):
        common,victims=pattern_plan()
        self.assertEqual(len(common),3)
        self.assertEqual(len(victims),7)
        self.assertEqual(sum(8 for _ in common)+sum(8 for _ in victims),80)
        self.assertTrue(all(base%8==0 for base in victims))
        self.assertEqual(16+2+len(victims)*2,32)

    def test_linked_radar_pattern_cannot_share_a_complete_car_cache(self):
        with self.assertRaisesRegex(ValueError,'overlaps'):
            pattern_plan(radar_pattern=232)

    def test_pointer_decode_accepts_only_the_seven_complete_actor_addresses(self):
        table=registration_table()
        expected={0xe093+i*32:1<<i for i in range(7)}
        for address in range(65536):
            actual=table[address-0xe000] if 0xe000<=address<0xe200 else 0
            self.assertEqual(actual,expected.get(address,0))

    def test_record_codegen_keeps_complete_field_names_and_word_order(self):
        code=indexed_records('    ld hl,Enemy_CacheClip\n    ld hl,Enemy_CacheTop\n    ld hl,(Enemy_WorldY)\n    ld (Enemy_DrawX),de\n')
        self.assertIn('ld de,15',code)
        self.assertIn('ld de,21',code)
        self.assertIn('ld l,(ix+4)',code)
        self.assertIn('ld h,(ix+5)',code)
        self.assertIn('ld (ix+6),e',code)
        self.assertIn('ld (ix+7),d',code)
        self.assertNotIn('deClip',code)
        self.assertIn('push de',code)
        self.assertIn('pop de',code)

    def test_bank_helpers_cannot_replace_native_instructions_or_trampolines(self):
        bank=bytearray([255])*16384
        bank[0x3f00]=0xc3
        validate_extension_space(bank)
        bank[0x3800]=0xc3
        with self.assertRaisesRegex(ValueError,'occupied'):validate_extension_space(bank)
