"""Um socket, um buffer e uma thread de leitura por conexão."""
import socket
import threading

from src.core.config import SEND_TIMEOUT
from src.core.protocol import receive_message, send_message, validate_message


class Connection:
    def __init__(self, sock, on_message, on_close, buffer=b""):
        self.socket = sock
        self.socket.settimeout(SEND_TIMEOUT)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buffer = buffer
        self.on_message = on_message
        self.on_close = on_close
        self.closed = False
        self.lock = threading.RLock()

    def start(self):
        threading.Thread(target=self._receive, daemon=True).start()

    def _receive(self):
        try:
            while not self.closed:
                message, self.buffer = receive_message(self.socket, self.buffer)
                if message is None:
                    break
                validate_message(message)
                self.on_message(message)
        except (OSError, ValueError, RecursionError) as error:
            self.close(str(error))
        finally:
            self.close()

    def send(self, message):
        # Evita que duas threads misturem bytes no mesmo socket.
        with self.lock:
            if self.closed:
                raise ConnectionError("Conexão encerrada.")
            try:
                send_message(self.socket, message)
            except OSError as error:
                self.close(str(error))
                raise

    def close(self, error=None):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
        self.on_close(error)


def listen(host, port, on_accept):
    """Retorna o socket de escuta; cada conexão é preparada em sua thread."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen()
        server.settimeout(0.2)
    except OSError:
        server.close()
        raise

    def prepare(sock, address):
        try:
            on_accept(sock, address)
        except (OSError, ValueError, RecursionError):
            sock.close()

    def accept_loop():
        while server.fileno() != -1:
            try:
                sock, address = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=prepare, args=(sock, address), daemon=True
            ).start()

    threading.Thread(target=accept_loop, daemon=True).start()
    return server
