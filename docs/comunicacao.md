# Comunicação TCP

Esta versão usa funções para JSON, configuração simples e duas classes pequenas. Connection representa um socket; NodeClient reúne as conexões de um jogador. O servidor de diagnóstico e o cliente podem ser executados juntos.

## O que cada arquivo faz

| Arquivo | Responsabilidade |
|---|---|
| core/config.py | Endereços por ambiente/.env e limites locais |
| core/protocol.py | Codificar, enviar, receber e validar JSON |
| core/transport.py | Connection e função listen |
| lobby/server.py | Aceitar clientes e processar seus eventos |
| node/client.py | Conectar ao lobby e montar a malha P2P |
| tests/test_communication.py | Testes de mensagens e sockets |

Registro, salas, movimentos e eleições não são implementados por esta camada. O servidor executável responde ECHO para verificar o transporte; TEXT/ECHO são mensagens de diagnóstico.

## Executar

Na raiz do projeto:
~~~bash
poetry install --no-root
poetry run python -m src.lobby
~~~

Em outro terminal:
~~~bash
poetry run python -m src.node --id A --peer-port 6001
~~~

No cliente:
~~~text
/lobby Olá!
/quit
~~~

O servidor deve devolver o texto. Outro cliente pode conectar em uma porta P2P diferente. O recebimento continua mesmo enquanto o teclado está parado.

O pyproject exige Python 3.14. Os testes desta alteração foram executados em Python 3.12.14; a equipe deve confirmar também em 3.14.

## Testar dois pares sem lobby

Iniciar ambos dentro de 15 segundos:

~~~bash
poetry run python -m src.node --id A --peer-port 6001 --no-lobby --peer B=127.0.0.1:6002
~~~

~~~bash
poetry run python -m src.node --id B --peer-port 6002 --no-lobby --peer A=127.0.0.1:6001
~~~

Após connected, A pode digitar /to B Olá e B pode digitar /to A Resposta. /all texto envia a todos os pares conectados, sem incluir o lobby.

Para três ou quatro jogadores, cada comando deve incluir --peer para todos os outros. O menor ID de cada par inicia a conexão. Todos escutam; o handshake verifica identidade e contexto da partida.

Em máquinas distintas, os endereços precisam ser IPs reais alcançáveis. O servidor pode usar --host 0.0.0.0 para ouvir na rede. O jogador pode usar --bind-host 0.0.0.0; esse endereço de escuta não deve ser anunciado aos outros.

## Como o código funciona

encode_message transforma um dicionário em JSON UTF-8 e acrescenta LF. send_message envia esses bytes.

receive_message acumula bytes até LF, separa a primeira mensagem e devolve o restante do buffer. O buffer deve ser reutilizado. Fechamento sem pendências devolve None; fechamento no meio de uma mensagem gera erro. Um timeout de leitura não descarta os bytes já acumulados.

Connection mantém esse buffer e uma thread de leitura. Quando recebe mensagem, chama um callback, isto é, uma função fornecida por quem criou a conexão. O aplicativo do jogador usa o callback para colocar a mensagem em uma queue.Queue.

O envio é síncrono, com lock para impedir que duas threads misturem bytes. Não há fila de envio nem thread de escrita. Um destino lento pode bloquear a chamada por até SEND_TIMEOUT, cujo padrão é um segundo; depois o erro fecha a conexão. Essa escolha simplifica a implementação e deve ser considerada na taxa de ciclos do jogo.

listen aceita sockets em segundo plano. Cada preparação ocorre numa thread para que um handshake lento não impeça aceitar outro jogador.

## Uso pelo jogo

~~~python
from src.node.client import NodeClient

node = NodeClient("A", peer_port=6001, match_id="m1", attempt_id="a1")
node.start()
node.connect_lobby()
node.connect_mesh({"B": ("192.168.1.20", 6002)})
~~~

Os IDs e endpoints reais devem vir da preparação feita pelo lobby. O valor padrão demo serve apenas aos testes manuais.

A aplicação deve consumir get_event, que devolve um dicionário:

~~~python
event = node.get_event(timeout=0.1)

if event["kind"] == "message":
    message = event["message"]
    print(event["peer_id"], message)
elif event["kind"] == "disconnected":
    print(event["peer_id"], event["error"])
~~~

queue.Empty significa que não chegou evento no prazo. Os tipos são connected, message, disconnected e error. O evento deve ser tratado pela sessão; a thread de rede não deve alterar a arena.

send(peer_id, tipo, payload) cria o envelope, envia e devolve o ID da mensagem. broadcast envia a todos os pares e informa falhas por eventos. A sessão deve atualizar epoch conforme sua eleição e decidir o significado de cada payload.

Antes do registro, send("lobby", "REGISTER", payload, anonymous=True) usa sender_id=null. Após REGISTER_OK, a aplicação atribui o ID recebido a node.player_id antes de conectar os pares. O endpoint anunciado combina PEER_ADVERTISE_HOST com a porta real de node.server.getsockname().

disconnect(peer_id) fecha o socket e retira seu endpoint conhecido. Essa operação deve ocorrer por decisão da sessão; não modifica os votantes automaticamente. close encerra todas as conexões. Como send é síncrono, não há flush de fila local.

## Configuração e falhas

.env.example contém host/port do lobby, bind/endereço anunciado e porta do jogador. CLI tem precedência. Timeouts e limite de mensagem são constantes explícitas em config.py.

O transporte informa fechamento, erro de socket, JSON inválido ou falha de handshake. Silêncio no teclado não prova desconexão. Heartbeat, prazo sem atividade, duplicatas de operações e regras de época pertencem à sessão do jogo.

A fila de eventos não tem limite; a aplicação deve consumi-la regularmente. Não há autenticação criptográfica, retorno de processo reiniciado ou reconexão automática depois de encerrada a sessão.

Esta versão substitui as classes NetworkConfig, JsonConnection, TcpListener e NetworkEvent da implementação anterior. Os eventos agora são dicionários e o envio é direto. Os módulos da equipe devem utilizar a interface descrita nesta página.

## Testes

~~~bash
poetry run python -m unittest -v
~~~

Os testes verificam mensagens fragmentadas/agrupadas, Unicode, timeout parcial, fechamento, JSON inválido, envelope, limite, clientes simultâneos, recebimento espontâneo, malha de quatro nós, queda do lobby e envios concorrentes.

A execução usa sockets reais em loopback. A integração entre máquinas e os algoritmos do jogo precisam de testes próprios.
