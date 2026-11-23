"""Estado da partida visto por um jogador, montado a partir dos CYCLE do host.

Todos (inclusive o host) desenham a partir desta cópia, então todos mostram
exatamente as mesmas decisões.
"""
from src.game.arena import ongoing

LETTERS = "ABCD"


class MatchView:
    def __init__(self, config, my_id):
        self.config = config
        self.my_id = my_id
        self.host_id = config["host_id"]
        self.width, self.height = config["width"], config["height"]
        self.order = [m["player_id"] for m in config["members"]]
        self.nicknames = {m["player_id"]: m["nickname"] for m in config["members"]}
        self.cycle = 0
        self.result = ongoing()
        self.reasons = {}  # player_id -> motivo da eliminação
        self.bikes = {}
        self.cells = {}    # (x, y) -> player_id
        for spawn in config["spawns"]:
            self.bikes[spawn["player_id"]] = {
                "x": spawn["x"], "y": spawn["y"],
                "direction": spawn["direction"], "alive": True,
            }
            self.cells[(spawn["x"], spawn["y"])] = spawn["player_id"]

    def letter(self, player_id):
        return LETTERS[self.order.index(player_id)]

    def apply_cycle(self, payload):
        if payload["cycle"] < self.cycle:
            return []  # ciclo antigo: não volta o estado
        self.cycle = payload["cycle"]
        for bike in payload["bikes"]:
            self.bikes[bike["player_id"]] = {
                k: bike[k] for k in ("x", "y", "direction", "alive")
            }
        for x, y, owner in payload["new_cells"]:
            self.cells[(x, y)] = owner
        for item in payload["eliminations"]:
            self.reasons[item["player_id"]] = item["reason"]
        self.result = payload["result"]
        return payload["eliminations"]

    def finished(self):
        return self.result["status"] != "ONGOING"

    def my_bike_alive(self):
        bike = self.bikes.get(self.my_id)
        return bool(bike and bike["alive"])
