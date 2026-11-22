"""Endereços locais. A configuração da partida será fornecida pelo lobby."""
import os

from dotenv import load_dotenv

load_dotenv()

LOBBY_HOST = os.getenv("LOBBY_HOST", "127.0.0.1")
LOBBY_PORT = int(os.getenv("LOBBY_PORT", "5000"))
PEER_BIND_HOST = os.getenv("PEER_BIND_HOST", "0.0.0.0")
PEER_ADVERTISE_HOST = os.getenv("PEER_ADVERTISE_HOST", "127.0.0.1")
PEER_PORT = int(os.getenv("PEER_PORT", "6001"))
CONNECT_TIMEOUT = 3.0
SEND_TIMEOUT = 1.0
MESH_TIMEOUT = 15.0
MAX_MESSAGE_BYTES = 1_048_576
