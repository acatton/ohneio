import pytest

import ohneio

BUFFER_SIZES = [1, 2, 3, 5, 7, 16, 100, 210, 256]


@ohneio.protocol
def echo_n_bytes(nbytes):
    while True:
        data = yield from ohneio.read(nbytes)
        yield from ohneio.write(data)


@pytest.mark.parametrize('read_len', BUFFER_SIZES)
@pytest.mark.parametrize('write_len', BUFFER_SIZES)
def test_buffer(read_len, write_len):
    buf = ohneio.Buffer()
    data = bytes(write_len)
    buf.write(data)
    assert len(buf.read(read_len)) == min(write_len, read_len)
    assert len(buf.read(read_len)) == min(max(write_len - read_len, 0), read_len)


def test_buffer_read_same_segment_multiple_times():
    buf = ohneio.Buffer()
    data = [b'Hello', b'world']
    for segment in data:
        buf.write(segment)
    for b in b''.join(data):
        assert buf.read(1) == bytes([b])


def test_buffer_read_chunks_over_different_segments():
    buf = ohneio.Buffer()
    for segment in [b'Hello', b'World', b'No?']:
        buf.write(segment)
    assert buf.read(3) == b'Hel'
    assert buf.read(3) == b'loW'
    assert buf.read(3) == b'orl'
    assert buf.read(4) == b'dNo?'


@pytest.mark.parametrize('nbytes', BUFFER_SIZES)
@pytest.mark.parametrize('data_len', BUFFER_SIZES)
def test_echo_n_bytes(nbytes, data_len):
    conn = echo_n_bytes(nbytes)
    data = b'\x00' * data_len

    sent = 0
    while sent < nbytes:
        assert len(conn.read()) == 0
        conn.send(data)
        sent += data_len

    assert len(conn.read(nbytes)) == nbytes


def wait_for(s):
    while True:
        data = yield from ohneio.peek()
        pos = data.find(s)
        if pos >= 0:
            return pos
        yield from ohneio.wait()


LINE_SEPARATOR = b'\n'


@ohneio.protocol
def line_reader():
    pos = yield from wait_for(LINE_SEPARATOR)
    if pos > 0:
        line = yield from ohneio.read(pos)
    else:
        line = b''
    return line


@pytest.mark.parametrize('segment_len', BUFFER_SIZES)
@pytest.mark.parametrize('input_,expected', [
    (b'\nhello', b''),
    (b'hello\n', b'hello'),
    (b'hello\nhello', b'hello'),
])
def test_line_reader(segment_len, input_, expected):
    conn = line_reader()

    for start in range(0, len(input_) + 1, segment_len):
        end = start + segment_len
        segment = input_[start:end]
        conn.send(segment)

    assert conn.has_result
    assert conn.get_result() == expected
