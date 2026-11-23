import itertools
import unittest

from src.core.protocol import make_message
from src.lobby.session import Lobby


class LobbyTests(unittest.TestCase):
    def setUp(self):
        self.lobby = Lobby()
        self.ids = itertools.count(1)
        self.player_ids = {}

    def request(self, client, kind, payload=None):
        message = make_message(kind, payload or {}, self.player_ids.get(client),
                               next(self.ids))
        return self.lobby.handle(client, message)

    def register(self, client, nickname):
        self.lobby.connect(client, "10.0.0.%d" % client)
        out = self.request(client, "REGISTER", {
            "nickname": nickname, "peer_endpoint": {"host": None, "port": 6000 + client},
        })
        self.assertEqual(out[0][1], "REGISTER_OK")
        self.player_ids[client] = out[0][2]["player_id"]

    def last_error(self, out):
        self.assertEqual(out[-1][1], "ERROR")
        return out[-1][2]["code"]

    def room_with(self, count):
        for client in range(1, count + 1):
            self.register(client, f"j{client}")
        room_id = self.request(1, "CREATE_ROOM", {"name": "sala"})[0][2]["room"]["room_id"]
        for client in range(2, count + 1):
            self.request(client, "JOIN_ROOM", {"room_id": room_id})
        return room_id

    def test_must_register_first(self):
        self.lobby.connect(1, "10.0.0.1")
        self.assertEqual(self.last_error(self.request(1, "LIST_ROOMS")), "INVALID_STATE")
        self.register(1, "ana")
        self.assertEqual(self.last_error(self.request(1, "REGISTER", {})),
                         "ALREADY_REGISTERED")

    def test_invalid_payload_and_unknown_type(self):
        self.lobby.connect(1, "10.0.0.1")
        out = self.request(1, "REGISTER", {"nickname": "", "peer_endpoint": {"port": 1}})
        self.assertEqual(self.last_error(out), "INVALID_MESSAGE")
        self.register(1, "ana")
        self.assertEqual(self.last_error(self.request(1, "DANCAR")), "INVALID_MESSAGE")

    def test_endpoint_uses_ip_seen_by_lobby(self):
        self.register(1, "ana")
        out = self.request(1, "CREATE_ROOM", {"name": "s"})
        member = out[0][2]["room"]["players"][0]
        self.assertEqual(member["endpoint"], {"host": "10.0.0.1", "port": 6001})

    def test_fifth_player_and_two_rooms_are_refused(self):
        room_id = self.room_with(4)
        self.register(5, "j5")
        out = self.request(5, "JOIN_ROOM", {"room_id": room_id})
        self.assertEqual(self.last_error(out), "ROOM_FULL")
        self.assertEqual(self.last_error(self.request(2, "CREATE_ROOM", {"name": "x"})),
                         "ALREADY_IN_ROOM")

    def test_only_creator_starts_with_three_or_four(self):
        room_id = self.room_with(2)
        self.assertEqual(self.last_error(self.request(1, "START_MATCH")),
                         "NOT_ENOUGH_PLAYERS")
        self.register(3, "j3")
        self.request(3, "JOIN_ROOM", {"room_id": room_id})
        self.assertEqual(self.last_error(self.request(2, "START_MATCH")),
                         "NOT_ROOM_CREATOR")
        out = self.request(1, "START_MATCH")
        self.assertEqual(out[0][1], "START_MATCH_OK")
        configs = [o for o in out if o[1] == "MATCH_CONFIG"]
        self.assertEqual(sorted(o[0] for o in configs), [1, 2, 3])
        config = configs[0][2]["config"]
        self.assertEqual(config["host_id"], self.player_ids[1])
        self.assertEqual(len(config["spawns"]), 3)
        self.register(4, "j4")
        self.assertEqual(self.last_error(self.request(4, "JOIN_ROOM", {"room_id": room_id})),
                         "ROOM_NOT_JOINABLE")

    def test_creator_leaving_passes_control_and_empty_room_disappears(self):
        room_id = self.room_with(3)
        out = self.lobby.disconnect(1)
        updates = [o for o in out if o[1] == "ROOM_UPDATED"]
        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[0][2]["room"]["creator_id"], self.player_ids[2])
        self.request(2, "LEAVE_ROOM")
        self.request(3, "LEAVE_ROOM")
        self.assertNotIn(room_id, self.lobby.rooms)


if __name__ == "__main__":
    unittest.main()
