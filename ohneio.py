import collections
import functools
import inspect
import io
import typing


class Buffer(typing.Sized):
    def __init__(self) -> None:
        self.queue = collections.deque()  # type: collections.deque[bytes]
        self.position = 0

    def write(self, chunk: bytes) -> None:
        self.queue.append(chunk)

    def _get_queue(self) -> typing.Generator[bytes, typing.Any, typing.Any]:
        assert len(self.queue) > 0 or self.position == 0, ("We can't have a positive position "
                                                           "on an empty queue.")

        q = iter(self.queue)
        try:
            data = next(q)
            yield data[self.position:]
        except StopIteration:
            pass
        else:
            yield from q

    def _get_data(self, nbytes: int):
        if nbytes == 0:
            return len(self.queue), 0, b''.join(self._get_queue())
        else:
            acc = io.BytesIO()
            q = self._get_queue()
            segments_read = 0
            position = self.position
            to_read = nbytes

            while True:
                try:
                    segment_len = acc.write(next(q))
                    to_read -= segment_len
                    segments_read += 1
                except StopIteration:
                    break

                if acc.tell() >= nbytes:
                    assert to_read <= 0
                    position += segment_len + to_read
                    break

                position = 0

            acc.seek(0)
            return segments_read, position, acc.read(nbytes)

    def peek(self, nbytes: int=0) -> bytes:
        _, _, data = self._get_data(nbytes)
        return data

    def read(self, nbytes: int=0) -> bytes:
        segment_read, position, data = self._get_data(nbytes)
        if position > 0:
            segment_read -= 1
        for i in range(segment_read):
            self.queue.popleft()
        self.position = position

        assert len(self.queue) > 0 or self.position == 0, ("We can't have a positive position "
                                                           "on an empty queue.")

        return data

    def __len__(self) -> int:
        return sum(len(d) for d in self.queue) - self.position

    def __repr__(self) -> str:
        return '<{self.__class__.__name__} {self.queue!r} pos={self.position}>'.format(self=self)


class _NoResultType:
    pass


class _StateEndedType:
    pass


_no_result = _NoResultType()
_state_ended = _StateEndedType()


class NoResult(RuntimeError):
    """Raised when no result is available."""


class _Action:
    """Action yielded to the consumer.

    Actions yielded to the consumer could be `object()`, but this custom object
    with a custom `repr()` ease debugging.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return '<Action: {!r}>'.format(self.name)


_get_input = _Action('get_input')
_get_output = _Action('get_output')
_wait = _Action('wait')


T = typing.TypeVar('T')


class ProtocolGenerator(typing.Generator[_Action, typing.Union[None, Buffer], T],
                        typing.Generic[T]):
    pass


S = typing.TypeVar('S')


class Consumer(typing.Generic[S]):
    """Protocol consumer

    Allows the developer to send, read and get the result of protocol function.

    This never needs to be instantiated, since this internally done by the :func:`~ohneio.protocol`
    decorator.
    """
    def __init__(self, gen: ProtocolGenerator[S]) -> None:
        self.gen = gen
        self.input = Buffer()
        self.output = Buffer()
        self.state = next(gen)  # type: typing.Union[_Action, _StateEndedType]
        if not isinstance(self.state, _Action):  # pragma: no cover
            # This is just a hint for users misusing the library.
            raise RuntimeError("Can't yield anything else than an action. Using `yield` instead "
                               "`yield from`?")
        self.res = _no_result  # type: typing.Union[S, _NoResultType]

    def _process(self) -> None:
        if self.has_result:
            return

        while self.state is _wait:
            self._next_state()
        while True:
            if self.state is _get_output:
                self._next_state(self.output)
            elif self.state is _get_input:
                self._next_state(self.input)
            else:
                break

    def _next_state(self, value: typing.Union[Buffer, None]=None) -> None:
        try:
            self.state = self.gen.send(value)
            if not isinstance(self.state, _Action):  # pragma: no cover
                # This is just a hint for users misusing the library.
                raise RuntimeError("Can't yield anything else than an action. Using `yield` "
                                   "instead `yield from`?")
        except StopIteration as e:
            self.state = _state_ended
            if len(e.args) > 0:
                self.res = e.args[0]

    @property
    def has_result(self) -> bool:
        """bool: Whether a result is available or not"""
        return self.res is not _no_result

    def get_result(self) -> S:
        """Get the result from the protocol

        Returns:
            The object returned by the protocol.

        Raises:
            NoResult: When no result is available
        """
        self._process()
        if not self.has_result:
            raise NoResult
        assert not isinstance(self.res, _NoResultType)
        return self.res

    def read(self, nbytes: int=0) -> bytes:
        """Read bytes from the output of the protocol.

        Args:
            nbytes: Read *at most* ``nbytes``, less bytes can be returned. If ``nbytes=0``
                then all available bytes are read.

        Returns:
            bytes: bytes read
        """
        acc = io.BytesIO()
        while True:
            if nbytes == 0:
                to_read = 0
            else:
                to_read = nbytes - acc.tell()

            acc.write(self.output.read(to_read))

            if nbytes > 0 and acc.tell() == nbytes:
                break

            self._process()

            if len(self.output) == 0:
                break
        return acc.getvalue()

    def send(self, data: bytes) -> None:
        """Send data to the input of the protocol

        Args:
            bytes: data to send to the protocol

        Returns:
            None
        """
        self.input.write(data)
        self._process()


def peek(nbytes=0) -> typing.Generator[_Action, Buffer, bytes]:
    """Read output without consuming it.

    Read but **does not** consume data from the protocol input.

    This is a *non-blocking* primitive, if less data than requested is available,
    less data is returned. It is meant to be used in combination with :func:`~ohneio.wait`, but
    edge cases and smart people can (and most likely will) prove me wrong.

    Args:
        nbytes (:obj:`int`, optional): amount of bytes to read *at most*. ``0`` meaning all bytes.

    Returns:
        bytes: data read from the buffer
    """
    input_ = yield _get_input
    return input_.peek(nbytes)


def wait() -> typing.Generator[_Action, None, None]:
    """Wait for any action to be triggered on the consumer.

    This waits for any action to be triggered on the consumer, in most cases, this means more
    input is available or some output has been consumed. *But, it could also mean that the result
    of the protocol has been polled.* Therefore, it is always considered a good practice to wait
    at the end of a loop, and execute your non-blocking primitive before.

    Returns:
        None

    Example:
        >>> def wait_for(b):
        ...   while True:
        ...     data = yield from peek()
        ...     pos = data.find(b)
        ...     if pos >= 0:
        ...       return pos
        ...     yield from wait()
        ...
        >>> @protocol
        ... def linereader():
        ...   pos = yield from wait_for(b'\\n')
        ...   data = yield from read(pos)
        ...   return data.decode('ascii')
        ...
        >>> conn = linereader()
        >>> conn.send(b"Hello ")
        >>> conn.has_result
        False
        >>> conn.read()
        b''
        >>> conn.send(b"World\\nRight?")
        >>> conn.get_result()
        'Hello World'
    """
    yield _wait


def read(nbytes: int=0) -> typing.Generator[_Action, typing.Union[Buffer, None], bytes]:
    """Read and consume data.

    Read and consume data from the protocol input. And wait for it if an amount
    of bytes is specified.

    Args:
        nbytes (:obj:`int`, optional): amount of bytes to read. If ``nbytes=0``, it reads all
            data available in the buffer, and does not block. Therefore, it means if no data
            is available, it will return 0 bytes.

    Returns:
        bytes: data read from the buffer.

    Example:

        >>> @protocol
        ... def reader():
        ...    data = yield from read()
        ...    print("Read:", repr(data))
        ...    data = yield from read(3)
        ...    print("Read:", repr(data))
        ...
        >>> conn = reader()
        >>> conn.send(b'Hello')
        Read: b'Hello'
        >>> conn.send(b'fo')
        >>> conn.send(b'obar')
        Read: b'foo'
    """
    while True:
        input_ = yield _get_input
        if len(input_) >= nbytes:
            return input_.read(nbytes)
        yield from wait()


def write(data: bytes) -> typing.Generator[_Action, typing.Union[Buffer, None], None]:
    """Write and flush data.

    Write data to the protocol output, and wait for it to be entirely consumed.

    *This is a generator function that has to be used with ``yield from``.*

    Args:
        data (bytes): data to write to the output.

    Returns:
        None: Only when the data has been entirely consumed.

    Example:

        >>> @protocol
        ... def foo():
        ...     yield from write(b'foo')
        ...     return "Done!"
        ...
        >>> conn = foo()
        >>> conn.read(1)
        b'f'
        >>> conn.has_result
        False
        >>> conn.read(2)
        b'oo'
        >>> conn.get_result()
        'Done!'
    """
    output = yield _get_output
    output.write(data)
    while len(output) != 0:
        yield from wait()
        output = yield _get_output


R = typing.TypeVar('R')


def protocol(func: typing.Callable[..., ProtocolGenerator[R]]) -> typing.Callable[..., Consumer[R]]:
    """Wraps a Ohne I/O protocol function.

    Under the hood this wraps the generator inside a :class:`~ohneio.Consumer`.

    Args:
        func (callable): Protocol function to wrap. (Protocol functions have to be generators)

    Returns:
        callable: wrapped function.
    """
    if not callable(func):  # pragma: no cover
        # This is for users misusing the library, type hinting already checks this
        raise ValueError("A protocol needs to a be a callable")
    if not inspect.isgeneratorfunction(func):  # pragma: no cover
        # This is for users misusing the library, type hinting already checks this
        raise ValueError("A protocol needs to be a generator function")

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return Consumer(func(*args, **kwargs))

    return wrapper
