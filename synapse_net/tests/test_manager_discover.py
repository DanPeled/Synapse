# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the direct-link-aware UDP discovery responder."""

from unittest.mock import patch

from synapse_net.manager_discover import chooseReplyAddress


def test_choose_reply_address_prefers_link_local_on_direct_link():
    addresses = ["10.0.0.5", "169.254.2.10"]
    with patch("synapse_net.manager_discover.getIP", return_value="10.0.0.5"):
        assert chooseReplyAddress("169.254.2.100", addresses) == "169.254.2.10"


def test_choose_reply_address_prefers_same_subnet():
    addresses = ["10.0.0.5", "192.168.1.10"]
    with patch("synapse_net.manager_discover.getIP", return_value="10.0.0.5"):
        assert chooseReplyAddress("192.168.1.20", addresses) == "192.168.1.10"


def test_choose_reply_address_falls_back_to_getip():
    with patch("synapse_net.manager_discover.getIP", return_value="10.0.0.5"):
        assert chooseReplyAddress("", ["10.0.0.5"]) == "10.0.0.5"


def test_build_response_includes_all_addresses():
    from synapse_net.manager_discover import UDPDeviceResponder

    with (
        patch("synapse_net.manager_discover.socket.socket"),
        patch(
            "synapse_net.manager_discover._localIPv4Addresses",
            return_value=["10.0.0.5", "169.254.2.10"],
        ),
        patch("synapse_net.manager_discover.getIP", return_value="10.0.0.5"),
    ):
        responder = UDPDeviceResponder("robot", "pi", 1234, "1.0")
        response = responder.buildResponse("169.254.2.100")

    assert response["ip"] == "169.254.2.10"
    assert response["addresses"] == ["10.0.0.5", "169.254.2.10"]
    assert response["nickname"] == "robot"
    assert "directLink" in response
