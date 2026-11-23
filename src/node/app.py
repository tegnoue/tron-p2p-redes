"""Aplicativo do jogador: lobby, preparação da malha P2P e partida.

Um único laço (run) é dono de todo o estado. As threads de rede (NodeClient)
e de teclado só entregam eventos por filas.

Fases: LOBBY -> PREPARANDO -> CONTAGEM -> JOGANDO -> RESULTADO -> LOBBY | FIM
"""
import argparse
import os
import queue
import time

from src.core import config
from src.game.arena import DIRECTIONS
from src.node import ui
from src.node.client import NodeClient
from src.node.host import Host
from src.node.state import MatchView

HEARTBEAT_S = 1.0         # intervalo entre HEARTBEAT
PEER_TIMEOUT_S = 3.0      # silêncio que indica falha de um par
PREPARE_TIMEOUT_S = 20.0  # prazo para todos ficarem prontos
COUNTDOWN_MS = 3000
IN_MATCH = ("PREPARANDO", "CONTAGEM", "JOGANDO")


class App:
    def __init__(self, nickname, node, keys, advertise_host=None, render=True):
        self.nickname = nickname
        self.node = node
        self.keys = keys
        self.advertise_host = advertise_host
        self.render = render
        self.phase = "LOBBY"
        self.registered = False
        self.lobby_ok = False
        self.room = None
        self.log = []
        self.line = ""        # linha sendo digitada no lobby
        self.dirty = True     # tela precisa ser redesenhada
        self._reset_match()

    def _reset_match(self):
        self.config = self.view = self.host = self.host_id = None
        self.others = []
        self.ready, self.gone, self.last_seen = set(), set(), {}
        self.deadline = self.countdown_end = self.next_tick = None
        self.next_heartbeat = 0.0
        self.shown_second = None
        self.abort_reason = None

    # ---------- início e laço principal ----------

    def connect(self, lobby_host, lobby_port):
        self.node.start()
        self.node.connect_lobby(lobby_host, lobby_port)
        self.lobby_ok = True
        port = self.node.server.getsockname()[1]
        self._send("lobby", "REGISTER", {
            "nickname": self.nickname,
            "peer_endpoint": {"host": self.advertise_host, "port": port},
        }, anonymous=True)
        self._log("Conectado ao lobby. Registrando...")

    def run(self):
        while self.phase != "FIM":
            self._drain_events()
            self._drain_keys()
            self._timers()
            if self.render and self.dirty:
                ui.draw(self._screen())
                self.dirty = False
        self.node.close()

    def _drain_events(self):
        timeout = 0.01
        while True:
            try:
                event = self.node.get_event(timeout=timeout)
            except queue.Empty:
                return
            timeout = 0
            self._on_event(event)

    def _on_event(self, event):
        kind, peer = event["kind"], event["peer_id"]
        if kind == "message" and peer == "lobby":
            self._on_lobby(event["message"])
        elif kind == "message":
            self.last_seen[peer] = time.monotonic()
            self._on_peer(peer, event["message"])
        elif kind == "connected" and peer != "lobby":
            self._log(f"Conectado a {self._name(peer)}.")
            if self.phase == "PREPARANDO" and peer == self.host_id:
                self._send(peer, "READY", {})
        elif kind == "disconnected":
            self._on_disconnect(peer)
        elif kind == "error" and peer in self.others and peer not in self.gone \
                and self.phase in IN_MATCH:
            self._log(f"Erro com {self._name(peer)}: {event['error']}")
            if self.phase == "PREPARANDO" and (self.host or peer == self.host_id):
                self._abort(f"Não foi possível conectar a {self._name(peer)}.")

    # ---------- mensagens do lobby ----------

    def _on_lobby(self, message):
        kind, payload = message["type"], message["payload"]
        if kind == "REGISTER_OK":
            self.node.player_id = payload["player_id"]
            self.registered = True
            self._log(f"Registrado como {self.nickname}. Digite 'listar' ou 'criar NOME'.")
        elif kind == "LIST_ROOMS_OK":
            self._log("Salas:" if payload["rooms"] else "Nenhuma sala criada.")
            for r in payload["rooms"]:
                self._log(f"  {r['room_id']}: '{r['name']}' "
                          f"{r['player_count']}/{r['max_players']} {r['state']}")
        elif kind in ("CREATE_ROOM_OK", "JOIN_ROOM_OK"):
            self.room = payload["room"]
            self._log(f"Você entrou na sala {self.room['room_id']}. "
                      "O criador digita 'iniciar' com 3 ou 4 jogadores.")
        elif kind == "ROOM_UPDATED":
            if self.room and self.room["room_id"] == payload["room"]["room_id"]:
                self.room = payload["room"]
                self.dirty = True
        elif kind == "LEAVE_ROOM_OK":
            self.room = None
            self._log("Você saiu da sala.")
        elif kind == "START_MATCH_OK":
            self._log("Partida iniciada pelo lobby.")
        elif kind == "MATCH_CONFIG":
            self._start_match(payload["config"])
        elif kind == "ERROR":
            self._log("Lobby: " + payload.get("message", payload.get("code", "")))

    def _start_match(self, match_config):
        self._reset_match()
        self.log = []  # o painel da partida mostra só eventos da partida
        me = self.node.player_id
        self.config, self.room = match_config, None
        self.host_id = match_config["host_id"]
        self.view = MatchView(match_config, me)
        self.host = Host(match_config) if me == self.host_id else None
        self.others = [m["player_id"] for m in match_config["members"]
                       if m["player_id"] != me]
        self.node.match_id = match_config["match_id"]
        self.node.attempt_id = match_config["attempt_id"]
        now = time.monotonic()
        self.deadline = now + PREPARE_TIMEOUT_S
        self.last_seen = {p: now for p in self.others}
        self.phase = "PREPARANDO"
        self._log(f"Partida configurada. Host: {self._name(self.host_id)}.")
        self.node.connect_mesh({
            m["player_id"]: (m["endpoint"]["host"], m["endpoint"]["port"])
            for m in match_config["members"] if m["player_id"] != me
        })

    # ---------- mensagens entre jogadores ----------

    def _on_peer(self, peer, message):
        kind, payload = message["type"], message["payload"]
        if kind == "HEARTBEAT" or self.phase not in IN_MATCH:
            return  # mensagens atrasadas após o fim são ignoradas
        if kind == "ERROR":
            self._log(f"{self._name(peer)} informou erro: {payload.get('message')}")
        elif self.host is None and peer == self.host_id:
            self._from_host(kind, payload)
        elif self.host is not None:
            self._to_host(peer, kind, payload)
        else:
            self._error(peer, "INVALID_SENDER", f"{kind} só pode vir do host.")

    def _from_host(self, kind, payload):
        if kind == "COUNTDOWN" and self.phase == "PREPARANDO":
            self.phase = "CONTAGEM"
            self.countdown_end = time.monotonic() + payload["duration_ms"] / 1000
            self._log("Contagem iniciada!")
        elif kind == "CYCLE" and self.phase in ("CONTAGEM", "JOGANDO"):
            self.phase = "JOGANDO"
            self._apply_cycle(payload)
        elif kind == "MATCH_OVER":
            self.view.result = payload["result"]
            self._finish(None)
        elif kind == "ABORT":
            self._finish("Cancelada pelo host: " + payload.get("reason", ""))
        else:
            self._error(self.host_id, "INVALID_STATE",
                        f"{kind} inesperado na fase {self.phase}.")

    def _to_host(self, peer, kind, payload):
        if kind == "READY" and self.phase == "PREPARANDO":
            self.ready.add(peer)
            self.dirty = True
            if self.ready >= set(self.others):
                self._start_countdown()
        elif kind == "MOVE" and self.phase in ("CONTAGEM", "JOGANDO"):
            if payload.get("direction") not in DIRECTIONS:
                self._error(peer, "INVALID_MESSAGE", "direction deve ser UP, DOWN, LEFT ou RIGHT.")
            else:
                self.host.receive_move(peer, payload["direction"])
        else:
            self._error(peer, "INVALID_STATE", f"{kind} inesperado na fase {self.phase}.")

    def _start_countdown(self):
        now = time.monotonic()
        self.node.broadcast("COUNTDOWN", {"duration_ms": COUNTDOWN_MS})
        self.phase = "CONTAGEM"
        self.countdown_end = self.next_tick = now + COUNTDOWN_MS / 1000
        self.last_seen = {p: now for p in self.others}
        self._log("Todos prontos. Contagem iniciada!")

    def _apply_cycle(self, payload):
        for item in self.view.apply_cycle(payload):
            reason = ui.REASONS.get(item["reason"], item["reason"])
            self._log(f"Ciclo {payload['cycle']}: {self._name(item['player_id'])} "
                      f"eliminado ({reason}).")
        self.dirty = True

    # ---------- falhas ----------

    def _on_disconnect(self, peer):
        if peer == "lobby":
            self.lobby_ok = self.registered = False
            extra = " A partida continua." if self.phase in IN_MATCH else ""
            self._log("Conexão com o lobby perdida." + extra)
            return
        if self.phase not in IN_MATCH or peer in self.gone:
            return
        self.gone.add(peer)
        name = self._name(peer)
        if self.host is not None and self.phase == "PREPARANDO":
            self._abort(f"{name} desconectou antes do início.")
        elif self.host is not None:
            self.host.player_lost(peer)
            self._log(f"{name} desconectou: sua moto será eliminada.")
        elif peer == self.host_id:
            self._finish(f"O host ({name}) caiu. Partida encerrada para todos.")
        else:
            self._log(f"{name} desconectou.")

    def _abort(self, reason):
        """Somente o host: cancela a partida para todos."""
        if self.host is not None:
            self.node.broadcast("ABORT", {"reason": reason})
        self._finish(reason)

    def _finish(self, abort_reason):
        self.phase = "RESULTADO"
        self.abort_reason = abort_reason
        self._log(abort_reason or "Fim da partida.")

    # ---------- temporizadores ----------

    def _timers(self):
        now = time.monotonic()
        if self.phase not in IN_MATCH:
            return
        if now >= self.next_heartbeat:
            self.node.broadcast("HEARTBEAT", {})
            self.next_heartbeat = now + HEARTBEAT_S
        if self.phase == "PREPARANDO" and now > self.deadline:
            if self.host is not None:
                self._abort("Tempo de preparação esgotado.")
            else:
                self._finish("O host não iniciou a partida a tempo.")
            return
        if self.phase in ("CONTAGEM", "JOGANDO"):
            watched = ([p for p in self.others if p not in self.gone]
                       if self.host is not None else [self.host_id])
            for peer in watched:
                if now - self.last_seen.get(peer, now) > PEER_TIMEOUT_S:
                    self._log(f"{self._name(peer)} sem responder há "
                              f"{PEER_TIMEOUT_S:.0f} s.")
                    self.node.disconnect(peer)
                    self._on_disconnect(peer)
        if self.phase == "CONTAGEM":
            second = max(0, int(self.countdown_end - now) + 1)
            if second != self.shown_second:
                self.shown_second, self.dirty = second, True
        if self.host is not None and self.phase in ("CONTAGEM", "JOGANDO") \
                and now >= self.next_tick:
            self._host_tick(now)

    def _host_tick(self, now):
        self.phase = "JOGANDO"
        payload = self.host.tick()
        self.node.broadcast("CYCLE", payload)
        self._apply_cycle(payload)
        tick = self.config["tick_ms"] / 1000
        self.next_tick += tick
        if self.next_tick < now:
            self.next_tick = now + tick  # atrasou: não acelera para compensar
        if self.host.finished():
            self.node.broadcast("MATCH_OVER", {"result": self.view.result})
            self._finish(None)

    # ---------- teclado ----------

    def _drain_keys(self):
        while True:
            try:
                key = self.keys.get_nowait()
            except queue.Empty:
                return
            self.dirty = True
            if key in ("\x03", "\x04"):  # Ctrl+C no Windows / fim da entrada
                self.phase = "FIM"
            elif self.phase == "LOBBY":
                self._lobby_key(key)
            elif key.lower() == "q":
                self.phase = "FIM"
            elif self.phase == "RESULTADO" and key in ("\r", "\n"):
                self._back_to_lobby()
            elif key.lower() in ui.KEY_DIRECTIONS and self.phase in ("CONTAGEM", "JOGANDO"):
                self._move(ui.KEY_DIRECTIONS[key.lower()])

    def _move(self, direction):
        if not self.view.my_bike_alive():
            return
        if self.host is not None:
            self.host.receive_move(self.node.player_id, direction)
        else:
            self._send(self.host_id, "MOVE", {"direction": direction})

    def _lobby_key(self, key):
        if key in ("\r", "\n"):
            text, self.line = self.line.strip(), ""
            if text:
                self._log("> " + text)
                self._command(text)
        elif key in ("\x7f", "\x08"):
            self.line = self.line[:-1]
        elif key.isprintable():
            self.line += key

    def _command(self, text):
        parts = text.split(maxsplit=1)
        cmd, arg = parts[0].lower(), (parts[1] if len(parts) > 1 else "")
        if cmd == "fim":
            self.phase = "FIM"
        elif not self.lobby_ok:
            self._log("Sem conexão com o lobby. Digite 'fim' para sair.")
        elif not self.registered:
            self._log("Aguardando o registro no lobby...")
        elif cmd == "listar":
            self._send("lobby", "LIST_ROOMS", {})
        elif cmd == "criar" and arg:
            self._send("lobby", "CREATE_ROOM", {"name": arg})
        elif cmd == "entrar" and arg:
            self._send("lobby", "JOIN_ROOM", {"room_id": arg})
        elif cmd == "sair":
            self._send("lobby", "LEAVE_ROOM", {})
        elif cmd == "iniciar":
            self._send("lobby", "START_MATCH", {})
        else:
            self._log("Comando inválido. Use: listar | criar NOME | entrar ID | "
                      "sair | iniciar | fim")

    def _back_to_lobby(self):
        for peer in self.others:
            self.node.disconnect(peer)
        self._reset_match()
        self.phase = "LOBBY"
        self._log("De volta ao lobby." if self.lobby_ok else
                  "O lobby está indisponível. Digite 'fim' para sair.")

    # ---------- auxiliares ----------

    def _send(self, peer, kind, payload, anonymous=False):
        try:
            self.node.send(peer, kind, payload, anonymous=anonymous)
            return True
        except (OSError, KeyError) as error:
            self._log(f"Falha ao enviar {kind}: {error}")
            return False

    def _error(self, peer, code, text):
        self._send(peer, "ERROR", {"code": code, "message": text})

    def _name(self, player_id):
        if self.view and player_id in self.view.nicknames:
            return self.view.nicknames[player_id]
        return str(player_id)

    def _log(self, text):
        self.log = self.log[-100:] + [text]
        self.dirty = True

    def _screen(self):
        if self.phase in ("LOBBY", "FIM"):
            return ui.lobby_screen(self.nickname, self.room, self.log, self.line)
        if self.phase == "PREPARANDO":
            info = ([f"Prontos: {len(self.ready)}/{len(self.others)}"]
                    if self.host else ["Conectando aos jogadores..."])
        elif self.phase == "CONTAGEM":
            info = [f"Começa em {self.shown_second} s — prepare a primeira curva!"]
        elif self.phase == "JOGANDO":
            info = (["Em jogo!"] if self.view.my_bike_alive()
                    else ["Você foi eliminado. Assistindo..."])
        else:
            info = ui.result_lines(self.view, self.node.player_id, self.abort_reason)
        return ui.match_screen(self.view, self.phase, info, self.log)


def main():
    parser = argparse.ArgumentParser(description="Jogador do Tron P2P")
    parser.add_argument("--name", "--nome", dest="name", required=True,
                        help="apelido exibido no jogo")
    parser.add_argument("--peer-port", type=int, default=config.PEER_PORT,
                        help="porta onde este jogador ouve os outros")
    parser.add_argument("--bind-host", default=config.PEER_BIND_HOST)
    parser.add_argument("--advertise-host", default=os.getenv("PEER_ADVERTISE_HOST"),
                        help="IP anunciado aos outros (padrão: IP visto pelo lobby)")
    parser.add_argument("--lobby-host", default=config.LOBBY_HOST)
    parser.add_argument("--lobby-port", type=int, default=config.LOBBY_PORT)
    args = parser.parse_args()

    node = NodeClient("anonimo", args.bind_host, args.peer_port)
    keyboard = ui.Keyboard()
    app = App(args.name, node, keyboard.keys, args.advertise_host)
    try:
        app.connect(args.lobby_host, args.lobby_port)
    except OSError as error:
        print("Não foi possível iniciar (lobby fora do ar ou porta em uso?):", error)
        node.close()
        return
    keyboard.start()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        keyboard.stop()
        node.close()


if __name__ == "__main__":
    main()
