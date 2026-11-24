"""Tiny PNG writer, so the vision check needs no image library or real photos."""
import struct
import zlib

COLORS = {"red": (220, 20, 20), "green": (20, 170, 40), "blue": (20, 60, 220)}


def square(color: str, size: int = 224) -> bytes:
    """A colored square centered on white."""
    edge, rgb, white = size // 4, bytes(COLORS[color]), b"\xff\xff\xff"
    blank = b"\0" + white * size
    middle = b"\0" + white * edge + rgb * (size - 2 * edge) + white * edge
    rows = b"".join(middle if edge <= y < size - edge else blank for y in range(size))

    def chunk(kind: bytes, body: bytes) -> bytes:
        crc = zlib.crc32(kind + body)
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
