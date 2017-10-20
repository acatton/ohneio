import pytest

from ohneio.pipe import read, send, putback, pipe, MissingElement, iterpipe


@pipe
def infinite(elem):
    while True:
        yield from send(elem)


@pipe
def echo():
    while True:
        elem = yield from read()
        yield from send(elem)


@pipe
def duplicate():
    while True:
        elem = yield from read()
        yield from send(elem)
        yield from send(elem)


@pipe
def multiply():
    while True:
        a = yield from read()
        b = yield from read()
        yield from send(a * b)



def test_pipe_send():
    pipe = infinite(1)
    assert pipe.read() == 1
    assert pipe.read() == 1


def test_reading_from_empty_raises_exception():
    pipe = echo()
    with pytest.raises(MissingElement):
        pipe.read()


def test_pipe_read():
    pipe = echo()
    pipe.write(1)
    assert pipe.read() == 1
    pipe.write(2)
    assert pipe.read() == 2


def test_pipe_buffers():
    pipe = duplicate()
    pipe.write_many([1, 2, 3, 4])
    assert pipe.readall() == [1, 1, 2, 2, 3, 3, 4, 4]


def test_pipethrough_echoes():
    generator = echo.__wrapped__()
    assert list(iterpipe(generator, [1, 2, 3])) == [1, 2, 3]


def test_pipethrough_consume_the_whole_pipe():
    generator = duplicate.__wrapped__()
    assert list(iterpipe(generator, [1, 2])) == [1, 1, 2, 2]


def test_pipethrough_keeps_going_when_nothing_is_read():
    generator = multiply.__wrapped__()
    assert list(iterpipe(generator, [3, 4])) == [12]
