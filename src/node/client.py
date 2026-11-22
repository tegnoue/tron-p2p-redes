"""Rede do jogador. As regras do jogo consomem os eventos recebidos."""
import itertools
import queue
import socket
import threading
import time

from src.core import config
from src.core.protocol import (
    make_message, receive_message, send_message, validate_message,
)
from src.core.transport import Connection, listen


class NodeClient:
    def __init__(self, player_id, peer_host=config.PEER_BIND_HOST,
                 peer_port=config.PEER_PORT, match_id="demo", attempt_id="demo"):
        if not isinstance(player_id, str) or not 1 <= len(player_id) <= 64:
            raise ValueError("ID do jogador inválido.")
        if player_id == "lobby":
            raise ValueError("ID reservado.")
        self.player_id = player_id
        self.peer_host, self.peer_port = peer_host, peer_port
        self.match_id, self.attempt_id = match_id, attempt_id
        self.epoch = 0
        self.events = queue.Queue()
        self.connections = {}
        self.counters = {}
        self.peers = {}
        self.lock = threading.RLock()
        self.stopped = threading.Event()
        self.server = None

    def start(self):
        if self.server is not None or self.stopped.is_set():
            raise RuntimeError("Aplicativo já iniciado ou encerrado.")
        self.server = listen(self.peer_host, self.peer_port, self._accept_peer)

    def _attach(self, sock, peer_id, buffer=b"", first_id=1):
        connection = Connection(
            sock,
            lambda message: self._received(peer_id, message),
            lambda error: self._disconnected(peer_id, connection, error),
            buffer,
        )
        with self.lock:
            if self.stopped.is_set() or peer_id in self.connections:
                sock.close()
                raise ConnectionError("Aplicativo encerrado ou par duplicado.")
            self.connections[peer_id] = connection
            self.counters[peer_id] = itertools.count(first_id)
            self.events.put({"kind": "connected", "peer_id": peer_id})
        connection.start()

    def _received(self, peer_id, message):
        if message["sender_id"] != peer_id:
            raise ValueError("Identidade incompatível com a conexão.")
        if peer_id != "lobby":
            self._check_context(message)
        self.events.put({
            "kind": "message", "peer_id": peer_id, "message": message,
        })

    def _disconnected(self, peer_id, connection, error):
        with self.lock:
            if self.connections.get(peer_id) is connection:
                self.connections.pop(peer_id)
                self.counters.pop(peer_id)
        self.events.put({
            "kind": "disconnected", "peer_id": peer_id, "error": error,
        })

    def _check_context(self, message):
        if (message["match_id"], message["attempt_id"]) != (
            self.match_id, self.attempt_id
        ):
            raise ValueError("Partida ou tentativa incorreta.")

    def _accept_peer(self, sock, address):
        try:
            sock.settimeout(config.CONNECT_TIMEOUT)
            hello, buffer = receive_message(sock, b"", wait_on_timeout=False)
            if hello is None:
                raise ConnectionError("Handshake incompleto.")
            validate_message(hello)
            self._check_context(hello)
            peer_id = hello["sender_id"]
            if (hello["type"] != "PEER_HELLO" or peer_id not in self.peers
                    or peer_id >= self.player_id or hello["epoch"] != 0
                    or hello["payload"] != {
                        "player_id": peer_id, "initiated_by": peer_id
                    }):
                raise ValueError("Identificação do par inválida.")
            reply = make_message(
                "PEER_HELLO_OK", {}, self.player_id, 1,
                self.match_id, self.attempt_id, 0, hello["id"],
            )
            send_message(sock, reply)
            self._attach(sock, peer_id, buffer, first_id=2)
        except (OSError, ValueError) as error:
            self.events.put({"kind": "error", "peer_id": str(address),
                             "error": str(error)})
            raise

    def connect_lobby(self, host=config.LOBBY_HOST, port=config.LOBBY_PORT):
        sock = socket.create_connection((host, port), config.CONNECT_TIMEOUT)
        try:
            self._attach(sock, "lobby")
        except Exception:
            sock.close()
            raise

    def _connect_peer(self, peer_id, address):
        sock = socket.create_connection(address, config.CONNECT_TIMEOUT)
        try:
            hello = make_message(
                "PEER_HELLO",
                {"player_id": self.player_id, "initiated_by": self.player_id},
                self.player_id, 1, self.match_id, self.attempt_id, 0,
            )
            send_message(sock, hello)
            reply, buffer = receive_message(sock, b"", wait_on_timeout=False)
            if reply is None:
                raise ConnectionError("Par saiu durante o handshake.")
            validate_message(reply)
            self._check_context(reply)
            if (reply["type"] != "PEER_HELLO_OK" or reply["sender_id"] != peer_id
                    or reply["reply_to"] != 1 or reply["epoch"] != 0):
                raise ValueError("Resposta de identificação inválida.")
            self._attach(sock, peer_id, buffer, first_id=2)
        except Exception:
            sock.close()
            raise

    def connect_mesh(self, peers):
        """Chamar na preparação, com endpoints oficiais de todos os outros."""
        self.peers = dict(peers)
        for peer_id, address in self.peers.items():
            if self.player_id < peer_id:
                threading.Thread(
                    target=self._retry_peer, args=(peer_id, address), daemon=True
                ).start()

    def _retry_peer(self, peer_id, address):
        deadline = time.monotonic() + config.MESH_TIMEOUT
        while not self.stopped.is_set() and time.monotonic() < deadline:
            try:
                self._connect_peer(peer_id, address)
                return
            except (OSError, ValueError):
                self.stopped.wait(0.1)
        if not self.stopped.is_set():
            self.events.put({"kind": "error", "peer_id": peer_id,
                             "error": "Prazo de conexão esgotado."})

    def send(self, peer_id, kind, payload, reply_to=None, anonymous=False):
        if anonymous and peer_id != "lobby":
            raise ValueError("Envio anônimo somente ao lobby.")
        with self.lock:
            connection = self.connections[peer_id]
            counter = self.counters[peer_id]
        with connection.lock:
            message = make_message(
                kind, payload, None if anonymous else self.player_id,
                next(counter),
                None if peer_id == "lobby" else self.match_id,
                None if peer_id == "lobby" else self.attempt_id,
                None if peer_id == "lobby" else self.epoch, reply_to,
            )
            connection.send(message)
            return message["id"]

    def broadcast(self, kind, payload):
        with self.lock:
            peers = [peer for peer in self.connections if peer != "lobby"]
        for peer_id in peers:
            try:
                self.send(peer_id, kind, payload)
            except (OSError, KeyError) as error:
                self.events.put({"kind": "error", "peer_id": peer_id,
                                 "error": str(error)})

    def get_event(self, timeout=None):
        return self.events.get(timeout=timeout)

    def disconnect(self, peer_id):
        with self.lock:
            connection = self.connections.get(peer_id)
            self.peers.pop(peer_id, None)
        if connection is not None:
            connection.close()

    def close(self):
        self.stopped.set()
        if self.server is not None:
            self.server.close()
        with self.lock:
            connections = list(self.connections.values())
        for connection in connections:
            connection.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Teste da comunicação")
    parser.add_argument("--id", "--name", dest="id", required=True)
    parser.add_argument("--peer-port", type=int, default=config.PEER_PORT)
    parser.add_argument("--bind-host", default=config.PEER_BIND_HOST)
    parser.add_argument("--lobby-host", default=config.LOBBY_HOST)
    parser.add_argument("--lobby-port", type=int, default=config.LOBBY_PORT)
    parser.add_argument("--no-lobby", action="store_true")
    parser.add_argument("--peer", action="append", default=[], help="ID=HOST:PORT")
    args = parser.parse_args()
    peers = {}
    for value in args.peer:
        peer_id, endpoint = value.split("=", 1)
        host, port = endpoint.rsplit(":", 1)
        peers[peer_id] = (host, int(port))
    node = NodeClient(args.id, args.bind_host, args.peer_port)
    node.start()
    if not args.no_lobby:
        try:
            node.connect_lobby(args.lobby_host, args.lobby_port)
        except OSError as error:
            print("Lobby indisponível:", error)
    node.connect_mesh(peers)
    commands = queue.Queue()

    def keyboard():
        while True:
            try:
                text = input("> ")
            except (EOFError, OSError):
                text = "/quit"
            commands.put(text)
            if text == "/quit":
                return

    print("/lobby texto | /to ID texto | /all texto | /quit", flush=True)
    threading.Thread(target=keyboard, daemon=True).start()
    try:
        while True:
            try:
                print(node.get_event(timeout=0.1), flush=True)
            except queue.Empty:
                pass
            try:
                command = commands.get_nowait()
            except queue.Empty:
                continue
            if command == "/quit":
                break
            try:
                if command.startswith("/lobby "):
                    node.send("lobby", "TEXT", {"text": command[7:]})
                elif command.startswith("/to "):
                    peer_id, text = command[4:].split(" ", 1)
                    node.send(peer_id, "TEXT", {"text": text})
                elif command.startswith("/all "):
                    node.broadcast("TEXT", {"text": command[5:]})
                else:
                    print("Comando desconhecido.")
            except (OSError, ValueError, KeyError) as error:
                print("Falha no envio:", error)
    except KeyboardInterrupt:
        pass
    finally:
        node.close()


if __name__ == "__main__":
    main()
