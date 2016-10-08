import ohneio
import pytest


NEW_LINE = b'\n'


def wait_for(s):
    """Wait for a certain string to be available in the buffer."""
    while True:
        data = yield from ohneio.peek()
        pos = data.find(s)
        if pos > 0:
            return pos
        yield from ohneio.wait()


def read_upto(s):
    """Read data up to the specified string in the buffer.

    If this string is not available in the buffer, this waits for the string to be available.
    """
    pos = yield from wait_for(s)
    data = yield from ohneio.read(pos + len(s))
    return data


@ohneio.protocol
def echo():
    while True:
        line = yield from read_upto(NEW_LINE)
        yield from ohneio.write(line)


@pytest.fixture
def conn():
    return echo()


@pytest.mark.parametrize('input_, expected_output', [
    (b"Hello World", b""),
    (b"Hello World\n", b"Hello World\n"),
    (b"Hello World\nAnd", b"Hello World\n"),
    (b"Hello World\nAnd the universe\n", b"Hello World\nAnd the universe\n"),
])
def test_only_echo_complete_lines(conn, input_, expected_output):
    conn.send(input_)
    assert conn.read() == expected_output


def test_buffers_segments(conn):
    conn.send(b"Hello ")
    assert conn.read() == b''
    conn.send(b"World\n")
    assert conn.read() == b"Hello World\n"
