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


def read_until(s):
    pos = yield from wait_for(LINE_SEPARATOR)
    if pos > 0:
        data = yield from ohneio.read(pos)
    else:
        data = b''
    return data


LINE_SEPARATOR = b'\n'


@ohneio.protocol
def line_reader():
    line = yield from read_until(LINE_SEPARATOR)
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


def test_line_reader_no_result():
    conn = line_reader()
    conn.send(b'hello')
    assert not conn.has_result


@ohneio.protocol
def echo():
    while True:
        line = yield from read_until(LINE_SEPARATOR)
        yield from ohneio.read(len(LINE_SEPARATOR))
        yield from ohneio.write(line)
        yield from ohneio.write(LINE_SEPARATOR)


def test_echo():
    conn = echo()
    conn.send(b'hello')
    assert conn.read() == b''
    conn.send(b'\nworld')
    assert conn.read() == b'hello\n'
    conn.send(b'\nand the rest\n')
    assert conn.read() == b'world\nand the rest\n'
