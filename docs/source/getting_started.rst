Introduction
============


FAQ
---


Why not asyncio ?
~~~~~~~~~~~~~~~~~

asyncio_ is a great library, and Ohne I/O can be used in combination with
asyncio_, but it can also be used in combination with `raw sockets`_ and/or
any network library.

Ohne I/O does not intend to compete in *any way* with asyncio_, it even intends
to be used in combination with asyncio_. (but it is not limited to asyncio_)

.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _raw sockets: https://docs.python.org/3/library/socket.html

The power of ``ohneio`` resides in the fact that **it does not produce any I/O**.
It only buffers byte streams, and allows developers to write simple stream parser
like they would write a coroutine.

This is how you would use an ``ohneio`` protocol:

.. code-block:: python

    parser = protocol()
    parser.send(bytes_to_send)
    received_bytes = parser.read()


Because ``ohneio`` can be considered as connection without I/O, this
documentation will referred to them with the variable ``conn``.

Writing an ``ohneio`` protocol parser is better than writing an asyncio_
protocol library, in the sense that your protocol could be then used by anybody
with any library.

Ohne I/O relies on the concept of `sans-io`_, which is the concept of writing
generic protocol parser, easily testable.

.. _sans-io: https://sans-io.readthedocs.io/


How does it work internally?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ohneio`` buffers data coming in or out. Thanks to generator functions, it
pauses protocol parsers execution until new data is fed in or read from the
parser.


Why not use manual buffers?
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ohneio`` kinda borrows from `parser combinators`_, it allows you to write
simple functions without passing objects around. And combine these functions
without managing any state.

.. _parser combinators: https://en.wikipedia.org/wiki/Parser_combinator

``ohneio`` also provides some primitives to wait for a certain amount of data,
or wait for more data.

Writing simple protocol parser, could very quickly lead to either spaghetti
code, badly abstracted code. ``ohneio`` tries to avoid this.


Getting started
---------------

To get started we'll write a simple line echo server. This protocol echoes each
line sent to the server. A line is defined by a sequence of bytes terminated by
the bytes ``0x0A``.

Writing a protocol
~~~~~~~~~~~~~~~~~~

.. literalinclude:: getting_started_ohneio_protocol.py
    :language: python
    :lines: 1, 3-32


Testing the protocol
~~~~~~~~~~~~~~~~~~~~

Because the protocol doesn't produce any I/O, you can directly simulates in
which order, and which segments of data will be read/buffered. And what should
be send back.

.. literalinclude:: getting_started_ohneio_protocol.py
    :language: python
    :lines: 2, 33-


Using a protocol
~~~~~~~~~~~~~~~~

Now that you wrote your echo protocol, you need to make it use the network, you
can use any network library you want:


Raw sockets
^^^^^^^^^^^

This example shows how to use Ohne I/O in combination with raw sockets and
``select()``. This creates one instance of the ``echo()`` protocol per connection.

It then feeds data comming in the connection to the Ohne I/O protocol, then it
feeds the output of the Ohne I/O protocol to the socket.

.. code-block:: python
    :emphasize-lines: 38, 45-46

    import contextlib
    import select
    import socket


    BUFFER_SIZE = 1024


    @contextlib.contextmanager
    def create_server(host, port):
        for res in socket.getaddrinfo(host, port):
            af, socktype, proto, canonname, sa = res
            try:
                s = socket.socket(af, socktype, proto)
            except socket.error:
                continue
            try:
                s.bind(sa)
                s.listen(1)
                yield s
                return
            except socket.error:
                continue
            finally:
                s.close()
        raise RuntimeError("Couldn't create a connection")


    def echo_server(host, port):
        connections = {}  # open connections: fileno -> (socket, protocol)
        with create_server(host, port) as server:
            while True:
                rlist, _, _ = select.select([server.fileno()] + list(connections.keys()), [], [])

                for fileno in rlist:
                    if fileno == server.fileno():  # New connection
                        conn, _ = server.accept()
                        connections[conn.fileno()] = (conn, echo())
                    else:  # Data comming in
                        sock, proto = connections[fileno]
                        data = sock.recv(BUFFER_SIZE)
                        if not data:  # Socket closed
                            del connections[fileno]
                            continue
                        proto.send(data)
                        data = proto.read()
                        if data:
                            sock.send(data)


    if __name__ == '__main__':
        import sys
        echo_server(host=sys.argv[1], port=sys.argv[2])


``gevent``
^^^^^^^^^^

This example shows how to use Ohne I/O in combination with gevent library:

.. code-block:: python

    import gevent
    from gevent.server import StreamServer


    BUFFER_SIZE = 1024


    def echo_server(host, port):
        server = StreamServer((host, port), handle)
        try:
            server.serve_forever()
        finally:
            server.close()


    def handle(socket, _):
        conn = echo()
        try:
            while True:
                data = socket.recv(BUFFER_SIZE)
                if not data:
                    break
                conn.send(data)
                data = conn.read()
                if data:
                    socket.send(data)
                gevent.sleep(0)  # Prevent one green thread from taking over
        finally:
            socket.close()


    if __name__ == '__main__':
        import sys
        echo_server(host=sys.argv[1], port=int(sys.argv[2]))
