# Camada de comunicação

Esta implementação fornece o transporte entre processos: conexões TCP, mensagens JSON completas, filas de envio, recebimento independente do teclado e conexão entre pares. Os arquivos estão completos e podem ser executados juntos.

Registro de jogadores, salas, colisões, histórico de jogo, votação e heartbeat da partida são regras de aplicação. Não estão implementados pelos programas de diagnóstico. O servidor de diagnóstico apenas devolve mensagens; ele não é um lobby funcional de salas.

## 1. Arquivos e responsabilidades

| Arquivo | Função |
|---|---|
| src/core/config.py | Configuração por ambiente/.env e limites locais |
| src/core/exceptions.py | Erros que a sessão pode capturar |
| src/core/protocol.py | JSON, LF, buffer, envelope e leitura de mensagens |
| src/core/transport.py | Escuta TCP e threads de leitura/escrita por conexão |
| src/lobby/server.py | Transporte do lobby e fila de eventos dos clientes |
| src/node/client.py | Conexão ao lobby, porta P2P e malha |
| src/lobby/__main__.py | Permite python -m src.lobby |
| src/node/__main__.py | Permite python -m src.node |
| tests/test_communication.py | Testes de enquadramento e rede real em loopback |

src/node/host.py não precisa receber código de rede: o host utiliza NodeClient como qualquer outro jogador. src/lobby/session.py recebe as regras de registro/salas da equipe responsável. Os identificadores connection-1, connection-2 do LobbyServer identificam sockets, não jogadores registrados.

## 2. Executar

O projeto exige Python 3.14 ou superior conforme seu pyproject.toml. A implementação utiliza recursos disponíveis também em 3.12; os testes locais foram executados em Python 3.12.14. A execução em 3.14 deve ser confirmada no ambiente da equipe.

Na raiz do repositório:

~~~bash
poetry install --no-root
~~~

A opção --no-root instala as dependências sem tentar empacotar o projeto. A execução abaixo usa os módulos src diretamente.

Copiar .env.example para .env é opcional. Argumentos de linha de comando substituem os valores de ambiente. No Windows, a cópia pode ser feita com Copy-Item; em Linux/macOS, com cp.

### Teste do lobby

Primeiro terminal:
~~~bash
poetry run python -m src.lobby
~~~

Segundo terminal:
~~~bash
poetry run python -m src.node --id A --peer-port 6001
~~~

Terceiro terminal:
~~~bash
poetry run python -m src.node --id B --peer-port 6002
~~~

No terminal de A ou B:
~~~text
/lobby Olá, lobby!
~~~

O servidor deve devolver ECHO com o mesmo payload. É uma mensagem de diagnóstico, não uma operação de sala. O recebimento acontece mesmo quando o teclado está parado. /quit encerra o processo; Ctrl+C também é aceito.

### Teste P2P sem lobby

Os dois terminais devem iniciar dentro do prazo MESH_TIMEOUT, cujo padrão é 15 s. Se o prazo acabar, reiniciar o teste ou aumentar esse valor.

Terminal A:
~~~bash
poetry run python -m src.node --id A --peer-port 6001 --no-lobby --peer B=127.0.0.1:6002
~~~

Terminal B:
~~~bash
poetry run python -m src.node --id B --peer-port 6002 --no-lobby --peer A=127.0.0.1:6001
~~~

Após o evento connected:
~~~text
/to B Mensagem de A para B
~~~

Em B:
~~~text
/to A Resposta de B
~~~

O comando /all envia aos pares conectados, sem incluir o lobby.

Para três ou quatro jogadores, cada linha deve incluir --peer para todos os outros. Por exemplo, A conhece B, C e D; B conhece A, C e D. Somente o menor ID de cada par inicia a conexão. A escuta ocorre em todos os jogadores.

### Máquinas diferentes

LOBBY_HOST deve indicar a máquina do servidor. Cada --peer deve usar o IP real do respectivo jogador. PEER_BIND_HOST pode ser 0.0.0.0; PEER_ADVERTISE_HOST precisa ser um endereço alcançável pelas outras máquinas. As portas precisam estar acessíveis na rede local.

NodeClient.advertised_endpoint fornece host anunciado e a porta real da escuta, inclusive quando a porta 0 foi usada para alocação automática em testes.

## 3. Caminho de uma mensagem

NodeClient.send cria o envelope e enfileira bytes. A thread de escrita faz sendall. A thread de leitura acumula bytes até LF, valida o JSON e o envelope e gera NetworkEvent. A sessão obtém esse evento por get_event.

Cada conexão tem um MessageReader. Seu buffer é um atributo do objeto, preservado entre leituras e até quando recv gera timeout. Assim, uma mensagem parcial não é esquecida.

Há somente uma thread lendo e uma escrevendo em cada socket. Vários produtores podem chamar send sem intercalar bytes ou repetir IDs. As threads não alteram o estado do jogo.

O limite físico inclui LF. A fila possui limite de quantidade e bytes. Se o destino não acompanha os envios, a conexão fecha e a aplicação recebe erro de fila cheia; não há descarte silencioso de registros.

O evento connected informa que a conexão está disponível. message contém um objeto Python. disconnected informa fechamento normal ou erro. error pode indicar falha do listener, handshake ou prazo de conexão da malha.

## 4. Interface para o restante do projeto

Exemplo mínimo de consumidor:

~~~python
import queue
from src.node.client import NodeClient

node = NodeClient("A")
node.start()

try:
    node.connect_lobby()
    node.send("lobby", "TEXT", {"text": "teste"})

    while True:
        try:
            event = node.get_event(timeout=0.1)
        except queue.Empty:
            continue

        if event.kind == "message":
            print(event.peer_id, event.message)
        elif event.kind == "disconnected":
            print("Conexão encerrada:", event.peer_id, event.error)
finally:
    node.close()
~~~

A sessão do jogo deve consumir os eventos e decidir seu efeito. O recebimento não espera input e não exige que o cliente tenha enviado uma solicitação primeiro.

### Registro e identidade

Antes de receber o player_id do lobby, a aplicação pode usar uma identidade temporária e enviar:

~~~python
request_id = node.send(
    "lobby",
    "REGISTER",
    {"nickname": "Ana", "peer_endpoint": node.advertised_endpoint},
    anonymous=True,
)
~~~

Quando a aplicação receber REGISTER_OK, deve chamar set_player_id com o ID atribuído. Isso só é permitido antes de conectar pares. O transporte não implementa a decisão de registro.

Depois de receber a lista oficial:
~~~python
node.set_peers({
    "B": ("192.168.1.20", 6002),
    "C": ("192.168.1.21", 6003),
})
node.connect_mesh()
~~~

A aplicação deve criar NodeClient com match_id e attempt_id recebidos da preparação, em vez dos valores "demo" usados pelo diagnóstico. O handshake verifica contexto, identidade conhecida e regra do iniciador; não usa autenticação criptográfica.

### Envio e contexto

- send(peer_id, tipo, payload) envia a um destino e devolve o ID da mensagem.
- send("lobby", ...) usa contexto de lobby.
- broadcast(tipo, payload) envia aos pares e devolve um mapa de falhas.
- epoch representa a época corrente informada pela sessão. O transporte não inicia eleição nem decide se uma época maior é válida.
- LobbyServer.send permite reply_to, match_id e attempt_id para respostas/notificações.
- get_event devolve o próximo evento; queue.Empty significa que não chegou evento no prazo.

Cada conexão possui IDs crescentes. A aplicação deve tratar correlação, repetição de operações e validade dos tipos/payloads específicos. A validação de envelope não implementa todas as regras do protocolo do jogo.

### Falha e fechamento

last_received_at(peer_id) permite consultar o instante monotônico de última mensagem válida. O transporte reporta erros do TCP; a sessão deve implementar heartbeat e suspeita por falta de atividade. Silêncio no teclado não é desconexão.

disconnect(peer_id, forget=True) fecha e remove o endpoint conhecido. Deve ser usado depois de uma decisão da sessão; isso não altera automaticamente os votantes.

flush espera a escrita local das mensagens enfileiradas. Não significa que o receptor confirmou sua aplicação. close cancela a comunicação e descarta pendências; na saída normal, a aplicação deve concluir seu protocolo, fazer flush e então fechar.

O fechamento do lobby remove somente essa conexão. A malha P2P continua disponível.

## 5. Configuração e limites

.env.example lista os valores utilizados. Timeouts de conexão limitam o estabelecimento/handshake. IO_TIMEOUT permite verificar fechamento entre leituras e limita uma escrita bloqueada. MESH_TIMEOUT limita tentativas de conexão dos pares.

MAX_MESSAGE_BYTES limita uma linha; MAX_PENDING_MESSAGES limita mensagens em envio; MAX_PENDING_BYTES limita os bytes pendentes. A fila de eventos da aplicação é uma queue.Queue sem limite: o consumidor deve drená-la regularmente. Um jogo que deixe de consumir eventos pode acumular memória.

Os IDs e endpoints de diagnóstico não substituem a configuração oficial fornecida pelo lobby. Não há reconexão automática de uma sessão encerrada nem reentrada de jogador; essas políticas pertencem à aplicação.

## 6. Verificação

~~~bash
poetry run python -m unittest -v
~~~

Os testes cobrem:
- Unicode, fragmentação e várias mensagens na mesma leitura;
- bytes parciais preservados após timeout;
- fechamento normal/incompleto;
- JSON inválido, chave duplicada, números não finitos e limite;
- três clientes no lobby e recebimento espontâneo;
- quatro nós em malha e mensagens nos dois sentidos;
- queda do lobby sem derrubar os pares;
- handshake inválido ou contexto errado;
- IDs sequenciais com envios concorrentes;
- fila cheia com erro explícito e desconexão única.

Os testes de rede utilizam sockets TCP reais em loopback. Eles não substituem a execução entre máquinas distintas, nem validam eleição, quorum ou regras do jogo.

## 7. Ordem para estudar o código

protocol.py mostra texto, bytes, delimitador e buffer. transport.py mostra como leitura e escrita deixam de bloquear o programa principal. server.py mostra o atendimento simultâneo; client.py acrescenta identificação e montagem da malha. Os testes demonstram os limites de cada comportamento.

A separação permite ao motor ignorar sockets: ele recebe comandos da sessão e devolve resultados. A sessão decide o que enviar e como tratar eventos de rede.
