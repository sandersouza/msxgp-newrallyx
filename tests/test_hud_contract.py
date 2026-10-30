"""Native HUD ownership and pointer semantics, using synthetic RAM only."""
import unittest
from src.toolchain.msx.hud_contract import native_values,DIGIT_OFFSETS


def snapshot():
    data=bytearray(4096)
    for location,value in ((0x988,0x8230),(0x98e,0x8240),(0x990,0x80a0)):
        data[location:location+2]=value.to_bytes(2,'little')
    data[0x230]=4
    data[0x240:0x242]=bytes([9,60])
    def number(address,value):
        for offset,digit in zip(DIGIT_OFFSETS,f'{value:06d}'):
            data[address-0x8000+offset]=int(digit)
    number(0x80a0,123450);number(0x80c0,987650);number(0x8060,20000)
    return data


class NativeHudContractTests(unittest.TestCase):
    def test_selected_score_pointer_and_original_state_remain_authoritative(self):
        data=snapshot();before=bytes(data)
        self.assertEqual(native_values(data),dict(score=123450,high=20000,lives=3,fuel=30))
        self.assertEqual(bytes(data),before)
        data[0x990:0x992]=(0x80c0).to_bytes(2,'little')
        self.assertEqual(native_values(data)['score'],987650)
        self.assertEqual(native_values(data)['high'],20000)  # HUD awards no record/bonus.

    def test_empty_gauge_does_not_exhaust_fractional_game_fuel(self):
        data=snapshot();data[0x241]=0;data[0x292]=0x77
        self.assertEqual(native_values(data)['fuel'],0)
        self.assertEqual(data[0x240],9)
        self.assertEqual(data[0x292],0x77)

    def test_car_count_includes_current_car_and_display_caps_do_not_change_count(self):
        data=snapshot()
        for count,expected in ((0,0),(1,0),(2,1),(10,9),(255,9)):
            data[0x230]=count
            self.assertEqual(native_values(data)['lives'],expected)
            self.assertEqual(data[0x230],count)

    def test_native_zero_and_blank_tile_codes_are_not_packed_bcd(self):
        data=snapshot()
        for offset,code in zip(DIGIT_OFFSETS,(0x40,2,0,0,0,0x30)):
            data[0x60+offset]=code
        self.assertEqual(native_values(data)['high'],20000)

    def test_invalid_native_addresses_and_digits_are_rejected(self):
        for pointer in (0,0x7fff,0x8ff9,0x8fff,0x9000,0xffff):
            data=snapshot();data[0x990:0x992]=pointer.to_bytes(2,'little')
            with self.assertRaises(ValueError):native_values(data)
        data=snapshot();data[0xa6]=0x0a
        with self.assertRaises(ValueError):native_values(data)
        data=snapshot();data[0x240]=10
        with self.assertRaises(ValueError):native_values(data)
