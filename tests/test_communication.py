import queue
import socket
import threading
import time
import unittest
from unittest.mock import patch

from src.core.protocol import (
    encode_message, make_message, receive_message, validate_message,
)
from src.core.transport import Connection, listen
from src.node.client import NodeClient


def wait_event(node, kind, peer_id=None):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        event = node.get_event(timeout=deadline - time.monotonic())
        if event["kind"] == kind and (
            peer_id is None or event["peer_id"] == peer_id
        ):
            return event
    raise AssertionError(f"Evento ausente: {kind}")


def eventually(condition):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("Condição não atingida")


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.sender, self.receiver = socket.socketpair()
        self.addCleanup(self.sender.close)
        self.addCleanup(self.receiver.close)

    def test_multiple_messages_preserve_buffer(self):
        self.sender.sendall(b"".join(
            encode_message({"n": n}) for n in range(5)
        ))
        buffer = b""
        for n in range(5):
            message, buffer = receive_message(self.receiver, buffer)
            self.assertEqual(message, {"n": n})

    def test_unicode_fragmented_with_timeout(self):
        self.receiver.settimeout(0.02)
        data = encode_message({"text": "Olá 🚲"})
        def send():
            for byte in data:
                self.sender.sendall(bytes([byte]))
                time.sleep(0.025)
        thread = threading.Thread(target=send)
        thread.start()
        message, _ = receive_message(self.receiver, b"")
        thread.join()
        self.assertEqual(message, {"text": "Olá 🚲"})

    def test_clean_and_incomplete_eof(self):
        self.sender.shutdown(socket.SHUT_WR)
        self.assertEqual(receive_message(self.receiver, b""), (None, b""))
        with self.assertRaises(ConnectionError):
            receive_message(self.receiver, b'{"partial":')

    def test_invalid_frames(self):
        for raw in (b"[]\n", b'{"a":1,"a":2}\n', b'{"a":NaN}\n',
                    b'{"a":1e999}\n', b'{"a":"\\ud800"}\n', b"\xff\n"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                receive_message(self.receiver, raw)

    def test_message_limit(self):
        with patch("src.core.protocol.MAX_MESSAGE_BYTES", 16):
            with self.assertRaises(ValueError):
                encode_message({"text": "x" * 20})
            with self.assertRaises(ValueError):
                receive_message(self.receiver, b"x" * 16)

    def test_envelope(self):
        valid = make_message("TEXT", {"text": "ok"}, "A", 1)
        validate_message(valid)
        for field, value in (("id", True), ("epoch", -1),
                             ("payload", []), ("version", 2)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_message(dict(valid, **{field: value}))


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.connections = []

    def node(self, name, **kwargs):
        node = NodeClient(name, peer_host="127.0.0.1", peer_port=0, **kwargs)
        node.start()
        self.addCleanup(node.close)
        return node

    def echo_server(self):
        def accept(sock, address):
            counter = iter(range(1, 10000))
            connection = Connection(
                sock,
                lambda message: connection.send(make_message(
                    "ECHO", message["payload"], "lobby",
                    next(counter), reply_to=message["id"],
                )),
                lambda error: None,
            )
            self.connections.append(connection)
            connection.start()
        server = listen("127.0.0.1", 0, accept)
        def close():
            server.close()
            for connection in self.connections:
                connection.close()
        self.addCleanup(close)
        return server

    def test_three_clients(self):
        server = self.echo_server()
        nodes = [self.node(name) for name in ("A", "B", "C")]
        for node in nodes:
            node.connect_lobby(*server.getsockname())
            node.send("lobby", "TEXT", {"name": node.player_id})
        for node in nodes:
            self.assertEqual(
                wait_event(node, "message")["message"]["payload"],
                {"name": node.player_id},
            )

    def test_unsolicited_message_and_disconnect(self):
        server = self.echo_server()
        node = self.node("A")
        node.connect_lobby(*server.getsockname())
        eventually(lambda: len(self.connections) == 1)
        self.connections[0].send(make_message(
            "NOTICE", {"text": "sem pedido"}, "lobby", 1
        ))
        self.assertEqual(wait_event(node, "message")["message"]["type"], "NOTICE")
        self.connections[0].close()
        wait_event(node, "disconnected", "lobby")
        with self.assertRaises(queue.Empty):
            node.get_event(timeout=0.1)

    def test_four_node_mesh_and_lobby_failure(self):
        server = self.echo_server()
        nodes = [self.node(name) for name in ("A", "B", "C", "D")]
        addresses = {n.player_id: n.server.getsockname() for n in nodes}
        for node in nodes:
            node.connect_lobby(*server.getsockname())
            node.connect_mesh({
                peer: addr for peer, addr in addresses.items()
                if peer != node.player_id
            })
        eventually(lambda: all(len(n.connections) == 4 for n in nodes))
        for connection in self.connections:
            connection.close()
        for node in nodes:
            wait_event(node, "disconnected", "lobby")
        for node in nodes:
            node.broadcast("TEXT", {"from": node.player_id})
        for node in nodes:
            received = [wait_event(node, "message") for _ in range(3)]
            self.assertEqual(
                {e["peer_id"] for e in received},
                set(addresses) - {node.player_id},
            )

    def test_failed_handshake_does_not_stop_listener(self):
        a, b = self.node("A"), self.node("B")
        with socket.create_connection(b.server.getsockname()) as bad:
            bad.sendall(b"invalid\n")
        wait_event(b, "error")
        addresses = {"A": a.server.getsockname(), "B": b.server.getsockname()}
        b.connect_mesh({"A": addresses["A"]})
        a.connect_mesh({"B": addresses["B"]})
        wait_event(a, "connected", "B")

    def test_wrong_context_is_rejected(self):
        a = self.node("A", attempt_id="old")
        b = self.node("B", attempt_id="new")
        b.peers = {"A": a.server.getsockname()}
        with self.assertRaises((ValueError, OSError)):
            a._connect_peer("B", b.server.getsockname())
        self.assertNotIn("A", b.connections)

    def test_concurrent_sends_do_not_mix_messages(self):
        server = self.echo_server()
        node = self.node("A")
        node.connect_lobby(*server.getsockname())
        threads = [
            threading.Thread(target=lambda: [
                node.send("lobby", "TEXT", {"n": n}) for n in range(5)
            ]) for _ in range(4)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        replies = [wait_event(node, "message")["message"] for _ in range(20)]
        self.assertEqual([r["reply_to"] for r in replies], list(range(1, 21)))

    def test_partial_eof_reports_error(self):
        events = queue.Queue()
        def accept(sock, address):
            connection = Connection(sock, lambda message: None,
                                    lambda error: events.put(error))
            self.connections.append(connection)
            connection.start()
        server = listen("127.0.0.1", 0, accept)
        self.addCleanup(server.close)
        with socket.create_connection(server.getsockname()) as sender:
            sender.sendall(b'{"partial":')
        self.assertIn("incompleta", events.get(timeout=3))


if __name__ == "__main__":
    unittest.main()
