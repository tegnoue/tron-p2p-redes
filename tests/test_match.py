"""Partidas completas com sockets reais em loopback (sem desenhar a tela)."""
import queue
import threading
import time
import unittest

from src.lobby.server import run_server
from src.node.app import App
from src.node.client import NodeClient


def wait_until(condition, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("Condição não atingida")


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.stop_lobby = threading.Event()
        ports = queue.Queue()
        threading.Thread(target=run_server, daemon=True, args=(
            "127.0.0.1", 0, {"tick_ms": 40}, self.stop_lobby, ports.put,
        )).start()
        self.lobby_port = ports.get(timeout=5)
        self.addCleanup(self.stop_lobby.set)
        self.apps = []

    def player(self, name):
        node = NodeClient("anonimo", "127.0.0.1", 0)
        app = App(name, node, queue.Queue(), render=False)
        app.connect("127.0.0.1", self.lobby_port)
        thread = threading.Thread(target=app.run, daemon=True)
        thread.start()
        self.apps.append(app)
        self.addCleanup(lambda: (app.keys.put("\x04"), thread.join(2)))
        wait_until(lambda: app.registered)
        return app

    @staticmethod
    def type(app, text):
        for char in text + "\n":
            app.keys.put(char)

    def start_match(self, count=3):
        apps = [self.player(f"j{i}") for i in range(count)]
        self.type(apps[0], "criar sala")
        wait_until(lambda: apps[0].room is not None)
        for app in apps[1:]:
            self.type(app, "entrar " + apps[0].room["room_id"])
        wait_until(lambda: len(apps[0].room["players"]) == count)
        self.type(apps[0], "iniciar")
        wait_until(lambda: all(a.phase == "JOGANDO" for a in apps))
        return apps

    def assert_same_result(self, apps):
        wait_until(lambda: all(a.phase == "RESULTADO" for a in apps))
        first = apps[0].view
        for app in apps:
            self.assertIsNone(app.abort_reason)
            self.assertEqual(app.view.result, first.result)
            self.assertEqual(app.view.cycle, first.cycle)
            self.assertEqual(app.view.cells, first.cells)
            self.assertEqual(app.view.reasons, first.reasons)
        self.assertIn(first.result["status"], ("WINNER", "DRAW"))

    def test_complete_match_with_turns(self):
        apps = self.start_match()
        self.type(apps[1], "w")  # uma curva pela rede
        self.type(apps[0], "s")  # uma curva local do host
        self.assert_same_result(apps)

    def test_player_disconnect_eliminates_and_match_continues(self):
        apps = self.start_match()
        host, quitter, other = apps
        quitter_id = quitter.node.player_id
        quitter.keys.put("q")
        self.assert_same_result([host, other])
        self.assertEqual(host.view.reasons[quitter_id], "DESCONEXAO")

    def test_host_failure_ends_match_for_everyone(self):
        apps = self.start_match()
        apps[0].keys.put("q")
        wait_until(lambda: all(a.phase == "RESULTADO" for a in apps[1:]))
        for app in apps[1:]:
            self.assertIn("host", app.abort_reason)

    def test_lobby_failure_does_not_stop_match(self):
        apps = self.start_match()
        self.stop_lobby.set()
        wait_until(lambda: not any(a.lobby_ok for a in apps))
        self.assert_same_result(apps)

    def test_only_creator_can_start(self):
        apps = [self.player(f"j{i}") for i in range(3)]
        self.type(apps[0], "criar sala")
        wait_until(lambda: apps[0].room is not None)
        for app in apps[1:]:
            self.type(app, "entrar 1")
        wait_until(lambda: len(apps[0].room["players"]) == 3)
        self.type(apps[1], "iniciar")
        wait_until(lambda: any("criador" in line for line in apps[1].log))
        self.assertEqual(apps[0].phase, "LOBBY")


if __name__ == "__main__":
    unittest.main()
