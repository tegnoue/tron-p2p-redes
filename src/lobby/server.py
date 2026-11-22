"""Transporte do lobby. O executável responde ECHO para testar a rede."""
import argparse
import itertools
import queue

from src.core import config
from src.core.protocol import make_message
from src.core.transport import Connection, listen


def start_server():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=config.LOBBY_HOST)
    parser.add_argument("--port", type=int, default=config.LOBBY_PORT)
    args = parser.parse_args()
    events = queue.Queue()
    clients = {}
    counters = {}
    connection_ids = itertools.count(1)

    def accept(sock, address):
        client_id = next(connection_ids)
        connection = Connection(
            sock,
            lambda message: events.put(("message", client_id, message)),
            lambda error: events.put(("disconnected", client_id, error)),
        )
        events.put(("connected", client_id, connection))
        connection.start()

    server = listen(args.host, args.port, accept)
    print(f"Lobby de teste em {server.getsockname()}", flush=True)
    try:
        while True:
            kind, client_id, data = events.get()
            if kind == "connected":
                clients[client_id] = data
                counters[client_id] = itertools.count(1)
            elif kind == "disconnected":
                clients.pop(client_id, None)
                counters.pop(client_id, None)
            elif kind == "message" and client_id in clients:
                print(f"Cliente {client_id}: {data}", flush=True)
                # Trocar este tratamento pela sessão de registro/salas.
                reply = make_message(
                    "ECHO", data["payload"], "lobby",
                    next(counters[client_id]), reply_to=data["id"],
                )
                try:
                    clients[client_id].send(reply)
                except OSError:
                    pass  # a desconexão já gera seu próprio evento
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        for connection in list(clients.values()):
            connection.close()


if __name__ == "__main__":
    start_server()
