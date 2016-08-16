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


class Consumer:
    def __init__(self, gen):
        self.gen = gen
        self.input = Buffer()
        self.output = Buffer()
        self.state = next(gen)

    def _communicate(self, value):
        self.state = self.gen.send(value)

    def read(self, nbytes=0):
        if nbytes == 0:
            has_enough_bytes = lambda: False
        else:
            has_enough_bytes = lambda: nbytes >= len(self.output)

        acc = io.BytesIO()
        while self.state is _write and not has_enough_bytes():
            to_read = max(0, nbytes - acc.tell())
            acc.write(self.output.read(to_read))
            self._communicate(self.output)

        return acc.getvalue()

    def send(self, data):
        self.input.write(data)
        while self.state is _read:
            self._communicate(self.input)
        while self.state is _wait:
            self._communicate(None)


_read = object()
_write = object()
_wait = object()


def read(nbytes=0):
    old_len = -1
    while True:
        input_ = yield _read
        new_len = len(input_)
        if len(input_) >= nbytes:
            return input_.read(nbytes)
        if old_len == new_len:
            yield _wait
        old_len = new_len


def write(data):
    output = yield _write
    output.write(data)
    while True:
        output = yield _write
        if len(output) == 0:
            return


def protocol(func):
    if not callable(func):
        raise ValueError("A protocol needs to a be a callable")
    if not inspect.isgeneratorfunction(func):
        raise ValueError("A protocol needs to be a generator function")

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return Consumer(func(*args, **kwargs))

    return wrapper
