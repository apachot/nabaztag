from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


MESSAGE_INVERSION_TABLE = (
    1, 171, 205, 183, 57, 163, 197, 239, 241, 27, 61, 167, 41, 19, 53, 223,
    225, 139, 173, 151, 25, 131, 165, 207, 209, 251, 29, 135, 9, 243, 21, 191,
    193, 107, 141, 119, 249, 99, 133, 175, 177, 219, 253, 103, 233, 211, 245, 159,
    161, 75, 109, 87, 217, 67, 101, 143, 145, 187, 221, 71, 201, 179, 213, 127,
    129, 43, 77, 55, 185, 35, 69, 111, 113, 155, 189, 39, 169, 147, 181, 95,
    97, 11, 45, 23, 153, 3, 37, 79, 81, 123, 157, 7, 137, 115, 149, 63,
    65, 235, 13, 247, 121, 227, 5, 47, 49, 91, 125, 231, 105, 83, 117, 31,
    33, 203, 237, 215, 89, 195, 229, 15, 17, 59, 93, 199, 73, 51, 85, 255,
)


class AmbientService:
    DISABLE = 0
    WEATHER = 1
    STOCK_MARKET = 2
    PERIPH = 3
    MOVE_LEFT_EAR = 4
    MOVE_RIGHT_EAR = 5
    EMAIL = 6
    AIR_QUALITY = 7
    NOSE = 8
    BOTTOM_LED = 9
    TAICHI = 0x0E


class ChoreographyLed:
    BOTTOM = 0
    LEFT = 1
    MIDDLE = 2
    RIGHT = 3
    TOP = 4


LED_NAME_TO_CHOREOGRAPHY = {
    "bottom": ChoreographyLed.BOTTOM,
    "left": ChoreographyLed.LEFT,
    "center": ChoreographyLed.MIDDLE,
    "right": ChoreographyLed.RIGHT,
    "nose": ChoreographyLed.TOP,
}


@dataclass(slots=True)
class EncodedPacket:
    payload: bytes
    description: str


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    normalized = color.lstrip("#")
    return int(normalized[0:2], 16), int(normalized[2:4], 16), int(normalized[4:6], 16)


def encode_message_packet(message: str) -> bytes:
    previous_char = 35
    encoded = bytearray([0x00])
    for current_char in message.encode("utf-8"):
        encoded.append((MESSAGE_INVERSION_TABLE[previous_char % 128] * current_char + 47) % 256)
        previous_char = current_char
    return bytes(encoded)


def _frame_packet(packet_type: int, internal: bytes) -> bytes:
    length = len(internal)
    return bytes(
        [
            0x7F,
            packet_type,
            (length >> 16) & 0xFF,
            (length >> 8) & 0xFF,
            length & 0xFF,
        ]
    ) + internal + b"\xFF"


def _frame_packet_list(*packets: tuple[int, bytes]) -> bytes:
    payload = bytearray([0x7F])
    for packet_type, internal in packets:
        length = len(internal)
        payload.extend(
            [
                packet_type,
                (length >> 16) & 0xFF,
                (length >> 8) & 0xFF,
                length & 0xFF,
            ]
        )
        payload.extend(internal)
    payload.append(0xFF)
    return bytes(payload)


def build_audio_packet(url: str) -> EncodedPacket:
    if url.startswith("broadcast/"):
        # Local assets behave better as message resources than as HTTP streams.
        message = f"MU {url}\nMW\n"
        description = f"Play local audio {url}"
    else:
        message = f"ST {url}\nPL 3\nMW\n"
        description = f"Stream audio {url}"
    return EncodedPacket(
        payload=_frame_packet(0x0A, encode_message_packet(message)),
        description=description,
    )


def build_ears_packet(left: int, right: int) -> EncodedPacket:
    payload = _frame_packet(
        0x04,
        bytes([0x7F, 0xFF, 0xFF, 0xFE, AmbientService.MOVE_LEFT_EAR, left, AmbientService.MOVE_RIGHT_EAR, right]),
    )
    return EncodedPacket(payload=payload, description=f"Move ears to left={left} right={right}")


def build_nose_or_bottom_packet(target: str, color: str) -> EncodedPacket:
    red, green, blue = _hex_to_rgb(color)
    value = 0 if color.lower() == "#000000" else 1
    if target == "nose":
        service = AmbientService.NOSE
        if color.lower() == "#000000":
            value = 0
        elif blue >= red and blue >= green:
            value = 2
        else:
            value = 1
    else:
        service = AmbientService.BOTTOM_LED
        value = red
    payload = _frame_packet(0x04, bytes([0x7F, 0xFF, 0xFF, 0xFE, service, value]))
    return EncodedPacket(payload=payload, description=f"Set {target} LED to {color}")


def build_choreography_packet(*, target: str, color: str, filename: str) -> tuple[EncodedPacket, bytes]:
    red, green, blue = _hex_to_rgb(color)
    led_id = LED_NAME_TO_CHOREOGRAPHY[target]
    tempo = 10
    body = bytearray(4)
    body.extend([0x00, 0x01, tempo])
    body.extend([0x00, 0x07, led_id, red, green, blue, 0x00, 0x00])
    body[0:4] = (len(body) - 4).to_bytes(4, byteorder="big")
    body.extend(b"\x00\x00\x00\x00")
    message = f"CH broadcast/ojn_local/chor/{filename}\n"
    return (
        EncodedPacket(
            payload=_frame_packet(0x0A, encode_message_packet(message)),
            description=f"Run LED choreography for {target} -> {color}",
        ),
        bytes(body),
    )


def build_init_packet() -> bytes:
    ambient = bytes(
        [
            0x7F,
            0xFF,
            0xFF,
            0xFE,
            AmbientService.NOSE,
            0x00,
            AmbientService.MOVE_LEFT_EAR,
            0x00,
            AmbientService.MOVE_RIGHT_EAR,
            0x00,
        ]
    )
    sleep = bytes([0x00])
    return _frame_packet_list((0x04, ambient), (0x0B, sleep))


def choreography_storage_path(root: Path, filename: str) -> Path:
    return root / "chor" / filename
