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
    data = b'\x00' * write_len
    buf.write(data)
    assert len(buf.read(read_len)) == min(write_len, read_len)
    assert len(buf.read(read_len)) == min(max(write_len - read_len, 0), read_len)


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

    assert len(conn.read()) == nbytes
