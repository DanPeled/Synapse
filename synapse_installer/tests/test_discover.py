# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import itertools
import json
import socket

import synapse_installer.discover as discover_mod
from synapse_installer.discover import _parseResponse, discoverDevices


def _noDirectLinks(monkeypatch):
    monkeypatch.setattr(discover_mod, "findDirectLinkInterfaces", lambda: [])


def test_parse_response_valid():
    payload = json.dumps(
        {
            "ip": "10.0.0.5",
            "hostname": "robot",
            "nickname": "shooter",
            "username": "pi",
            "version": "1.2.3",
            "team_number": 1234,
        }
    ).encode()

    device = _parseResponse(payload, ("10.0.0.5", 45454))

    assert device is not None
    assert device.nickname == "shooter"
    assert device.hostname == "robot"
    assert device.ip == "10.0.0.5"
    assert device.username == "pi"
    assert device.version == "1.2.3"
    assert device.teamNumber == 1234


def test_parse_response_uses_sender_ip():
    payload = json.dumps({"hostname": "robot"}).encode()

    device = _parseResponse(payload, ("10.0.0.9", 45454))

    assert device is not None
    assert device.ip == "10.0.0.9"
    assert device.nickname == "robot"


def test_parse_response_invalid_json():
    assert _parseResponse(b"not json", ("10.0.0.5", 45454)) is None


def test_parse_response_non_dict():
    assert _parseResponse(b"[]", ("10.0.0.5", 45454)) is None


def test_parse_response_invalid_ip():
    payload = json.dumps({"ip": "not-an-ip"}).encode()

    assert _parseResponse(payload, ("10.0.0.5", 45454)) is None


def test_parse_response_bad_team_number():
    payload = json.dumps({"ip": "10.0.0.5", "team_number": "nope"}).encode()

    device = _parseResponse(payload, ("10.0.0.5", 45454))

    assert device is not None
    assert device.teamNumber == 0


class FakeSocket:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = []
        self.closed = False
        self.options = []

    def setsockopt(self, *args):
        self.options.append(args)

    def settimeout(self, timeout):
        self.timeout = timeout

    def bind(self, address):
        self.bound = address

    def sendto(self, data, address):
        self.sent.append((data, address))

    def recvfrom(self, size):
        if self.responses:
            return self.responses.pop(0)
        raise socket.timeout

    def close(self):
        self.closed = True


def test_discover_devices(monkeypatch):
    _noDirectLinks(monkeypatch)
    response = json.dumps(
        {"ip": "10.0.0.5", "hostname": "robot", "nickname": "robot"}
    ).encode()
    fake = FakeSocket([(response, ("10.0.0.5", 45454))])

    monkeypatch.setattr(discover_mod.socket, "socket", lambda *a, **k: fake)
    counter = itertools.count(0, 0.1)
    monkeypatch.setattr(discover_mod.time, "monotonic", lambda: next(counter))

    devices = discoverDevices(timeout=2.0)

    assert len(devices) == 1
    assert devices[0].ip == "10.0.0.5"
    assert fake.sent == [(b"PING_DISCOVERY", ("255.255.255.255", 45454))]
    assert fake.closed is True


def test_discover_devices_deduplicates(monkeypatch):
    _noDirectLinks(monkeypatch)
    response = json.dumps({"ip": "10.0.0.5", "nickname": "robot"}).encode()
    fake = FakeSocket(
        [
            (response, ("10.0.0.5", 45454)),
            (response, ("10.0.0.5", 45454)),
        ]
    )

    monkeypatch.setattr(discover_mod.socket, "socket", lambda *a, **k: fake)
    counter = itertools.count(0, 0.1)
    monkeypatch.setattr(discover_mod.time, "monotonic", lambda: next(counter))

    assert len(discoverDevices(timeout=2.0)) == 1


def test_discover_devices_send_failure(monkeypatch):
    _noDirectLinks(monkeypatch)

    class FailingSocket(FakeSocket):
        def sendto(self, data, address):
            raise OSError("network down")

    fake = FailingSocket([])

    monkeypatch.setattr(discover_mod.socket, "socket", lambda *a, **k: fake)

    assert discoverDevices() == []
    assert fake.closed is True


def test_parse_response_link_local_uses_source_ip():
    payload = json.dumps(
        {
            "ip": "10.0.0.5",
            "addresses": ["10.0.0.5", "169.254.2.10"],
            "hostname": "robot",
            "directLink": True,
        }
    ).encode()

    device = _parseResponse(payload, ("169.254.2.10", 45454))

    assert device is not None
    assert device.ip == "169.254.2.10"
    assert device.isDirectLink is True
    assert device.addresses == ["10.0.0.5", "169.254.2.10"]


def test_parse_response_prefers_same_subnet_address():
    payload = json.dumps(
        {
            "ip": "10.72.176.5",
            "addresses": ["10.72.176.5", "192.168.1.10"],
            "hostname": "robot",
        }
    ).encode()

    device = _parseResponse(payload, ("192.168.1.20", 45454))

    assert device is not None
    assert device.ip == "192.168.1.10"


def test_discover_devices_broadcasts_on_direct_links(monkeypatch):
    from synapse_installer.direct_connect import DirectLinkInterface

    monkeypatch.setattr(
        discover_mod,
        "findDirectLinkInterfaces",
        lambda: [DirectLinkInterface("usb0", "169.254.2.100", "255.255.0.0", True)],
    )
    fake = FakeSocket([])

    monkeypatch.setattr(discover_mod.socket, "socket", lambda *a, **k: fake)
    counter = itertools.count(0, 0.1)
    monkeypatch.setattr(discover_mod.time, "monotonic", lambda: next(counter))

    discoverDevices(timeout=2.0)

    assert (b"PING_DISCOVERY", ("255.255.255.255", 45454)) in fake.sent
    assert (b"PING_DISCOVERY", ("169.254.255.255", 45454)) in fake.sent
