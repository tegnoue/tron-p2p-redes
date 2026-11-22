"""Sockets em segundo plano: uma leitura e uma escrita por conexão."""
import logging
import queue
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any

from src.core.exceptions import ConnectionClosedError, SendQueueFull
from src.core.protocol import MessageReader, encode_message


@dataclass(frozen=True)
class NetworkEvent:
    kind: str                       # connected, message, disconnected, error
    peer_id: str
    message: dict[str, Any] | None = None
    error: str | None = None


class JsonConnection:
    """send enfileira; somente a thread de escrita usa sendall."""

    def __init__(self, sock, peer_id, config, on_message, on_close,
                 reader=None):
        self.socket = sock
        self.peer_id = peer_id
        self.config = config
        self.on_message = on_message
        self.on_close = on_close
        self.reader = reader or MessageReader(sock, config.max_message_bytes)
        self.socket.settimeout(config.io_timeout)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.last_received_at = time.monotonic()
        self._outbox = queue.Queue(config.max_pending_messages)
        self._condition = threading.Condition()
        self._pending = 0
        self._pending_bytes = 0
        self._closed = False
        self._started = False
        self._threads = []

    @property
    def closed(self):
        with self._condition:
            return self._closed

    def start(self):
        with self._condition:
            if self._closed or self._started:
                return
            self._started = True
            for name, target in (("send", self._write), ("receive", self._read)):
                thread = threading.Thread(
                    target=target, name=f"{name}-{self.peer_id}", daemon=True
                )
                self._threads.append(thread)
                thread.start()

    def send(self, message):
        data = encode_message(message, self.config.max_message_bytes)
        with self._condition:
            if self._closed:
                raise ConnectionClosedError(f"Conexão fechada: {self.peer_id}")
            try:
                if (self._pending >= self.config.max_pending_messages
                        or self._pending_bytes + len(data) > self.config.max_pending_bytes):
                    raise queue.Full
                self._outbox.put_nowait(data)
            except queue.Full:
                overflow = True
            else:
                self._pending += 1
                self._pending_bytes += len(data)
                overflow = False
        if overflow:
            error = SendQueueFull(f"Fila cheia: {self.peer_id}")
            self.close(error=error)
            raise error

    def flush(self, timeout=2.0):
        """Espera escrita local, não confirmação da aplicação remota."""
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._pending and not self._closed:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return not self._closed and self._pending == 0

    def _read(self):
        try:
            while not self.closed:
                try:
                    message = self.reader.receive()
                except socket.timeout:
                    continue  # reader mantém seus bytes parciais
                if message is None:
                    self.close()
                    return
                self.last_received_at = time.monotonic()
                self.on_message(self, message)
        except Exception as error:
            self.close(error=error)

    def _write(self):
        while not self.closed:
            try:
                data = self._outbox.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if not self.closed:
                    self.socket.sendall(data)
            except OSError as error:
                self.close(error=error)
            finally:
                with self._condition:
                    self._pending -= 1
                    self._pending_bytes -= len(data)
                    self._condition.notify_all()

    def close(self, error=None):
        with self._condition:
            if self._closed:
                return
            self._closed = True
            while True:
                try:
                    dropped = self._outbox.get_nowait()
                except queue.Empty:
                    break
                self._pending -= 1
                self._pending_bytes -= len(dropped)
            self._condition.notify_all()
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()
        try:
            self.on_close(self, error)
        except Exception:
            logging.exception("Erro no callback de encerramento")

    def wait_closed(self, timeout=2.0):
        deadline = time.monotonic() + timeout
        for thread in self._threads:
            if thread is not threading.current_thread():
                thread.join(max(0, deadline - time.monotonic()))


class TcpListener:
    """Aceita sockets sem bloquear por causa do handshake de outro cliente."""

    def __init__(self, host, port, on_socket, on_error=None):
        self.host, self.port = host, port
        self.on_socket = on_socket
        self.on_error = on_error or (lambda error: None)
        self.socket = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._pending = set()
        self._workers = set()
        self._thread = None

    @property
    def address(self):
        return self.socket.getsockname()

    def start(self):
        if self.socket is not None:
            raise RuntimeError("Listener já iniciado.")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.listen()
            sock.settimeout(0.2)
        except Exception:
            sock.close()
            raise
        self.socket = sock
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()

    def _accept(self):
        while not self._stop.is_set():
            try:
                sock, address = self.socket.accept()
            except socket.timeout:
                continue
            except OSError as error:
                if not self._stop.is_set():
                    self.on_error(error)
                return
            with self._lock:
                if self._stop.is_set():
                    sock.close()
                    return
                self._pending.add(sock)
                worker = threading.Thread(
                    target=self._prepare, args=(sock, address), daemon=True
                )
                self._workers.add(worker)
                worker.start()

    def _prepare(self, sock, address):
        try:
            self.on_socket(sock, address)
        except Exception as error:
            sock.close()
            if not self._stop.is_set():
                self.on_error(error)
        finally:
            with self._lock:
                self._pending.discard(sock)
                self._workers.discard(threading.current_thread())

    def close(self):
        self._stop.set()
        if self.socket is not None:
            self.socket.close()
        with self._lock:
            sockets, workers = list(self._pending), list(self._workers)
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        if self._thread:
            self._thread.join(2)
        for thread in workers:
            thread.join(2)
