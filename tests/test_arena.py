import unittest

from src.game.arena import create_state
from src.game.engine import eliminate, step, valid_turn


def spawn(player_id, x, y, direction):
    return {"player_id": player_id, "x": x, "y": y, "direction": direction}


class EngineTests(unittest.TestCase):
    def test_bike_moves_one_cell_and_leaves_trail(self):
        state = create_state(10, 10, [spawn("a", 2, 2, "RIGHT"),
                                      spawn("b", 2, 7, "RIGHT")])
        event = step(state, {})
        self.assertEqual((state["bikes"]["a"]["x"], state["bikes"]["a"]["y"]), (3, 2))
        self.assertIn((2, 2), state["occupied"])
        self.assertIn([3, 2, "a"], event["new_cells"])
        self.assertEqual(event["cycle"], 1)

    def test_reverse_turn_is_ignored(self):
        self.assertFalse(valid_turn("RIGHT", "LEFT"))
        self.assertFalse(valid_turn("RIGHT", "RIGHT"))
        self.assertTrue(valid_turn("RIGHT", "UP"))
        state = create_state(10, 10, [spawn("a", 2, 2, "RIGHT"),
                                      spawn("b", 2, 7, "RIGHT")])
        step(state, {"a": "LEFT"})
        self.assertEqual(state["bikes"]["a"]["x"], 3)

    def test_wall_keeps_last_valid_position(self):
        state = create_state(5, 5, [spawn("a", 4, 0, "RIGHT"),
                                    spawn("b", 0, 4, "UP"),
                                    spawn("c", 2, 2, "DOWN")])
        event = step(state, {})
        self.assertFalse(state["bikes"]["a"]["alive"])
        self.assertEqual(state["bikes"]["a"]["x"], 4)
        self.assertEqual(event["eliminations"][0]["reason"], "WALL")
        self.assertEqual(event["eliminations"][0]["attempted_x"], 5)

    def test_same_cell_eliminates_both(self):
        state = create_state(9, 9, [spawn("a", 2, 4, "RIGHT"),
                                    spawn("b", 4, 4, "LEFT"),
                                    spawn("c", 0, 0, "RIGHT")])
        event = step(state, {})
        self.assertEqual({e["player_id"]: e["reason"] for e in event["eliminations"]},
                         {"a": "HEAD_ON", "b": "HEAD_ON"})
        self.assertEqual(state["occupied"][(3, 4)], "a")
        self.assertEqual(event["result"]["winner_id"], "c")

    def test_swap_positions_eliminates_both(self):
        state = create_state(9, 9, [spawn("a", 2, 4, "RIGHT"),
                                    spawn("b", 3, 4, "LEFT"),
                                    spawn("c", 0, 0, "RIGHT")])
        event = step(state, {})
        self.assertEqual({e["reason"] for e in event["eliminations"]}, {"TRAIL"})
        self.assertEqual(len(event["eliminations"]), 2)

    def test_trail_of_eliminated_bike_remains(self):
        state = create_state(6, 6, [spawn("a", 5, 0, "RIGHT"),
                                    spawn("b", 3, 2, "UP"),
                                    spawn("c", 0, 5, "RIGHT")])
        step(state, {})
        self.assertIn((5, 0), state["occupied"])
        step(state, {"b": "RIGHT"})  # outro ciclo: o rastro de a continua
        self.assertEqual(state["occupied"][(5, 0)], "a")

    def test_last_bikes_together_is_draw(self):
        state = create_state(5, 5, [spawn("a", 4, 0, "RIGHT"),
                                    spawn("b", 0, 4, "LEFT"),
                                    spawn("c", 2, 2, "UP")])
        step(state, {})
        self.assertEqual(state["result"]["winner_id"], "c")
        state = create_state(5, 5, [spawn("a", 4, 0, "RIGHT"),
                                    spawn("b", 0, 4, "LEFT"),
                                    spawn("c", 2, 0, "UP")])
        event = step(state, {})
        self.assertEqual(event["result"],
                         {"status": "DRAW", "winner_id": None,
                          "finalists": ["a", "b", "c"]})

    def test_id_order_does_not_change_result(self):
        def run(ids):
            state = create_state(9, 9, [spawn(ids[0], 2, 4, "RIGHT"),
                                        spawn(ids[1], 4, 4, "LEFT"),
                                        spawn(ids[2], 3, 0, "DOWN")])
            results = []
            for _ in range(5):
                if state["result"]["status"] != "ONGOING":
                    break
                results.append(step(state, {})["eliminations"])
            return [[e["reason"] for e in r] for r in results]
        self.assertEqual(run(["a", "b", "c"]), run(["z", "y", "x"]))

    def test_disconnection_eliminates_without_moving_others(self):
        state = create_state(9, 9, [spawn("a", 1, 1, "RIGHT"),
                                    spawn("b", 7, 7, "LEFT"),
                                    spawn("c", 1, 7, "UP")])
        info = eliminate(state, "a", "DESCONEXAO")
        self.assertEqual(info["reason"], "DESCONEXAO")
        self.assertEqual(state["bikes"]["b"]["x"], 7)
        self.assertIn((1, 1), state["occupied"])
        eliminate(state, "b", "DESCONEXAO")
        self.assertEqual(state["result"]["winner_id"], "c")
        self.assertIsNone(eliminate(state, "c", "DESCONEXAO"))


if __name__ == "__main__":
    unittest.main()
