import abc
import collections
import functools
from typing import (
    Callable, Deque, Generator, Generic, Iterable, Iterator, List, Optional, Sequence, Tuple,
    TypeVar, cast,
)


T = TypeVar('T')
R = TypeVar('R')

nothing = object()


class Action(Generic[T], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __repr__(self) -> str:
        ...


class ReadAction(Action[T]):
    def __repr__(self) -> str:
        return 'read()'


class DataAction(Action[T]):
    def __init__(self, data: T) -> None:
        self.data = data


class SendAction(DataAction[T]):
    def __repr__(self) -> str:
        return 'send({!r})'.format(self.data)


class PutbackAction(DataAction[T]):
    def __repr__(self) -> str:
        return 'putback({!r})'.format(self.data)


PipeGenerator = Generator[Action[T], Optional[T], R]


class MissingElement(IndexError):
    pass


class Pipe(Generic[T, R]):
    def __init__(self, generator: PipeGenerator[T, R]) -> None:
        self.generator = generator
        self.current_action = None  # type: Optional[Action[T]]
        self.buffer_in = collections.deque()  # type: Deque[T]
        self.buffer_out = collections.deque()  # type: Deque[T]
        # This is a nice way to do a Maybe[R]
        self.result = []  # type: List[R]

    def _process(self) -> None:
        while True:
            if self.current_action is None:
                self.current_action = next(self.generator)

            if isinstance(self.current_action, SendAction):
                self.buffer_out.append(self.current_action.data)
                self.current_action = None
                return
            elif isinstance(self.current_action, ReadAction):
                if not self.buffer_in:
                    return  # Can't do anything...
                self.current_action = self.generator.send(self.buffer_in.popleft())
                continue
            elif isinstance(self.current_action, PutbackAction):
                self.buffer_in.appendleft(self.current_action.data)
                self.current_action = None
            else:  # pragma: no cover
                assert False, "This should never happen if type-hinting was checked."

    def write(self, elem: T) -> None:
        """Write single element into the pipe

        Args:
            elem: element to write into the pipe.
        """
        self.buffer_in.append(elem)

    def write_many(self, elems: Sequence[T]) -> None:
        """Write many elements into the pipe

        Args:
            elems (list): All elements to push into the pipe
        """
        self.buffer_in.extend(elems)

    def read(self) -> T:
        """Read one element from the pipe.

        Returns:
            The element read from the pipe.

        Raises:
            MissingElement: When no element can be read from the pipe (yet).
        """
        self._process()
        try:
            return self.buffer_out.popleft()
        except IndexError:
            raise MissingElement

    def readall(self) -> Sequence[T]:
        """Consume as much as possible from the pipe.

        Returns:
            The list of elements that were read. (Can be empty if no elements
            were read.)
        """
        return list(self.iterate())

    def iterate(self) -> Iterator[T]:
        """Iterate over what can be consumed from the pipe.

        Returns:
            An iterator of elements. If the iterator is not consumed, elements stay in the pipe.
        """
        while True:
            try:
                yield self.read()
            except MissingElement:
                break


def iterpipe(generator: PipeGenerator[T, None], iterable: Iterable[T]) -> Iterator[T]:
    pipe = Pipe(generator)
    for elem in iterable:
        pipe.write(elem)
        try:
            res = pipe.read()
        except MissingElement:
            continue
        else:
            yield res
    yield from pipe.iterate()


def send(data: T) -> PipeGenerator[T, None]:
    yield SendAction(data)


def read() -> PipeGenerator[T, T]:
    elem = yield ReadAction()
    return cast(T, elem)


def putback(data: T) -> PipeGenerator[T, None]:
    yield PutbackAction(data)


def pipe(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Pipe[T, R]:
        return Pipe(func(*args, **kwargs))
    return wrapper
