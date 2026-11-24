"""Lógica do host: guarda as curvas pedidas e calcula cada ciclo com o motor.

Não usa rede. O aplicativo entrega os MOVE recebidos e envia o CYCLE devolvido.
"""
from src.game.arena import DIRECTIONS, bikes_list, create_state
from src.game.engine import eliminate, step, valid_turn

PENDING_LIMIT = 2  # curvas guardadas por jogador; uma é usada por ciclo


class Host:
    def __init__(self, config):
        self.state = create_state(config["width"], config["height"],
                                  config["spawns"])
        self.pending = {s["player_id"]: [] for s in config["spawns"]}
        self.lost = set()

    def finished(self):
        return self.state["result"]["status"] != "ONGOING"

    def receive_move(self, player_id, direction):
        """Valida a curva contra a última pendente (ou a direção atual)."""
        bike = self.state["bikes"].get(player_id)
        queue = self.pending.get(player_id)
        if bike is None or not bike["alive"] or direction not in DIRECTIONS:
            return False
        if len(queue) >= PENDING_LIMIT:
            return False
        reference = queue[-1] if queue else bike["direction"]
        if not valid_turn(reference, direction):
            return False
        queue.append(direction)
        return True

    def player_lost(self, player_id):
        """Desconexão: a moto é eliminada no início do próximo ciclo."""
        self.lost.add(player_id)

    def tick(self):
        """Produz o payload do próximo CYCLE."""
        eliminations = []
        for player_id in sorted(self.lost):
            info = eliminate(self.state, player_id, "DESCONEXAO")
            if info:
                eliminations.append(info)
        self.lost.clear()
        if self.finished():  # a desconexão encerrou a partida
            return {"cycle": self.state["cycle"], "bikes": bikes_list(self.state),
                    "new_cells": [], "eliminations": eliminations,
                    "result": self.state["result"]}
        turns = {p: q.pop(0) for p, q in self.pending.items() if q}
        event = step(self.state, turns)
        event["eliminations"] = eliminations + event["eliminations"]
        return event
