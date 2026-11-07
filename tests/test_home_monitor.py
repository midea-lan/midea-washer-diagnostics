import unittest
from enum import Enum

from home_monitor import build_device, json_value
from initialize_home_devices import supported


class SampleCode(Enum):
    WASH = 3


class HomeMonitorTests(unittest.TestCase):
    def test_json_value_preserves_nested_values_and_enum_codes(self) -> None:
        value = {"program": SampleCode.WASH, "levels": [7, None]}

        self.assertEqual(json_value(value), {"program": 3, "levels": [7, None]})

    def test_build_device_uses_registered_da_parser(self) -> None:
        info = {
            "device_id": 123456789,
            "type": 0xDA,
            "protocol": 1,
            "ip_address": "192.168.0.20",
            "port": 6444,
            "model": "test-model",
            "subtype": 0,
        }
        device = build_device(info)

        self.assertEqual(device.device_id, 123456789)
        self.assertEqual(device.device_type, 0xDA)
        self.assertTrue(supported(info))

    def test_unknown_device_type_is_not_selected(self) -> None:
        self.assertFalse(supported({
            "device_id": 123456789,
            "type": 0x99,
            "protocol": 1,
            "ip_address": "192.168.0.20",
            "port": 6444,
        }))


if __name__ == "__main__":
    unittest.main()
