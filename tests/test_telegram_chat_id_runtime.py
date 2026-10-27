import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telethon.types import InputPeerChannel, InputPeerChat, InputPeerEmpty, InputPeerUser

from calmlib.telegram.utils import get_chat_id


@pytest.mark.parametrize("peer, expected", [
    (InputPeerUser(123, 456), 123),
    (InputPeerChannel(234, 567), 234),
    (InputPeerChat(345), 345),
])
def test_username_resolution_with_real_telethon_types(peer, expected):
    client = SimpleNamespace(get_input_entity=AsyncMock(return_value=peer))
    assert asyncio.run(get_chat_id("example", client)) == expected
    client.get_input_entity.assert_awaited_once_with("example")


def test_empty_peer_reports_resolution_error():
    client = SimpleNamespace(get_input_entity=AsyncMock(return_value=InputPeerEmpty()))
    with pytest.raises(ValueError, match="InputPeerEmpty"):
        asyncio.run(get_chat_id("example", client))
