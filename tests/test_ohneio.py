import ohneio
from ohneio.utils import read_until


@ohneio.protocol
def line_prefixer(prefix):
    while True:
        line = yield from read_until(b'\n')
        yield from ohneio.send(b''.join([prefix, b': ', line]))


@ohneio.protocol
def line_parser():
    line = yield from read_until(b'\n')
    return line[:-1]  # Strip the \n at the end


def test_line_prefixer():
    proto = line_prefixer(b"sent")
    proto.send(b'partial ')
    assert proto.read() == b''

    proto.send(b'line\n')
    assert proto.read() == b'sent: partial line\n'


def test_line_parser():
    proto = line_parser()

    proto.send(b'some')
    assert not proto.has_result

    proto.send(b'line\n')
    assert proto.has_result
    assert proto.get_result() == b'someline'
