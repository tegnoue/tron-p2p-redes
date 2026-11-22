"""JSON por linha. Não decide registros, salas, movimentos ou eleições."""
import json
import math

from src.core.exceptions import ProtocolError

MAX_MESSAGE_BYTES = 1_048_576


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(f"Chave JSON duplicada: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ProtocolError(f"Constante JSON inválida: {value}")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ProtocolError("Número JSON não finito.")
    return number


def encode_message(message, max_bytes=MAX_MESSAGE_BYTES):
    if not isinstance(message, dict):
        raise ProtocolError("Mensagem deve ser objeto JSON.")
    try:
        data = json.dumps(
            message, ensure_ascii=False, allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ProtocolError(f"Não foi possível codificar JSON: {error}") from error
    if len(data) > max_bytes:
        raise ProtocolError("Mensagem excede o limite.")
    return data


def decode_message(line):
    try:
        message = json.loads(
            line.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
            parse_float=_finite_float,
        )
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ProtocolError(f"JSON inválido: {error}") from error
    if not isinstance(message, dict):
        raise ProtocolError("Mensagem deve ser objeto JSON.")
    pending = [message]
    try:
        while pending:
            value = pending.pop()
            if isinstance(value, str):
                value.encode("utf-8")
            elif isinstance(value, dict):
                pending.extend(value.keys())
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
    except UnicodeError as error:
        raise ProtocolError("String contém caractere Unicode inválido.") from error
    return message


def send_message(connection, message, max_bytes=MAX_MESSAGE_BYTES):
    """Uso síncrono, principalmente durante o handshake."""
    connection.sendall(encode_message(message, max_bytes))


class MessageReader:
    """Um leitor por socket. Preserva bytes até entre timeouts."""

    def __init__(self, connection, max_bytes=MAX_MESSAGE_BYTES, buffer=b""):
        self.connection = connection
        self.max_bytes = max_bytes
        self.buffer = buffer

    def receive(self):
        while b"\n" not in self.buffer:
            if len(self.buffer) >= self.max_bytes:
                raise ProtocolError("Mensagem excede o limite.")
            chunk = self.connection.recv(4096)
            if not chunk:
                if self.buffer:
                    raise ProtocolError("Conexão encerrada no meio de mensagem.")
                return None
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        if len(line) + 1 > self.max_bytes:
            raise ProtocolError("Mensagem excede o limite.")
        return decode_message(line)


def receive_message(connection, buffer=b""):
    """Compatibilidade com o exemplo inicial: retorna mensagem e restante."""
    reader = MessageReader(connection, buffer=buffer)
    message = reader.receive()
    return message, reader.buffer


def make_message(message_type, payload, sender_id, message_id,
                 match_id=None, attempt_id=None, epoch=None, reply_to=None):
    return {
        "version": 1, "type": message_type, "id": message_id,
        "reply_to": reply_to, "sender_id": sender_id,
        "match_id": match_id, "attempt_id": attempt_id,
        "epoch": epoch, "payload": payload,
    }


def validate_envelope(message):
    expected = {
        "version", "type", "id", "reply_to", "sender_id",
        "match_id", "attempt_id", "epoch", "payload",
    }
    if set(message) != expected:
        raise ProtocolError("Campos do envelope inválidos.")
    if type(message["version"]) is not int or message["version"] != 1:
        raise ProtocolError("Versão não suportada.")
    if not isinstance(message["type"], str) or not message["type"]:
        raise ProtocolError("Tipo da mensagem inválido.")
    if type(message["id"]) is not int or message["id"] < 1:
        raise ProtocolError("ID da mensagem inválido.")
    if message["reply_to"] is not None:
        if type(message["reply_to"]) is not int or message["reply_to"] < 1:
            raise ProtocolError("reply_to inválido.")
    for field in ("sender_id", "match_id", "attempt_id"):
        value = message[field]
        if value is not None and (
            not isinstance(value, str) or not 1 <= len(value) <= 64
        ):
            raise ProtocolError(f"{field} inválido.")
    if message["epoch"] is not None:
        if type(message["epoch"]) is not int or message["epoch"] < 0:
            raise ProtocolError("Época inválida.")
    if not isinstance(message["payload"], dict):
        raise ProtocolError("Payload deve ser objeto.")
    return message
