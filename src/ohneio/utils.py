import struct
import io
from typing import Any, Callable

from . import Protocol, read, send, putback

__all__ = ['readstr', 'sendstr', 'read_until']


def readstr(encoding: str='utf-8') -> Protocol[str]:
    """Read a string from the protocol.

    If the stream contains partial unicode data, this one will be put back into the stream for
    later processing.

    Args:
        encoding (str): encoding to use to decode the bytes into a string

    Raises:
        UnicodeDecodeError if the data can't be decoded.
    """
    # TODO: Use IncrementalDecoder
    data = yield from read()
    return data.decode(encoding)


def sendstr(s: str, encoding: str='utf-8') -> Protocol[None]:
    """Send a string to the protocol.

    Args:
        s (str): String to send.
        encoding (str): encoding to use to encode the string into bytes.

    Raises:
        UnicodeEncodeError if the data can't be encoded.
    """
    yield from send(s.encode(encoding))


def read_until(b: bytes, included: bool=True) -> Protocol[bytes]:
    """Read the input until certain bytes match

    Args:
        b (bytes): Stop reading when this sequence of bytes is in the input.
        included (bool): Whether or not to consume the bytes in question

    Returns:
        bytes that were read.
    """
    # TODO: This is not optimized at all, but for praciticity purposes.
    # TODO: Optimize this.
    acc = bytes()
    while b not in acc:
        acc += yield from read()

    data, sep, leftover = acc.partition(b)
    assert sep == b

    if included:
        yield from putback(leftover)
        return data + sep
    else:
        yield from putback(sep + leftover)
        return data


def read_nbytes(n: int) -> Protocol[bytes]:
    """Read a certain an *exact* amount of bytes.

    Args:
        n (int): Amount of bytes to be read.

    Returns:
        bytes that we read.
    """
    buf = io.BytesIO()
    while buf.tell() < n:
        incomming = yield from read()
        buf.write(incomming)
    buf.seek(0, io.SEEK_SET)

    data = buf.read(n)
    leftover = buf.read()
    yield from putback(leftover)
    return data


def struct_reader(fmt: str) -> Callable[[], Protocol[Any]]:
    """Factory for a protocol function that reads a C struct.

    This factory uses the struct.pack() and struct.unpack() in the background. Refers to the module
    documentation for more information.

    Args:
        fmt (str): Format string to read the C struct from.

    Returns:
        A protocol generator.
    """
    data_length = struct.calcsize(fmt)

    def generator() -> Protocol[Any]:
        data = yield from read_nbytes(data_length)
        return struct.unpack(fmt, data)

    return generator
