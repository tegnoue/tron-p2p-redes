"""Interface no terminal: leitura de teclas sem Enter e desenho com códigos ANSI.

Só usa a biblioteca padrão: termios/tty no Linux e macOS, msvcrt no Windows.
A thread do teclado apenas coloca as teclas numa fila; quem decide o que
fazer com elas é o laço do aplicativo.
"""
import os
import queue
import sys
import threading

KEY_DIRECTIONS = {"w": "UP", "s": "DOWN", "a": "LEFT", "d": "RIGHT"}
COLORS = ["\033[91m", "\033[96m", "\033[92m", "\033[93m"]  # A, B, C, D
RESET = "\033[0m"
REASONS = {"WALL": "parede", "TRAIL": "rastro", "HEAD_ON": "colisão frontal",
           "DESCONEXAO": "desconexão"}


class Keyboard:
    """Lê uma tecla por vez, sem esperar Enter."""

    def __init__(self):
        self.keys = queue.Queue()
        self._restore = None

    def start(self):
        if os.name == "nt":
            import msvcrt
            os.system("")  # ativa os códigos ANSI no terminal do Windows
            read = msvcrt.getwch
        else:
            import termios
            import tty
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            tty.setcbreak(fd)  # teclas chegam na hora, sem eco
            self._restore = lambda: termios.tcsetattr(fd, termios.TCSADRAIN, old)
            read = lambda: sys.stdin.read(1)

        def loop():
            while True:
                key = read()
                self.keys.put(key or "\x04")  # vazio = fim da entrada
                if not key:
                    return

        threading.Thread(target=loop, daemon=True).start()
        sys.stdout.write("\033[?25l\033[2J")  # esconde o cursor e limpa a tela

    def stop(self):
        sys.stdout.write("\033[?25h" + RESET + "\n")  # mostra o cursor de novo
        sys.stdout.flush()
        if self._restore:
            self._restore()


def draw(lines):
    """Redesenha a tela no lugar, sem rolar o terminal."""
    sys.stdout.write("\033[H" + "\n".join(l + "\033[K" for l in lines) + "\033[J")
    sys.stdout.flush()


def lobby_screen(nickname, room, log, line):
    lines = [f"TRON P2P — lobby    jogador: {nickname}", ""]
    if room:
        names = ", ".join(m["nickname"] for m in room["players"])
        creator = next((m["nickname"] for m in room["players"]
                        if m["player_id"] == room["creator_id"]), "?")
        lines.append(f"Sala {room['room_id']} '{room['name']}' "
                     f"({len(room['players'])}/{room['max_players']}) "
                     f"criador: {creator} | jogadores: {names}")
    else:
        lines.append("Você não está em uma sala.")
    lines += ["", "Comandos: listar | criar NOME | entrar ID | sair | iniciar | fim",
              "-" * 60]
    lines += log[-15:]
    lines += ["", "> " + line]
    return lines


def match_screen(view, phase, info, log):
    """Arena à esquerda; legenda e situação à direita."""
    heads = {(b["x"], b["y"]): p for p, b in view.bikes.items()}
    border = "+" + "-" * view.width + "+"
    rows = [border]
    for y in range(view.height):
        row = []
        for x in range(view.width):
            owner = view.cells.get((x, y))
            if owner is None:
                row.append(" ")
                continue
            color = COLORS[view.order.index(owner)]
            head = heads.get((x, y))
            if head is not None and view.bikes[head]["alive"]:
                char = view.letter(head)
            elif head is not None:
                char = "X"
            else:
                char = view.letter(owner).lower()
            row.append(color + char + RESET)
        rows.append("|" + "".join(row) + "|")
    rows.append(border)

    panel = [f"Fase: {phase}", f"Ciclo: {view.cycle}", ""]
    for player_id in view.order:
        name = view.nicknames[player_id]
        tags = []
        if player_id == view.my_id:
            tags.append("você")
        if player_id == view.host_id:
            tags.append("host")
        bike = view.bikes[player_id]
        status = ("vivo" if bike["alive"] else
                  "eliminado (" + REASONS.get(view.reasons.get(player_id), "?") + ")")
        tag = f" [{', '.join(tags)}]" if tags else ""
        panel.append(COLORS[view.order.index(player_id)] + view.letter(player_id)
                     + RESET + f" {name}{tag}: {status}")
    panel += [""] + info + ["", "Teclas: W A S D mover | q sair", ""]
    panel += ["Eventos:"] + log[-8:]
    return [r + "   " + (panel[i] if i < len(panel) else "")
            for i, r in enumerate(rows)]


def result_lines(view, my_id, abort_reason):
    """Situação global e individual do resultado."""
    if abort_reason:
        return ["PARTIDA ENCERRADA", abort_reason,
                "Enter: voltar ao lobby | q: sair"]
    result = view.result
    if result["status"] == "WINNER":
        global_text = "Vencedor: " + view.nicknames[result["winner_id"]]
        mine = "VOCÊ VENCEU!" if result["winner_id"] == my_id else "Você perdeu."
    else:
        names = ", ".join(view.nicknames[p] for p in result["finalists"])
        global_text = "Empate entre " + names
        mine = "EMPATE!" if my_id in result["finalists"] else "Você perdeu."
    return [mine, global_text, "Enter: voltar ao lobby | q: sair"]
