import queue
import socket
import threading
import time
import unittest
from dataclasses import replace

from src.core.config import NetworkConfig
from src.core.exceptions import ProtocolError, SendQueueFull
from src.core.protocol import (
    MessageReader, decode_message, encode_message, make_message,
    send_message, validate_envelope,
)
from src.core.transport import JsonConnection
from src.lobby.server import LobbyServer
from src.node.client import NodeClient


def wait_event(owner, kind, peer_id=None, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            event = owner.get_event(timeout=deadline - time.monotonic())
        except queue.Empty:
            break
        if event.kind == kind and (peer_id is None or event.peer_id == peer_id):
            return event
    raise AssertionError(f"Evento não recebido: {kind}, {peer_id}")


def eventually(predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Condição não atingida")


class ProtocolTests(unittest.TestCase):
    def pair(self):
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        return left, right

    def test_unicode_roundtrip(self):
        message = {"text": "Olá! 🚲"}
        self.assertEqual(decode_message(encode_message(message)[:-1]), message)

    def test_five_messages_together(self):
        sender, receiver = self.pair()
        sender.sendall(b"".join(encode_message({"n": n}) for n in range(5)))
        reader = MessageReader(receiver)
        self.assertEqual([reader.receive() for _ in range(5)],
                         [{"n": n} for n in range(5)])

    def test_fragmented_utf8(self):
        sender, receiver = self.pair()
        data = encode_message({"text": "á"})
        def write():
            for byte in data:
                sender.sendall(bytes([byte]))
                time.sleep(0.001)
        thread = threading.Thread(target=write)
        thread.start()
        self.assertEqual(MessageReader(receiver).receive(), {"text": "á"})
        thread.join()

    def test_timeout_preserves_partial_bytes(self):
        sender, receiver = self.pair()
        receiver.settimeout(0.02)
        reader = MessageReader(receiver)
        sender.sendall(b'{"text":')
        with self.assertRaises(socket.timeout):
            reader.receive()
        sender.sendall(b'"ok"}\n')
        self.assertEqual(reader.receive(), {"text": "ok"})

    def test_clean_eof(self):
        sender, receiver = self.pair()
        sender.shutdown(socket.SHUT_WR)
        self.assertIsNone(MessageReader(receiver).receive())

    def test_incomplete_eof_is_error(self):
        sender, receiver = self.pair()
        sender.sendall(b'{"text":')
        sender.shutdown(socket.SHUT_WR)
        with self.assertRaises(ProtocolError):
            MessageReader(receiver).receive()

    def test_invalid_json_objects(self):
        for line in (b"[]", b'{"x":1,"x":2}', b'{"x":NaN}',
                     b'{"x":Infinity}', b'{"x":1e999}', b"\xff",
                     b'{"x":"\\ud800"}'):
            with self.subTest(line=line), self.assertRaises(ProtocolError):
                decode_message(line)

    def test_size_limit_includes_newline(self):
        data = encode_message({"x": "abc"})
        self.assertEqual(encode_message({"x": "abc"}, len(data)), data)
        with self.assertRaises(ProtocolError):
            encode_message({"x": "abc"}, len(data) - 1)
        sender, receiver = self.pair()
        sender.sendall(data)
        with self.assertRaises(ProtocolError):
            MessageReader(receiver, len(data) - 1).receive()

    def test_large_unterminated_frame(self):
        sender, receiver = self.pair()
        sender.sendall(b"x" * 128)
        with self.assertRaises(ProtocolError):
            MessageReader(receiver, 128).receive()

    def test_validate_envelope(self):
        message = make_message("TEXT", {"text": "ok"}, "A", 1)
        self.assertIs(validate_envelope(message), message)
        for field, value in (("id", True), ("version", 2),
                             ("payload", []), ("epoch", -1)):
            invalid = dict(message, **{field: value})
            with self.subTest(field=field), self.assertRaises(ProtocolError):
                validate_envelope(invalid)

    def test_non_object_outgoing(self):
        with self.assertRaises(ProtocolError):
            encode_message(["not", "an", "object"])


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.config = NetworkConfig(
            lobby_port=0, peer_port=0, peer_bind_host="127.0.0.1",
            io_timeout=0.1, connect_timeout=0.5, mesh_timeout=2,
        )

    def lobby(self):
        server = LobbyServer(self.config)
        server.start()
        self.addCleanup(server.close)
        return server

    def node(self, name, server=None, **kwargs):
        config = self.config
        if server:
            config = replace(config, lobby_port=server.address[1])
        node = NodeClient(name, config, **kwargs)
        node.start()
        self.addCleanup(node.close)
        return node

    def test_three_clients_and_independent_reception(self):
        server = self.lobby()
        nodes = [self.node(name, server) for name in ("A", "B", "C")]
        for node in nodes:
            node.connect_lobby()
        for _ in nodes:
            wait_event(server, "connected")
        self.assertEqual(len(server.client_ids), 3)
        for node in nodes:
            node.send("lobby", "TEXT", {"name": node.player_id})
        requests = [wait_event(server, "message") for _ in nodes]
        for event in requests:
            server.send(event.peer_id, "ECHO", event.message["payload"],
                        reply_to=event.message["id"])
        for node in nodes:
            event = wait_event(node, "message", "lobby")
            self.assertEqual(event.message["payload"], {"name": node.player_id})
        # Mensagem espontânea sem novo input/envio do cliente.
        for client_id in server.client_ids:
            server.send(client_id, "NOTICE", {"text": "aviso"})
        for node in nodes:
            self.assertEqual(wait_event(node, "message").message["type"], "NOTICE")

    def test_anonymous_registration_then_assigned_id(self):
        server = self.lobby()
        node = self.node("temporary", server)
        node.connect_lobby()
        request_id = node.send(
            "lobby", "REGISTER",
            {"nickname": "Ana", "peer_endpoint": node.advertised_endpoint},
            anonymous=True,
        )
        event = wait_event(server, "message")
        self.assertIsNone(event.message["sender_id"])
        self.assertEqual(event.message["id"], request_id)
        node.set_player_id("assigned")
        node.send("lobby", "TEXT", {"text": "ok"})
        self.assertEqual(wait_event(server, "message").message["sender_id"],
                         "assigned")

    def test_mesh_of_four_and_bidirectional_messages(self):
        nodes = [self.node(name) for name in ("A", "B", "C", "D")]
        addresses = {node.player_id: node.address for node in nodes}
        for node in nodes:
            node.set_peers({key: addr for key, addr in addresses.items()
                            if key != node.player_id})
        for node in nodes:
            node.connect_mesh()
        eventually(lambda: all(len(n.connected_ids) == 3 for n in nodes))
        self.assertEqual(sum(len(n.connected_ids) for n in nodes), 12)
        for node in nodes:
            self.assertEqual(node.broadcast("TEXT", {"from": node.player_id}), {})
        for node in nodes:
            messages = [wait_event(node, "message") for _ in range(3)]
            self.assertEqual({e.peer_id for e in messages},
                             set(addresses) - {node.player_id})

    def test_lobby_failure_does_not_close_peer_connection(self):
        server = self.lobby()
        a, b = self.node("A", server), self.node("B", server)
        a.set_peers({"B": b.address})
        b.set_peers({"A": a.address})
        a.connect_peer("B")
        for node in (a, b):
            node.connect_lobby()
        eventually(lambda: "A" in b.connected_ids)
        server.close()
        for node in (a, b):
            wait_event(node, "disconnected", "lobby")
        b.send("A", "TEXT", {"still": "playing"})
        self.assertEqual(wait_event(a, "message", "B").message["payload"],
                         {"still": "playing"})

    def test_disconnect_event_once(self):
        server = self.lobby()
        node = self.node("A", server)
        node.connect_lobby()
        connection_id = wait_event(server, "connected").peer_id
        node.close()
        wait_event(server, "disconnected", connection_id)
        time.sleep(0.15)
        with self.assertRaises(queue.Empty):
            server.get_event(timeout=0.05)

    def test_reject_invalid_peer_does_not_stop_listener(self):
        a, b = self.node("A"), self.node("B")
        a.set_peers({"B": b.address})
        b.set_peers({"A": a.address})
        with socket.create_connection(b.address) as bad:
            bad.sendall(b"not json\n")
        wait_event(b, "error")
        a.connect_peer("B")
        wait_event(b, "connected", "A")

    def test_reject_wrong_attempt(self):
        a = self.node("A", attempt_id="old")
        b = self.node("B", attempt_id="new")
        a.set_peers({"B": b.address})
        b.set_peers({"A": a.address})
        with self.assertRaises((OSError, ProtocolError)):
            a.connect_peer("B")
        self.assertNotIn("B", a.connected_ids)

    def test_smaller_id_must_connect(self):
        a, b = self.node("A"), self.node("B")
        b.set_peers({"A": a.address})
        with self.assertRaises(ValueError):
            b.connect_peer("A")

    def test_explicit_peer_removal_and_lifecycle(self):
        a, b = self.node("A"), self.node("B")
        a.set_peers({"B": b.address})
        b.set_peers({"A": a.address})
        a.connect_peer("B")
        wait_event(b, "connected", "A")
        a.disconnect("B", forget=True)
        wait_event(b, "disconnected", "A")
        self.assertNotIn("B", a.connected_ids)
        with self.assertRaises(ValueError):
            a.connect_peer("B")
        a.close()
        with self.assertRaises(RuntimeError):
            a.start()

    def test_pending_byte_limit(self):
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        sender = socket.create_connection(listener.getsockname())
        receiver, _ = listener.accept()
        self.addCleanup(receiver.close)
        conn = JsonConnection(
            sender, "slow", replace(self.config, max_pending_bytes=128),
            lambda connection, message: None,
            lambda connection, error: None,
        )
        self.addCleanup(conn.close)
        with self.assertRaises(SendQueueFull):
            conn.send({"text": "x" * 256})
        self.assertTrue(conn.closed)

    def test_queue_overflow_is_explicit(self):
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        sender = socket.create_connection(listener.getsockname())
        receiver, _ = listener.accept()
        self.addCleanup(receiver.close)
        errors = []
        conn = JsonConnection(
            sender, "slow", replace(self.config, max_pending_messages=1),
            lambda connection, message: None,
            lambda connection, error: errors.append(error),
        )
        self.addCleanup(conn.close)
        # Sem iniciar writer, a fila fica ocupada de forma determinística.
        conn.send({"n": 1})
        with self.assertRaises(SendQueueFull):
            conn.send({"n": 2})
        self.assertTrue(conn.closed)
        self.assertEqual(len(errors), 1)

    def test_message_ids_increase_with_concurrent_senders(self):
        server = self.lobby()
        node = self.node("A", server)
        node.connect_lobby()
        threads = [threading.Thread(
            target=lambda: [node.send("lobby", "TEXT", {"n": n}) for n in range(5)]
        ) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        received = [wait_event(server, "message").message["id"] for _ in range(20)]
        self.assertEqual(received, list(range(1, 21)))

    def test_partial_message_survives_connection_reader_timeout(self):
        server = self.lobby()
        with socket.create_connection(server.address) as sender:
            wait_event(server, "connected")
            data = encode_message(make_message("TEXT", {"text": "ok"}, "A", 1))
            sender.sendall(data[:20])
            time.sleep(0.25)
            sender.sendall(data[20:])
            self.assertEqual(wait_event(server, "message").message["type"], "TEXT")

    def test_invalid_envelope_disconnects_only_its_client(self):
        server = self.lobby()
        good = self.node("A", server)
        good.connect_lobby()
        wait_event(server, "connected")
        with socket.create_connection(server.address) as bad:
            bad_id = wait_event(server, "connected").peer_id
            bad.sendall(b'{"text":"sem envelope"}\n')
            event = wait_event(server, "disconnected", bad_id)
            self.assertIsNotNone(event.error)
            self.assertEqual(len(server.client_ids), 1)
        good.send("lobby", "TEXT", {"text": "continua"})
        self.assertEqual(wait_event(server, "message").message["payload"],
                         {"text": "continua"})


if __name__ == "__main__":
    unittest.main()
