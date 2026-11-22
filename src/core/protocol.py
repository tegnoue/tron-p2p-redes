"""Uma mensagem é um objeto JSON terminado por LF."""
import json
import socket

from src.core.config import MAX_MESSAGE_BYTES


def encode_message(message):
    if not isinstance(message, dict):
        raise ValueError("A mensagem deve ser um dicionário.")
    data = json.dumps(
        message, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8") + b"\n"
    if len(data) > MAX_MESSAGE_BYTES:
        raise ValueError("Mensagem grande demais.")
    return data


def send_message(connection, message):
    connection.sendall(encode_message(message))


def receive_message(connection, buffer, wait_on_timeout=True):
    # O buffer é reaproveitado; recv não respeita fronteiras de mensagens.
    while b"\n" not in buffer:
        if len(buffer) >= MAX_MESSAGE_BYTES:
            raise ValueError("Mensagem grande demais.")
        try:
            chunk = connection.recv(4096)
        except socket.timeout:
            if not wait_on_timeout:
                raise
            continue  # mantém o que já chegou; close interrompe a leitura
        if not chunk:
            if buffer:
                raise ConnectionError("Conexão fechou com mensagem incompleta.")
            return None, b""
        buffer += chunk

    line, buffer = buffer.split(b"\n", 1)
    if len(line) + 1 > MAX_MESSAGE_BYTES:
        raise ValueError("Mensagem grande demais.")
    message = json.loads(line.decode("utf-8"), parse_constant=_invalid_number,
                         object_pairs_hook=_unique_object)
    if not isinstance(message, dict):
        raise ValueError("O JSON deve ser um objeto.")
    # Rejeita números não finitos e escapes Unicode que não formam UTF-8.
    json.dumps(message, ensure_ascii=False, allow_nan=False).encode("utf-8")
    return message, buffer


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Chave duplicada: {key}")
        result[key] = value
    return result


def _invalid_number(value):
    raise ValueError(f"Número JSON inválido: {value}")


def make_message(kind, payload, sender, message_id, match_id=None,
                 attempt_id=None, epoch=None, reply_to=None):
    return {
        "version": 1, "type": kind, "id": message_id, "reply_to": reply_to,
        "sender_id": sender, "match_id": match_id, "attempt_id": attempt_id,
        "epoch": epoch, "payload": payload,
    }


def validate_message(message):
    fields = {
        "version", "type", "id", "reply_to", "sender_id",
        "match_id", "attempt_id", "epoch", "payload",
    }
    if set(message) != fields or type(message["version"]) is not int:
        raise ValueError("Envelope inválido.")
    if message["version"] != 1:
        raise ValueError("Versão inválida.")
    if not isinstance(message["type"], str) or not message["type"]:
        raise ValueError("Tipo inválido.")
    if type(message["id"]) is not int or message["id"] < 1:
        raise ValueError("ID inválido.")
    if message["reply_to"] is not None:
        if type(message["reply_to"]) is not int or message["reply_to"] < 1:
            raise ValueError("reply_to inválido.")
    for field in ("sender_id", "match_id", "attempt_id"):
        value = message[field]
        if value is not None and (not isinstance(value, str) or not 1 <= len(value) <= 64):
            raise ValueError(f"{field} inválido.")
    if message["epoch"] is not None:
        if type(message["epoch"]) is not int or message["epoch"] < 0:
            raise ValueError("Época inválida.")
    if not isinstance(message["payload"], dict):
        raise ValueError("Payload inválido.")
