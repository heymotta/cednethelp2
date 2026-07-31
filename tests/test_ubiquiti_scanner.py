"""Testes unitários da camada sem interface do scanner."""

import unittest

from scanner.parser import parse_response
from scanner.protocol import DISCOVERY_PORT, DISCOVERY_REQUEST


class DiscoveryParserTests(unittest.TestCase):
    def test_parses_common_text_response(self):
        payload = b"model=U6-LR\x00systemname=AP-Sala\x00mac=aa:bb:cc:dd:ee:ff\x00firmware=6.6.77\x00protocol=1"
        device = parse_response(payload, ("192.168.1.20", DISCOVERY_PORT), 3.5)
        self.assertIsNotNone(device)
        assert device is not None
        self.assertEqual(device.model, "U6-LR")
        self.assertEqual(device.system_name, "AP-Sala")
        self.assertEqual(device.mac, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(device.response_ms, 3.5)

    def test_accepts_binary_discovery_response_from_port(self):
        device = parse_response(b"\x01\x00\x00\x00", ("10.0.0.2", DISCOVERY_PORT))
        self.assertIsNotNone(device)

    def test_ignores_unrelated_packet(self):
        self.assertIsNone(parse_response(b"hello world", ("10.0.0.2", 9999)))


class DiscoveryProtocolTests(unittest.TestCase):
    def test_request_is_udp_discovery_payload(self):
        self.assertEqual(DISCOVERY_PORT, 10001)
        self.assertTrue(DISCOVERY_REQUEST.startswith(b"\x01\x00\x00\x00"))


if __name__ == "__main__":
    unittest.main()
