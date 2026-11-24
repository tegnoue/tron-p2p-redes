"""
Cliente de teste do lobby (só para testar, não é o jogo).

Como rodar (um terminal por jogador, na raiz do projeto):
    python -m scripts.cliente_teste --host 127.0.0.1 --port 5000

Comandos:
    registrar NOME PORTA     ex.: registrar ana 6001
    criar SALA               ex.: criar sala1
    listar
    entrar ID_DA_SALA        ex.: entrar 1
    sair
    iniciar
    cru TEXTO                envia TEXTO sem tratar (para testar mensagens inválidas)
    fim
"""
import argparse
import json
import itertools
import socket
import threading

from src.core.protocol import make_message, send_message


def ouvir(sock, estado):
    """Fica imprimindo tudo que o lobby manda e guarda o player_id recebido."""
    for linha in sock.makefile("r", encoding="utf-8"):
        print("<<", linha.strip())
        try:
            msg = json.loads(linha)
            if msg.get("type") == "REGISTER_OK":
                estado["id"] = msg["payload"]["player_id"]
        except (ValueError, KeyError, AttributeError):
            pass
    print("<< (conexão com o lobby fechada)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()

    sock = socket.create_connection((args.host, args.port))
    estado = {"id": None}  # player_id recebido em REGISTER_OK
    threading.Thread(target=ouvir, args=(sock, estado), daemon=True).start()
    ids = itertools.count(1)

    def enviar(tipo, payload):
        send_message(sock, make_message(tipo, payload, estado["id"], next(ids)))

    while True:
        try:
            partes = input().split(maxsplit=2)
        except EOFError:
            break
        if not partes:
            continue
        cmd = partes[0]
        if cmd == "registrar" and len(partes) == 3:
            enviar("REGISTER", {"nickname": partes[1],
                                "peer_endpoint": {"host": None, "port": int(partes[2])}})
        elif cmd == "criar" and len(partes) >= 2:
            enviar("CREATE_ROOM", {"name": partes[1]})
        elif cmd == "listar":
            enviar("LIST_ROOMS", {})
        elif cmd == "entrar" and len(partes) >= 2:
            enviar("JOIN_ROOM", {"room_id": partes[1]})
        elif cmd == "sair":
            enviar("LEAVE_ROOM", {})
        elif cmd == "iniciar":
            enviar("START_MATCH", {})
        elif cmd == "cru":
            sock.sendall((" ".join(partes[1:]) + "\n").encode("utf-8"))
        elif cmd == "fim":
            break
        else:
            print("comando inválido")
    sock.close()


if __name__ == "__main__":
    main()
