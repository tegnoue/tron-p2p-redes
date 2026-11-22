"""Erros da comunicação; as regras do jogo decidem como tratá-los."""


class ProtocolError(ValueError):
    """Bytes ou mensagem não atendem ao protocolo de transporte."""


class ConnectionClosedError(ConnectionError):
    """A operação exige uma conexão que já foi encerrada."""


class SendQueueFull(ConnectionError):
    """O destino não acompanha o ritmo de envio."""
