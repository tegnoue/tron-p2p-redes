"""Regras do jogo. Não usa rede: recebe o estado e as curvas de um ciclo.

O mesmo estado com as mesmas curvas produz sempre o mesmo resultado, e a
ordem dos IDs não favorece nenhum jogador.
"""
from src.game.arena import (
    DIRECTIONS, OPPOSITE, bikes_list, compute_result, inside,
)


def valid_turn(current, new):
    """Curva válida: direção conhecida, diferente da atual e não oposta."""
    return new in DIRECTIONS and new != current and new != OPPOSITE[current]


def step(state, turns):
    """Avança um ciclo. turns: {player_id: direção}. Altera state e devolve o evento.

    Todos os destinos são calculados antes de alterar a arena. Prioridade dos
    motivos: WALL, depois TRAIL, depois HEAD_ON.
    """
    if state["result"]["status"] != "ONGOING":
        raise ValueError("A partida já terminou.")
    alive = [p for p, bike in state["bikes"].items() if bike["alive"]]
    targets = {}
    for player_id in alive:
        bike = state["bikes"][player_id]
        turn = turns.get(player_id)
        if turn is not None and valid_turn(bike["direction"], turn):
            bike["direction"] = turn
        dx, dy = DIRECTIONS[bike["direction"]]
        targets[player_id] = (bike["x"] + dx, bike["y"] + dy)

    reasons = {}
    for player_id, (x, y) in targets.items():
        if not inside(state, x, y):
            reasons[player_id] = "WALL"
        elif (x, y) in state["occupied"]:
            reasons[player_id] = "TRAIL"  # inclui troca de posições
    free = [t for p, t in targets.items() if p not in reasons]
    for player_id, target in targets.items():
        if player_id not in reasons and free.count(target) > 1:
            reasons[player_id] = "HEAD_ON"

    new_cells = []
    for player_id in sorted(targets):
        x, y = targets[player_id]
        if reasons.get(player_id) == "WALL":
            continue  # mantém a última posição válida
        bike = state["bikes"][player_id]
        bike["x"], bike["y"] = x, y
        if (x, y) not in state["occupied"]:
            state["occupied"][(x, y)] = player_id  # menor ID em colisão frontal
            new_cells.append([x, y, player_id])

    eliminations = []
    for player_id in sorted(reasons):
        state["bikes"][player_id]["alive"] = False
        x, y = targets[player_id]
        eliminations.append({"player_id": player_id, "reason": reasons[player_id],
                             "attempted_x": x, "attempted_y": y})
    state["cycle"] += 1
    state["result"] = compute_result(state, alive)
    return {
        "cycle": state["cycle"], "bikes": bikes_list(state),
        "new_cells": new_cells, "eliminations": eliminations,
        "result": state["result"],
    }


def eliminate(state, player_id, reason):
    """Elimina uma moto entre ciclos (desconexão). O rastro permanece."""
    bike = state["bikes"].get(player_id)
    if bike is None or not bike["alive"] or state["result"]["status"] != "ONGOING":
        return None
    alive = [p for p, b in state["bikes"].items() if b["alive"]]
    bike["alive"] = False
    state["result"] = compute_result(state, alive)
    return {"player_id": player_id, "reason": reason,
            "attempted_x": bike["x"], "attempted_y": bike["y"]}
