"""Representação da arena: motos, células ocupadas e resultado."""

DIRECTIONS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
OPPOSITE = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}


def spawn_points(width, height):
    """Pontos de partida fixos; com três jogadores usam-se os três primeiros."""
    return [
        (3, 3, "RIGHT"),
        (width - 4, height - 4, "LEFT"),
        (width - 4, 3, "DOWN"),
        (3, height - 4, "UP"),
    ]


def create_state(width, height, spawns):
    """spawns: lista de {player_id, x, y, direction}. A posição inicial já é rastro."""
    state = {
        "width": width, "height": height, "cycle": 0,
        "bikes": {}, "occupied": {}, "result": ongoing(),
    }
    for spawn in spawns:
        player_id = spawn["player_id"]
        state["bikes"][player_id] = {
            "x": spawn["x"], "y": spawn["y"],
            "direction": spawn["direction"], "alive": True,
        }
        state["occupied"][(spawn["x"], spawn["y"])] = player_id
    return state


def inside(state, x, y):
    return 0 <= x < state["width"] and 0 <= y < state["height"]


def ongoing():
    return {"status": "ONGOING", "winner_id": None, "finalists": []}


def compute_result(state, alive_before):
    """Um sobrevivente vence; nenhum sobrevivente é empate entre os que estavam vivos."""
    alive = sorted(p for p, bike in state["bikes"].items() if bike["alive"])
    if len(alive) == 1:
        return {"status": "WINNER", "winner_id": alive[0], "finalists": alive}
    if not alive:
        return {"status": "DRAW", "winner_id": None,
                "finalists": sorted(alive_before)}
    return ongoing()


def bikes_list(state):
    """Motos em formato de mensagem, ordenadas por ID."""
    return [
        {"player_id": p, **state["bikes"][p]} for p in sorted(state["bikes"])
    ]
