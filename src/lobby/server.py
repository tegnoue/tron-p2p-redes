"""Servidor de transporte do lobby. Salas e registro pertencem à aplicação."""
import argparse
import itertools
import queue
import threading

from src.core.config import NetworkConfig
from src.core.protocol import make_message, validate_envelope
from src.core.transport import JsonConnection, NetworkEvent, TcpListener


class LobbyServer:
    def __init__(self, config=None):
        self.config = config or NetworkConfig.from_env()
        self.events = queue.Queue()
        self._lock = threading.RLock()
        self._clients = {}
        self._ids = itertools.count(1)
        self._message_ids = {}
        self._closed = False
        self.listener = TcpListener(
            self.config.lobby_host, self.config.lobby_port, self._accept,
            lambda error: self.events.put(
                NetworkEvent("error", "listener", error=str(error))
            ),
        )

    @property
    def address(self):
        return self.listener.address

    @property
    def client_ids(self):
        with self._lock:
            return tuple(self._clients)

    def start(self):
        if self._closed:
            raise RuntimeError("Servidor já encerrado.")
        self.listener.start()

    def _accept(self, sock, address):
        client_id = f"connection-{next(self._ids)}"
        connection = JsonConnection(
            sock, client_id, self.config, self._receive, self._disconnect
        )
        with self._lock:
            if self._closed:
                connection.close()
                return
            self._clients[client_id] = connection
            self._message_ids[client_id] = itertools.count(1)
            self.events.put(NetworkEvent("connected", client_id))
        connection.start()

    def _receive(self, connection, message):
        validate_envelope(message)
        self.events.put(NetworkEvent("message", connection.peer_id, message))

    def _disconnect(self, connection, error):
        with self._lock:
            if self._clients.get(connection.peer_id) is connection:
                del self._clients[connection.peer_id]
                self._message_ids.pop(connection.peer_id, None)
        self.events.put(NetworkEvent(
            "disconnected", connection.peer_id,
            error=None if error is None else str(error),
        ))

    def send(self, client_id, message_type, payload, reply_to=None,
             match_id=None, attempt_id=None):
        with self._lock:
            connection = self._clients[client_id]
            message = make_message(
                message_type, payload, "lobby",
                next(self._message_ids[client_id]),
                match_id=match_id, attempt_id=attempt_id, reply_to=reply_to,
            )
            connection.send(message)

    def get_event(self, timeout=None):
        return self.events.get(timeout=timeout)

    def close(self):
        with self._lock:
            self._closed = True
        self.listener.close()
        with self._lock:
            connections = list(self._clients.values())
        for connection in connections:
            connection.close()
        for connection in connections:
            connection.wait_closed()


def start_server():
    parser = argparse.ArgumentParser(description="Diagnóstico do transporte do lobby")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    from dataclasses import replace
    config = NetworkConfig.from_env()
    config = replace(
        config, lobby_host=args.host or config.lobby_host,
        lobby_port=config.lobby_port if args.port is None else args.port,
    )
    server = LobbyServer(config)
    server.start()
    print(f"Lobby de diagnóstico em {server.address}. Ctrl+C encerra.")
    try:
        while True:
            event = server.get_event()
            print(event, flush=True)
            if event.kind == "message":
                # Demonstra transporte; não implementa REGISTER nem salas.
                try:
                    server.send(
                        event.peer_id, "ECHO", event.message["payload"],
                        reply_to=event.message["id"],
                    )
                except (KeyError, ConnectionError):
                    pass  # o cliente pode ter saído depois de enviar
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


if __name__ == "__main__":
    start_server()
