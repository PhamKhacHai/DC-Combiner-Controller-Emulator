import pytest

from bridge_protocol import decode_message, encode_message, frame_from_dict, frame_to_dict, make_request
from models import CanFrame


def test_bridge_message_round_trip() -> None:
    message = make_request("send", can_id=0x500, data="0300", extended=False, rtr=False)
    encoded = encode_message(message)
    assert encoded.endswith("\n")
    assert decode_message(encoded) == message


def test_decode_rejects_non_object() -> None:
    with pytest.raises(ValueError):
        decode_message("[1, 2, 3]")


def test_frame_dict_round_trip() -> None:
    frame = CanFrame(can_id=0x510, data=bytes.fromhex("030f000001000000"), dlc=8, timestamp=123.5)
    payload = frame_to_dict(frame)
    assert payload["data"] == "030f000001000000"
    assert frame_from_dict(payload) == frame
