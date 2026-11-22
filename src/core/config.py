"""Configurações locais. Argumentos CLI podem substituir estes valores."""
import os
import math
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class NetworkConfig:
    lobby_host: str = "127.0.0.1"
    lobby_port: int = 5000
    peer_bind_host: str = "0.0.0.0"
    peer_advertise_host: str = "127.0.0.1"
    peer_port: int = 6001
    connect_timeout: float = 3.0
    io_timeout: float = 0.5
    mesh_timeout: float = 15.0
    max_message_bytes: int = 1_048_576
    max_pending_messages: int = 128
    max_pending_bytes: int = 4_194_304

    def __post_init__(self):
        for port in (self.lobby_port, self.peer_port):
            if not 0 <= port <= 65535:
                raise ValueError("Porta deve estar entre 0 e 65535.")
        for value in (self.connect_timeout, self.io_timeout, self.mesh_timeout):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Timeout deve ser positivo.")
        if (self.max_message_bytes < 128 or self.max_pending_messages < 1
                or self.max_pending_bytes < 128):
            raise ValueError("Limites de mensagem/fila inválidos.")

    @classmethod
    def from_env(cls):
        load_dotenv()
        return cls(
            lobby_host=os.getenv("LOBBY_HOST", "127.0.0.1"),
            lobby_port=int(os.getenv("LOBBY_PORT", "5000")),
            peer_bind_host=os.getenv("PEER_BIND_HOST", "0.0.0.0"),
            peer_advertise_host=os.getenv("PEER_ADVERTISE_HOST", "127.0.0.1"),
            peer_port=int(os.getenv("PEER_PORT", "6001")),
            connect_timeout=float(os.getenv("CONNECT_TIMEOUT", "3")),
            io_timeout=float(os.getenv("IO_TIMEOUT", "0.5")),
            mesh_timeout=float(os.getenv("MESH_TIMEOUT", "15")),
            max_message_bytes=int(os.getenv("MAX_MESSAGE_BYTES", "1048576")),
            max_pending_messages=int(os.getenv("MAX_PENDING_MESSAGES", "128")),
            max_pending_bytes=int(os.getenv("MAX_PENDING_BYTES", "4194304")),
        )
