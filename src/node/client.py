"""Rede do jogador: lobby, escuta P2P e malha. Não calcula o jogo."""
import itertools
import queue
import socket
import threading
import time

from src.core.config import NetworkConfig
from src.core.exceptions import ConnectionClosedError, ProtocolError
from src.core.protocol import (
    MessageReader, make_message, send_message, validate_envelope,
)
from src.core.transport import JsonConnection, NetworkEvent, TcpListener


class NodeClient:
    def __init__(self, player_id, config=None, peers=None,
                 match_id="demo", attempt_id="demo"):
        if not isinstance(player_id, str) or not 1 <= len(player_id) <= 64:
            raise ValueError("player_id inválido.")
        if player_id == "lobby":
            raise ValueError("ID reservado.")
        self.player_id = player_id
        self.config = config or NetworkConfig.from_env()
        self.match_id, self.attempt_id = match_id, attempt_id
        self.epoch = 0
        self.events = queue.Queue()
        self._lock = threading.RLock()
        self._connections = {}
        self._counters = {}
        self._peers = dict(peers or {})
        self._stop = threading.Event()
        self._connectors = []
        self.listener = TcpListener(
            self.config.peer_bind_host, self.config.peer_port,
            self._accept_peer,
            lambda error: self.events.put(
                NetworkEvent("error", "listener", error=str(error))
            ),
        )

    @property
    def address(self):
        return self.listener.address

    @property
    def advertised_endpoint(self):
        return {
            "host": self.config.peer_advertise_host,
            "port": self.address[1],
        }

    def set_player_id(self, player_id):
        if not isinstance(player_id, str) or not 1 <= len(player_id) <= 64:
            raise ValueError("player_id inválido.")
        if player_id == "lobby":
            raise ValueError("ID reservado.")
        with self._lock:
            if any(peer != "lobby" for peer in self._connections):
                raise RuntimeError("Não alterar identidade com pares conectados.")
            self.player_id = player_id

    def last_received_at(self, peer_id):
        with self._lock:
            return self._connections[peer_id].last_received_at

    @property
    def connected_ids(self):
        with self._lock:
            return tuple(self._connections)

    def set_peers(self, peers):
        """Roster de endpoints; não é configuração de votantes."""
        with self._lock:
            if any(peer != "lobby" for peer in self._connections):
                raise RuntimeError("Atualizar endpoints antes de conectar a malha.")
            self._peers = dict(peers)

    def start(self):
        if self._stop.is_set():
            raise RuntimeError("Aplicativo já encerrado.")
        self.listener.start()

    def _adopt(self, sock, peer_id, reader=None, next_id=1):
        connection = JsonConnection(
            sock, peer_id, self.config, self._receive, self._disconnect, reader
        )
        with self._lock:
            if self._stop.is_set():
                sock.close()
                raise ConnectionClosedError("Aplicativo encerrado.")
            previous = self._connections.get(peer_id)
            if previous is not None and not previous.closed:
                sock.close()
                raise ProtocolError(f"Conexão duplicada: {peer_id}")
            self._connections[peer_id] = connection
            self._counters[peer_id] = itertools.count(next_id)
            self.events.put(NetworkEvent("connected", peer_id))
        connection.start()
        return connection

    def _check_context(self, message):
        if (message["match_id"], message["attempt_id"]) != (
            self.match_id, self.attempt_id
        ):
            raise ProtocolError("Partida ou tentativa incorreta.")

    def _accept_peer(self, sock, address):
        sock.settimeout(self.config.connect_timeout)
        reader = MessageReader(sock, self.config.max_message_bytes)
        hello = reader.receive()
        if hello is None:
            raise ProtocolError("Conexão fechada antes de PEER_HELLO.")
        validate_envelope(hello)
        self._check_context(hello)
        peer_id = hello["sender_id"]
        with self._lock:
            known_peer = peer_id in self._peers
        if not known_peer or peer_id >= self.player_id:
            raise ProtocolError("Par desconhecido ou iniciador incorreto.")
        if (
            hello["type"] != "PEER_HELLO" or hello["epoch"] != 0
            or hello["payload"] != {
                "player_id": peer_id, "initiated_by": peer_id
            }
        ):
            raise ProtocolError("PEER_HELLO inválido.")
        response = make_message(
            "PEER_HELLO_OK", {}, self.player_id, 1,
            self.match_id, self.attempt_id, 0, reply_to=hello["id"],
        )
        send_message(sock, response, self.config.max_message_bytes)
        self._adopt(sock, peer_id, reader, next_id=2)

    def connect_peer(self, peer_id):
        """Conexão/handshake síncronos, usados na preparação."""
        with self._lock:
            if peer_id in self._connections:
                return
            if peer_id not in self._peers or self.player_id >= peer_id:
                raise ValueError("Somente o menor ID inicia a conexão.")
            address = self._peers[peer_id]
        sock = socket.create_connection(address, self.config.connect_timeout)
        try:
            sock.settimeout(self.config.connect_timeout)
            hello = make_message(
                "PEER_HELLO",
                {"player_id": self.player_id, "initiated_by": self.player_id},
                self.player_id, 1, self.match_id, self.attempt_id, 0,
            )
            send_message(sock, hello, self.config.max_message_bytes)
            reader = MessageReader(sock, self.config.max_message_bytes)
            response = reader.receive()
            if response is None:
                raise ProtocolError("Par encerrou durante handshake.")
            validate_envelope(response)
            self._check_context(response)
            if (
                response["type"] != "PEER_HELLO_OK"
                or response["sender_id"] != peer_id
                or response["reply_to"] != 1
                or response["epoch"] != 0
                or response["payload"] != {}
            ):
                raise ProtocolError("Resposta de handshake inválida.")
            self._adopt(sock, peer_id, reader, next_id=2)
        except Exception:
            sock.close()
            raise

    def connect_mesh(self):
        """Inicia as tentativas em segundo plano; todos devem escutar antes."""
        with self._lock:
            targets = [peer for peer in self._peers if self.player_id < peer]
        for peer_id in targets:
            thread = threading.Thread(
                target=self._retry_peer, args=(peer_id,), daemon=True
            )
            self._connectors.append(thread)
            thread.start()

    def _retry_peer(self, peer_id):
        deadline = time.monotonic() + self.config.mesh_timeout
        last_error = None
        while not self._stop.is_set() and time.monotonic() < deadline:
            try:
                self.connect_peer(peer_id)
                return
            except (OSError, ValueError) as error:
                last_error = error
                self._stop.wait(0.1)
        if not self._stop.is_set():
            self.events.put(NetworkEvent("error", peer_id, error=str(last_error)))

    def connect_lobby(self):
        with self._lock:
            if "lobby" in self._connections:
                return
        sock = socket.create_connection(
            (self.config.lobby_host, self.config.lobby_port),
            self.config.connect_timeout,
        )
        try:
            self._adopt(sock, "lobby")
        except Exception:
            sock.close()
            raise

    def _receive(self, connection, message):
        validate_envelope(message)
        if message["sender_id"] != connection.peer_id:
            raise ProtocolError("Identidade não corresponde à conexão.")
        if connection.peer_id != "lobby":
            self._check_context(message)
        self.events.put(NetworkEvent("message", connection.peer_id, message))

    def _disconnect(self, connection, error):
        with self._lock:
            if self._connections.get(connection.peer_id) is connection:
                del self._connections[connection.peer_id]
                self._counters.pop(connection.peer_id, None)
        self.events.put(NetworkEvent(
            "disconnected", connection.peer_id,
            error=None if error is None else str(error),
        ))

    def send(self, peer_id, message_type, payload, reply_to=None, anonymous=False):
        with self._lock:
            connection = self._connections.get(peer_id)
            if connection is None:
                raise ConnectionClosedError(f"Par não conectado: {peer_id}")
            is_lobby = peer_id == "lobby"
            if anonymous and not is_lobby:
                raise ValueError("Envio anônimo é exclusivo do registro no lobby.")
            message = make_message(
                message_type, payload, None if anonymous else self.player_id,
                next(self._counters[peer_id]),
                None if is_lobby else self.match_id,
                None if is_lobby else self.attempt_id,
                None if is_lobby else self.epoch,
                reply_to=reply_to,
            )
            connection.send(message)
            return message["id"]

    def broadcast(self, message_type, payload):
        failures = {}
        with self._lock:
            peers = [peer for peer in self._connections if peer != "lobby"]
        for peer in peers:
            try:
                self.send(peer, message_type, payload)
            except (OSError, ValueError) as error:
                failures[peer] = str(error)
        return failures

    def disconnect(self, peer_id, forget=False):
        """A sessão decide quando remover; transporte não altera votantes."""
        with self._lock:
            connection = self._connections.get(peer_id)
            if forget:
                self._peers.pop(peer_id, None)
        if connection is not None:
            connection.close()
            connection.wait_closed()

    def get_event(self, timeout=None):
        return self.events.get(timeout=timeout)

    def flush(self, timeout=2.0):
        with self._lock:
            connections = list(self._connections.values())
        results = [connection.flush(timeout) for connection in connections]
        return all(results)

    def close(self):
        self._stop.set()
        self.listener.close()
        with self._lock:
            connections = list(self._connections.values())
        for connection in connections:
            connection.close()
        for connection in connections:
            connection.wait_closed()
        for thread in self._connectors:
            thread.join(self.config.connect_timeout + 0.5)


def main():
    import argparse
    import uuid
    from dataclasses import replace

    parser = argparse.ArgumentParser(description="Diagnóstico da comunicação")
    parser.add_argument("--id", default=uuid.uuid4().hex)
    parser.add_argument("--lobby-host")
    parser.add_argument("--lobby-port", type=int)
    parser.add_argument("--peer-port", type=int)
    parser.add_argument("--bind-host")
    parser.add_argument("--no-lobby", action="store_true")
    parser.add_argument("--peer", action="append", default=[],
                        help="ID=HOST:PORT; repetir para cada adversário")
    args = parser.parse_args()
    config = NetworkConfig.from_env()
    config = replace(
        config, lobby_host=args.lobby_host or config.lobby_host,
        lobby_port=config.lobby_port if args.lobby_port is None else args.lobby_port,
        peer_bind_host=args.bind_host or config.peer_bind_host,
        peer_port=config.peer_port if args.peer_port is None else args.peer_port,
    )
    peers = {}
    for item in args.peer:
        peer_id, endpoint = item.split("=", 1)
        host, port = endpoint.rsplit(":", 1)
        peers[peer_id] = (host, int(port))
    node = NodeClient(args.id, config, peers)
    node.start()
    print(f"Jogador {args.id}, escuta {node.address}")
    print("/lobby texto | /to ID texto | /all texto | /quit")
    if not args.no_lobby:
        try:
            node.connect_lobby()
        except OSError as error:
            print(f"Não foi possível conectar ao lobby: {error}")
    node.connect_mesh()
    commands = queue.Queue()

    def read_keyboard():
        while True:
            try:
                line = input("> ")
            except (EOFError, OSError):
                commands.put("/quit")
                return
            commands.put(line)
            if line == "/quit":
                return

    threading.Thread(target=read_keyboard, daemon=True).start()
    try:
        running = True
        while running:
            try:
                event = node.get_event(timeout=0.1)
                print(event, flush=True)
            except queue.Empty:
                pass
            try:
                line = commands.get_nowait()
            except queue.Empty:
                continue
            if line == "/quit":
                running = False
                continue
            try:
                if line.startswith("/lobby "):
                    node.send("lobby", "TEXT", {"text": line[7:]})
                elif line.startswith("/to "):
                    peer, text = line[4:].split(" ", 1)
                    node.send(peer, "TEXT", {"text": text})
                elif line.startswith("/all "):
                    failures = node.broadcast("TEXT", {"text": line[5:]})
                    if failures:
                        print("Falhas de envio:", failures)
                else:
                    print("Comando desconhecido.")
            except (OSError, ValueError) as error:
                print(f"Falha no comando: {error}")
    except KeyboardInterrupt:
        pass
    finally:
        node.flush()
        node.close()


if __name__ == "__main__":
    main()
