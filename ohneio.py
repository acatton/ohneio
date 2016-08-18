import collections
import functools
import inspect
import io


class Buffer:
    def __init__(self):
        self.queue = collections.deque()
        self.position = 0

    def write(self, chunk):
        self.queue.append(chunk)

    def _get_queue(self):
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

    def _get_data(self, nbytes):
        if nbytes == 0:
            return len(self.queue), 0, b''.join(self._get_queue())
        else:
            acc = io.BytesIO()
            q = self._get_queue()
            segments_read = 0
            position = 0

            while True:
                try:
                    read = acc.write(next(q))
                    segments_read += 1
                except StopIteration:
                    break

                if acc.tell() >= nbytes:
                    position = acc.tell() - nbytes
                    if position != 0:
                        position = read - position
                    break

            acc.seek(0)
            return segments_read, position, acc.read(nbytes)

    def peek(self, nbytes):
        _, _, data = self._get_data(nbytes)
        return data

    def read(self, nbytes):
        segment_read, position, data = self._get_data(nbytes)
        if position > 0:
            segment_read -= 1
        for i in range(segment_read):
            self.queue.popleft()
        self.position = position

        assert len(self.queue) > 0 or self.position == 0, ("We can't have a positive position "
                                                           "on an empty queue.")

        return data

    def __len__(self):
        return sum(len(d) for d in self.queue) - self.position


_no_result = object()
_state_ended = object()


class NoResult(RuntimeError):
    pass


class Consumer:
    def __init__(self, gen):
        self.gen = gen
        self.input = Buffer()
        self.output = Buffer()
        self.state = next(gen)
        self.res = _no_result

    def _wait_before(meth):
        @functools.wraps(meth)
        def wrapper(self, *args, **kwargs):
            while self.state is _wait:
                self.state = next(self.gen)
            return meth(self, *args, **kwargs)
        return wrapper

    def _next_state(self, value=None):
        try:
            self.state = self.gen.send(value)
        except StopIteration as e:
            self.state = _state_ended
            if len(e.args) > 0:
                self.res = e.args[0]

    @property
    def has_result(self):
        return self.res is not _no_result

    def get_result(self):
        if not self.has_result:
            raise NoResult
        return self.res

    @_wait_before
    def read(self, nbytes=0):
        while self.state is _get_output:
            self._next_state(self.output)
        return self.output.read(nbytes)

    @_wait_before
    def send(self, data):
        self.input.write(data)
        while self.state is _get_input:
            self._next_state(self.input)

    def is_consumed(self):
        return len(self.input) == 0

    del _wait_before


class _Action:
    """Action yielded to the consumer.

    Actions yielded to the consumer could be `object()`, but this custom object
    with a custom `repr()` ease debugging.
    """

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<Action: {!r}'.format(self)


_get_input = _Action('get_input')
_get_output = _Action('get_output')
_wait = _Action('wait')


def peek(nbytes=0):
    input_ = yield _get_input
    return input_.peek(nbytes)


def wait():
    yield _wait


def read(nbytes=0):
    while True:
        input_ = yield _get_input
        if len(input_) >= nbytes:
            return input_.read(nbytes)
        yield _wait


def write(data):
    output = yield _get_output
    output.write(data)


def flush():
    while True:
        output = yield _get_output
        if len(output) == 0:
            return
        yield _wait


def protocol(func):
    if not callable(func):
        raise ValueError("A protocol needs to a be a callable")
    if not inspect.isgeneratorfunction(func):
        raise ValueError("A protocol needs to be a generator function")

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return Consumer(func(*args, **kwargs))

    return wrapper
