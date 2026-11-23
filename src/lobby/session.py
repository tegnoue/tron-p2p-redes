"""Registro, salas e início da partida. Não usa sockets: recebe mensagens já
validadas e devolve as respostas a enviar.

Baseado no servidor de lobby simples do grupo (máquina de estados por
cliente, dono da sala passado ao próximo), adaptado ao envelope do projeto.
"""
import itertools
import random
import uuid

from src.game.arena import spawn_points

MIN_PLAYERS = 3
MAX_PLAYERS = 4
DEFAULT_SETTINGS = {"width": 40, "height": 30, "tick_ms": 125}


class LobbyError(Exception):
    def __init__(self, code, text):
        super().__init__(text)
        self.code, self.text = code, text


class Lobby:
    def __init__(self, settings=None):
        self.settings = dict(DEFAULT_SETTINGS, **(settings or {}))
        self.sessions = {}   # client_id -> sessão
        self.players = {}    # player_id -> sessão (somente registrados)
        self.rooms = {}      # room_id -> sala
        self.room_ids = itertools.count(1)
        self.outbox = []     # (client_id, tipo, payload, reply_to)

    # ---------- eventos de conexão ----------

    def connect(self, client_id, ip):
        self.sessions[client_id] = {
            "client_id": client_id, "ip": ip, "player_id": None,
            "nickname": None, "endpoint": None, "room_id": None,
        }

    def disconnect(self, client_id):
        session = self.sessions.pop(client_id, None)
        if session and session["player_id"]:
            if session["room_id"]:
                self._leave(session)
            self.players.pop(session["player_id"], None)
            self._forget_started_rooms()
        return self._flush()

    def handle(self, client_id, message):
        session = self.sessions[client_id]
        handler = getattr(self, "_on_" + message["type"].lower(), None)
        try:
            if handler is None:
                raise LobbyError("INVALID_MESSAGE",
                                 "Tipo desconhecido: " + message["type"])
            registered = session["player_id"] is not None
            if message["type"] == "REGISTER" and registered:
                raise LobbyError("ALREADY_REGISTERED", "Jogador já registrado.")
            if message["type"] != "REGISTER" and not registered:
                raise LobbyError("INVALID_STATE", "Envie REGISTER primeiro.")
            if registered and message["sender_id"] != session["player_id"]:
                raise LobbyError("INVALID_SENDER", "sender_id não corresponde.")
            handler(session, message["payload"], message["id"])
        except LobbyError as error:
            self._reply(session, "ERROR", {"code": error.code,
                                           "message": error.text}, message["id"])
        return self._flush()

    # ---------- pedidos ----------

    def _on_register(self, session, payload, msg_id):
        nickname = _text(payload, "nickname", 24)
        endpoint = payload.get("peer_endpoint")
        if not isinstance(endpoint, dict) or not _valid_port(endpoint.get("port")):
            raise LobbyError("INVALID_MESSAGE", "peer_endpoint.port deve ser 1 a 65535.")
        host = endpoint.get("host")
        if host is not None and not isinstance(host, str):
            raise LobbyError("INVALID_MESSAGE", "peer_endpoint.host deve ser texto.")
        session["player_id"] = uuid.uuid4().hex[:8]
        session["nickname"] = nickname
        # Sem host informado, usa o IP visto pelo lobby.
        session["endpoint"] = {"host": host or session["ip"], "port": endpoint["port"]}
        self.players[session["player_id"]] = session
        self._reply(session, "REGISTER_OK",
                    {"player_id": session["player_id"]}, msg_id)

    def _on_list_rooms(self, session, payload, msg_id):
        rooms = [{
            "room_id": r["room_id"], "name": r["name"], "state": r["state"],
            "player_count": len(r["players"]), "max_players": MAX_PLAYERS,
        } for r in self.rooms.values()]
        self._reply(session, "LIST_ROOMS_OK", {"rooms": rooms}, msg_id)

    def _on_create_room(self, session, payload, msg_id):
        self._require_no_room(session)
        room = {
            "room_id": str(next(self.room_ids)), "room_version": 1,
            "name": _text(payload, "name", 48), "state": "AGUARDANDO",
            "creator_id": session["player_id"], "players": [_member(session)],
            "min_players": MIN_PLAYERS, "max_players": MAX_PLAYERS,
        }
        self.rooms[room["room_id"]] = room
        session["room_id"] = room["room_id"]
        self._reply(session, "CREATE_ROOM_OK", {"room": room}, msg_id)

    def _on_join_room(self, session, payload, msg_id):
        self._require_no_room(session)
        room = self.rooms.get(payload.get("room_id"))
        if room is None:
            raise LobbyError("ROOM_NOT_FOUND", "Sala não encontrada.")
        if room["state"] != "AGUARDANDO":
            raise LobbyError("ROOM_NOT_JOINABLE", "A partida dessa sala já começou.")
        if len(room["players"]) >= MAX_PLAYERS:
            raise LobbyError("ROOM_FULL", "Sala cheia.")
        room["players"].append(_member(session))
        room["room_version"] += 1
        session["room_id"] = room["room_id"]
        self._reply(session, "JOIN_ROOM_OK", {"room": room}, msg_id)
        self._notify_room(room, skip=session["player_id"])

    def _on_leave_room(self, session, payload, msg_id):
        if not session["room_id"]:
            raise LobbyError("INVALID_STATE", "Você não está em uma sala.")
        self._leave(session)
        self._reply(session, "LEAVE_ROOM_OK", {}, msg_id)

    def _on_start_match(self, session, payload, msg_id):
        room = self.rooms.get(session["room_id"])
        if room is None:
            raise LobbyError("INVALID_STATE", "Você não está em uma sala.")
        if room["creator_id"] != session["player_id"]:
            raise LobbyError("NOT_ROOM_CREATOR", "Só o criador da sala pode iniciar.")
        if not MIN_PLAYERS <= len(room["players"]) <= MAX_PLAYERS:
            raise LobbyError("NOT_ENOUGH_PLAYERS",
                             "São necessários três ou quatro participantes.")
        config = self._match_config(room)
        room["state"] = "EM_PARTIDA"
        room["room_version"] += 1
        self._reply(session, "START_MATCH_OK", {
            "match_id": config["match_id"], "attempt_id": config["attempt_id"],
        }, msg_id)
        for member in room["players"]:
            player = self.players[member["player_id"]]
            player["room_id"] = None  # libera o jogador para outra sala depois
            self._send(player, "MATCH_CONFIG", {"config": config})
        print(f"[lobby] partida iniciada na sala {room['room_id']}", flush=True)

    # ---------- auxiliares ----------

    def _match_config(self, room):
        width, height = self.settings["width"], self.settings["height"]
        order = list(room["players"])
        random.shuffle(order)  # sorteio dos pontos de partida
        spawns = [
            {"player_id": m["player_id"], "x": x, "y": y, "direction": d}
            for m, (x, y, d) in zip(order, spawn_points(width, height))
        ]
        return {
            "match_id": uuid.uuid4().hex[:12], "attempt_id": uuid.uuid4().hex[:12],
            "host_id": room["creator_id"], "members": list(room["players"]),
            "width": width, "height": height,
            "tick_ms": self.settings["tick_ms"], "spawns": spawns,
        }

    def _require_no_room(self, session):
        if session["room_id"]:
            raise LobbyError("ALREADY_IN_ROOM", "Saia da sala atual primeiro.")

    def _leave(self, session):
        room = self.rooms.get(session["room_id"])
        session["room_id"] = None
        if room is None:
            return
        room["players"] = [m for m in room["players"]
                           if m["player_id"] != session["player_id"]]
        if not room["players"]:
            del self.rooms[room["room_id"]]  # sala vazia some
            return
        if room["creator_id"] == session["player_id"]:
            room["creator_id"] = room["players"][0]["player_id"]  # mais antigo
        room["room_version"] += 1
        self._notify_room(room)

    def _forget_started_rooms(self):
        """Remove salas em partida quando nenhum integrante segue no lobby."""
        for room_id, room in list(self.rooms.items()):
            if room["state"] == "EM_PARTIDA" and not any(
                    m["player_id"] in self.players for m in room["players"]):
                del self.rooms[room_id]

    def _notify_room(self, room, skip=None):
        for member in room["players"]:
            if member["player_id"] != skip:
                self._send(self.players[member["player_id"]],
                           "ROOM_UPDATED", {"room": room})

    def _reply(self, session, kind, payload, reply_to):
        self.outbox.append((session["client_id"], kind, payload, reply_to))

    def _send(self, session, kind, payload):
        self.outbox.append((session["client_id"], kind, payload, None))

    def _flush(self):
        outbox, self.outbox = self.outbox, []
        return outbox


def _member(session):
    return {"player_id": session["player_id"], "nickname": session["nickname"],
            "endpoint": dict(session["endpoint"])}


def _text(payload, field, limit):
    value = payload.get(field)
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
        raise LobbyError("INVALID_MESSAGE",
                         f"Campo '{field}' deve ter de 1 a {limit} caracteres.")
    return value.strip()


def _valid_port(port):
    return type(port) is int and 1 <= port <= 65535
