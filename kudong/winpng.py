from dataclasses import dataclass
from typing import List, Optional, Tuple

from PySide6.QtGui import QImage


MAX_EMBEDDED_FILE_SIZE = 20 * 1024 * 1024
MAX_PATH_BYTES = 255


@dataclass
class WinPNGFile:
    path: str
    data: bytes


def _pixel(image: QImage, x: int, y: int) -> int:
    return image.pixel(x, y) & 0xFFFFFF


def _path_length_from_rgb(rgb: int) -> int:
    # WinPNG legacy images stored the path length directly in B.
    if (rgb & 0xFFFF00) == 0:
        return rgb & 0xFF

    # Current WinPNG distributes one byte over R3/G2/B3.
    return (
        ((rgb & 0x070000) >> 11)
        | ((rgb & 0x000300) >> 5)
        | (rgb & 0x000007)
    )


def _rgb_bytes(rgb: int) -> Tuple[int, int, int]:
    return (
        (rgb >> 16) & 0xFF,
        (rgb >> 8) & 0xFF,
        rgb & 0xFF,
    )


def _read_rgb_bytes(
    image: QImage,
    start_index: int,
    length: int,
    base_y: int = 0,
) -> bytes:
    width = image.width()
    result = bytearray(length)

    for i in range(length):
        pixel_index = start_index + (i // 3)
        x = pixel_index % width
        y = base_y + (pixel_index // width)
        rgb = _pixel(image, x, y)
        result[i] = (rgb >> (8 * (2 - (i % 3)))) & 0xFF

    return bytes(result)


def _safe_embedded_path(path_bytes: bytes) -> Optional[str]:
    try:
        path = path_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None

    if not path or "\ufffd" in path or "\\" in path:
        return None

    if any(char in path for char in '*?"<>|'):
        return None

    parts = path.replace("\\", "/").split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None

    return "/".join(parts)


def _decode_raw_container_image(image: QImage, depth: int = 0) -> List[WinPNGFile]:
    if image.isNull() or depth > 2:
        return []

    width = image.width()
    height = image.height()
    if width < 2 or height < 1:
        return []

    files: List[WinPNGFile] = []
    offset_y = 0

    while offset_y < height:
        first = _pixel(image, 0, offset_y)
        second = _pixel(image, 1, offset_y)

        path_length = _path_length_from_rgb(first)
        binary_length = second & 0xFFFFFF

        if path_length > MAX_PATH_BYTES:
            break
        if binary_length <= 0 or binary_length > MAX_EMBEDDED_FILE_SIZE:
            break

        pixel_count = (
            2
            + ((path_length + 2) // 3)
            + ((binary_length + 2) // 3)
        )
        container_height = (pixel_count + width - 1) // width

        if container_height <= 0 or offset_y + container_height > height:
            break

        path_start = 2
        data_start = path_start + ((path_length + 2) // 3)

        if path_length == 0:
            nested_data = _read_rgb_bytes(
                image,
                data_start,
                binary_length,
                offset_y,
            )
            nested_image = QImage.fromData(nested_data)
            if not nested_image.isNull():
                files.extend(_decode_raw_container_image(nested_image, depth + 1))
            offset_y += container_height
            continue

        path_bytes = _read_rgb_bytes(
            image,
            path_start,
            path_length,
            offset_y,
        )
        path = _safe_embedded_path(path_bytes)
        if path is None:
            break

        binary = _read_rgb_bytes(
            image,
            data_start,
            binary_length,
            offset_y,
        )
        files.append(WinPNGFile(path=path, data=binary))
        offset_y += container_height

    return files


def _get_d(b: int, c: int) -> int:
    return (
        (0x800000 + (b & 0xFF0000) - (c & 0xFF0000))
        | (0x008000 + (b & 0x00FF00) - (c & 0x00FF00))
        | (0x000080 + (b & 0x0000FF) - (c & 0x0000FF))
    ) & 0xFFFFFF


def _is_valid(a: int, b: int, c: int, d: int) -> bool:
    checksum = (
        (0x800000 + (a & 0xFF0000) - (b & 0xFF0000) - (c & 0xFF0000))
        + (0x008000 + (a & 0x00FF00) - (b & 0x00FF00) - (c & 0x00FF00))
        + (0x000080 + (a & 0x0000FF) - (b & 0x0000FF) - (c & 0x0000FF))
    )
    compare = ((a & 0x010101) + (d & 0x010101)) & 0x010101
    return checksum == compare


def _sample_points(width: int, height: int) -> List[Tuple[int, int]]:
    if width <= 0 or height <= 0:
        return []

    points = [
        (0, 0),
        (width - 1, 0),
        (0, height - 1),
        (width - 1, height - 1),
        (width // 2, height // 2),
        (width // 3, height // 3),
        ((width * 2) // 3, (height * 2) // 3),
        (width // 4, (height * 3) // 4),
        ((width * 3) // 4, height // 4),
    ]

    unique = []
    seen = set()
    for x, y in points:
        x = max(0, min(width - 1, x))
        y = max(0, min(height - 1, y))
        if (x, y) not in seen:
            seen.add((x, y))
            unique.append((x, y))
    return unique


def _get_ap(a: int, an: int) -> int:
    return 0x808080 + an - a


def _b2_to_b(bn: int, ap: int) -> int:
    return (
        0x808080
        + bn
        - (
            0x800000
            if (ap & 0x010000) == 0
            else (0x1000000 - (ap & 0xFF0000))
        )
        - (
            0x008000
            if (ap & 0x000100) == 0
            else (0x0010000 - (ap & 0x00FF00))
        )
        - (
            0x000080
            if (ap & 0x000001) == 0
            else (0x0000100 - (ap & 0x0000FF))
        )
    )


def _c2_to_c(cn: int, ap: int) -> int:
    return (
        0x808080
        + cn
        - (
            0x800000
            if (ap & 0x010000) == 0x010000
            else (0x1000000 - (ap & 0xFF0000))
        )
        - (
            0x008000
            if (ap & 0x000100) == 0x000100
            else (0x0010000 - (ap & 0x00FF00))
        )
        - (
            0x000080
            if (ap & 0x000001) == 0x000001
            else (0x0000100 - (ap & 0x0000FF))
        )
    )


def _b3_to_b(bn: int, ap: int) -> int:
    return (
        0x808080
        + bn
        - (
            (ap & 0xFF0000)
            if (ap & 0x010000) == 0
            else (0x17F0000 - ((ap & 0xFF0000) << 1))
        )
        - (
            (ap & 0x00FF00)
            if (ap & 0x000100) == 0
            else (0x0017F00 - ((ap & 0x00FF00) << 1))
        )
        - (
            (ap & 0x0000FF)
            if (ap & 0x000001) == 0
            else (0x000017F - ((ap & 0x0000FF) << 1))
        )
    )


def _c3_to_c(cn: int, ap: int) -> int:
    return (
        0x808080
        + cn
        - (
            (0x1800000 - ((ap & 0xFF0000) << 1))
            if (ap & 0x010000) == 0
            else ((ap & 0xFF0000) + 0x010000)
        )
        - (
            (0x0018000 - ((ap & 0x00FF00) << 1))
            if (ap & 0x000100) == 0
            else ((ap & 0x00FF00) + 0x000100)
        )
        - (
            (0x0000180 - ((ap & 0x0000FF) << 1))
            if (ap & 0x000001) == 0
            else ((ap & 0x0000FF) + 0x000001)
        )
    )


def _can_114(image: QImage, version: int) -> bool:
    width = image.width()
    height = image.height()
    if width % 2 or height % 2:
        return False

    for x, y in _sample_points(width // 2, height // 2):
        a = _pixel(image, 2 * x, 2 * y)
        bn = _pixel(image, 2 * x + 1, 2 * y)
        cn = _pixel(image, 2 * x, 2 * y + 1)
        an = _pixel(image, 2 * x + 1, 2 * y + 1)

        if version == 1:
            b = bn
            c = cn
            if a != an:
                return False
        elif version == 2:
            ap = _get_ap(a, an)
            b = _b2_to_b(bn, ap)
            c = _c2_to_c(cn, ap)
        else:
            ap = _get_ap(a, an)
            b = _b3_to_b(bn, ap)
            c = _c3_to_c(cn, ap)

        if not _is_valid(a, b, c, _get_d(b, c)):
            return False

    return True


def _decode_114(image: QImage, version: int) -> List[WinPNGFile]:
    if not _can_114(image, version):
        return []

    width = image.width()
    height = image.height()
    data_image = QImage(width // 2, height // 2, QImage.Format_RGB32)

    for y in range(height // 2):
        for x in range(width // 2):
            a = _pixel(image, 2 * x, 2 * y)
            b = _pixel(image, 2 * x + 1, 2 * y)
            c = _pixel(image, 2 * x, 2 * y + 1)

            if version == 2:
                an = _pixel(image, 2 * x + 1, 2 * y + 1)
                ap = _get_ap(a, an)
                b = _b2_to_b(b, ap)
                c = _c2_to_c(c, ap)
            elif version == 3:
                an = _pixel(image, 2 * x + 1, 2 * y + 1)
                ap = _get_ap(a, an)
                b = _b3_to_b(b, ap)
                c = _c3_to_c(c, ap)

            data_image.setPixel(x, y, _get_d(b, c))

    return _decode_raw_container_image(data_image)


def _can_prototype(image: QImage) -> bool:
    width = image.width()
    height = image.height()
    if width % 2 or height % 2:
        return False

    for x, y in _sample_points(width // 2, height // 2):
        a = _pixel(image, 2 * x, 2 * y)
        b = _pixel(image, 2 * x + 1, 2 * y)
        c = _pixel(image, 2 * x, 2 * y + 1)
        d = _pixel(image, 2 * x + 1, 2 * y + 1)

        if a != d or ((b + c) & 0xFFFFFF) != 0xFFFFFF:
            return False

    return True


def _decode_prototype(image: QImage) -> List[WinPNGFile]:
    if not _can_prototype(image):
        return []

    width = image.width()
    height = image.height()
    data_image = QImage(width // 2, height // 2, QImage.Format_RGB32)

    for y in range(height // 2):
        for x in range(width // 2):
            data_image.setPixel(x, y, _pixel(image, 2 * x + 1, 2 * y))

    return _decode_raw_container_image(data_image)


def extract_winpng_files(image_bytes: bytes) -> Tuple[List[WinPNGFile], Optional[str]]:
    """Decode an unencrypted WinPNG image.

    The currently used 1:1:4 v3 format is tried first, followed by older
    1:1:4 variants, the prototype format, and finally a raw container image.
    Key/password protected WinPNG images are intentionally not guessed.
    """
    image = QImage.fromData(image_bytes)
    if image.isNull():
        return [], None

    attempts = (
        ("114v3", lambda: _decode_114(image, 3)),
        ("114v2", lambda: _decode_114(image, 2)),
        ("114v1", lambda: _decode_114(image, 1)),
        ("prototype", lambda: _decode_prototype(image)),
        ("raw", lambda: _decode_raw_container_image(image)),
    )

    for mode, decoder in attempts:
        try:
            files = decoder()
        except Exception:
            files = []

        if files:
            return files, mode

    return [], None
