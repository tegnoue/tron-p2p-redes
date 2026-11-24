"""Servidor de lobby: aceita conexões e entrega as mensagens à sessão.

Um único laço processa os eventos, então as salas não precisam de lock.
Depois do MATCH_CONFIG o lobby não participa da partida.
"""
import argparse
import itertools
import queue
import threading

from src.core import config
from src.core.protocol import make_message
from src.core.transport import Connection, listen
from src.lobby.session import DEFAULT_SETTINGS, Lobby


def run_server(host, port, settings=None, stop=None, on_ready=None):
    events = queue.Queue()
    clients = {}
    counters = {}
    lobby = Lobby(settings)
    connection_ids = itertools.count(1)
    stop = stop or threading.Event()

    def accept(sock, address):
        client_id = next(connection_ids)
        connection = Connection(
            sock,
            lambda message: events.put(("message", client_id, message)),
            lambda error: events.put(("disconnected", client_id, error)),
        )
        events.put(("connected", client_id, (connection, address[0])))
        connection.start()

    def send_all(outbox):
        for client_id, kind, payload, reply_to in outbox:
            if client_id not in clients:
                continue
            reply = make_message(kind, payload, "lobby",
                                 next(counters[client_id]), reply_to=reply_to)
            try:
                clients[client_id].send(reply)
            except OSError:
                pass  # a desconexão já gera seu próprio evento

    server = listen(host, port, accept)
    print(f"[lobby] escutando em {server.getsockname()}", flush=True)
    if on_ready:
        on_ready(server.getsockname()[1])
    try:
        while not stop.is_set():
            try:
                kind, client_id, data = events.get(timeout=0.2)
            except queue.Empty:
                continue
            if kind == "connected":
                clients[client_id], ip = data
                counters[client_id] = itertools.count(1)
                lobby.connect(client_id, ip)
                print(f"[lobby] conexão {client_id} de {ip}", flush=True)
            elif kind == "disconnected" and client_id in clients:
                del clients[client_id], counters[client_id]
                send_all(lobby.disconnect(client_id))
                print(f"[lobby] desconectou {client_id}", flush=True)
            elif kind == "message" and client_id in clients:
                send_all(lobby.handle(client_id, data))
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        for connection in list(clients.values()):
            connection.close()


def start_server():
    parser = argparse.ArgumentParser(description="Servidor de lobby do Tron P2P")
    parser.add_argument("--host", default=config.LOBBY_HOST,
                        help="endereço de escuta (0.0.0.0 para a rede)")
    parser.add_argument("--port", type=int, default=config.LOBBY_PORT)
    parser.add_argument("--width", type=int, default=DEFAULT_SETTINGS["width"])
    parser.add_argument("--height", type=int, default=DEFAULT_SETTINGS["height"])
    parser.add_argument("--tick-ms", type=int, default=DEFAULT_SETTINGS["tick_ms"],
                        help="duração de um ciclo (125 ms = 8 ciclos/s)")
    args = parser.parse_args()
    run_server(args.host, args.port, {
        "width": args.width, "height": args.height, "tick_ms": args.tick_ms,
    })


if __name__ == "__main__":
    start_server()
