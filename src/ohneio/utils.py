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
