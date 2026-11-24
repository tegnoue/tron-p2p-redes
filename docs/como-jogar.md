# Como jogar o Tron P2P

Este guia explica como iniciar o lobby e os jogadores, como jogar pelo terminal e como reproduzir os cenários de falha exigidos no trabalho.

## 1. Preparação

Requisitos: Python 3.14 (definido no `pyproject.toml`) e Poetry. Não é preciso instalar nada para a interface: o teclado e a tela usam apenas a biblioteca padrão (`termios`/`tty` no Linux e macOS, `msvcrt` no Windows).

Na raiz do projeto:

~~~bash
poetry install --no-root
~~~

Sem Poetry, basta `pip install python-dotenv` e trocar `poetry run python` por `python` nos comandos abaixo.

O terminal precisa de pelo menos **33 linhas e 110 colunas**. Maximize a janela antes de entrar na partida. No Windows, use o Windows Terminal ou o PowerShell (Windows 10 ou superior).

## 2. Iniciar o lobby

~~~bash
poetry run python -m src.lobby --host 0.0.0.0 --port 5000
~~~

| Opção | Padrão | Significado |
|---|---|---|
| `--host` | `127.0.0.1` | Endereço de escuta. Use `0.0.0.0` para aceitar outras máquinas |
| `--port` | `5000` | Porta do lobby |
| `--tick-ms` | `125` | Duração de um ciclo (125 ms = 8 ciclos por segundo) |
| `--width`, `--height` | `40`, `30` | Tamanho da arena |

Os valores da partida são definidos pelo lobby e enviados a todos os jogadores, então todos usam a mesma configuração.

## 3. Iniciar os jogadores

Um terminal por jogador (3 ou 4 jogadores):

~~~bash
poetry run python -m src.node --name ana  --peer-port 6001
poetry run python -m src.node --name bia  --peer-port 6002
poetry run python -m src.node --name caio --peer-port 6003
~~~

| Opção | Padrão | Significado |
|---|---|---|
| `--name` | obrigatório | Apelido mostrado no jogo |
| `--peer-port` | `6001` | Porta onde o jogador ouve os outros jogadores. Na mesma máquina, cada jogador usa uma porta diferente |
| `--lobby-host`, `--lobby-port` | `127.0.0.1`, `5000` | Endereço do lobby |
| `--bind-host` | `0.0.0.0` | Interface onde a porta P2P escuta |
| `--advertise-host` | IP visto pelo lobby | IP que os outros jogadores usarão para conectar a este |

As opções também podem vir de variáveis de ambiente ou de um arquivo `.env` (veja `.env.example`). A linha de comando tem prioridade.

### Em máquinas diferentes

1. Na máquina do lobby, descubra o IP da rede (`ip addr`, `ipconfig`), por exemplo `192.168.0.10`, e inicie o lobby com `--host 0.0.0.0`.
2. Em cada máquina, inicie o jogador com `--lobby-host 192.168.0.10`.
3. Por padrão, o lobby anuncia aos outros o IP de onde veio a conexão de cada jogador. Um jogador que rode na **mesma máquina do lobby** também deve usar `--lobby-host 192.168.0.10` (e não `127.0.0.1`), ou informar `--advertise-host 192.168.0.10`. Caso contrário, os outros receberiam `127.0.0.1`.
4. O firewall precisa liberar a porta do lobby e as portas P2P.

## 4. No lobby

A tela do lobby aceita comandos digitados seguidos de Enter:

| Comando | Efeito |
|---|---|
| `listar` | Mostra as salas, quantos jogadores têm e o estado |
| `criar NOME` | Cria uma sala; quem cria é o **criador** e será o **host** da partida |
| `entrar ID` | Entra na sala pelo número mostrado em `listar` (ex.: `entrar 1`) |
| `sair` | Sai da sala; se o criador sair, o jogador mais antigo assume |
| `iniciar` | Somente o criador, com 3 ou 4 jogadores na sala |
| `fim` | Fecha o programa |

Exemplo com três jogadores: ana digita `criar sala1`, bia e caio digitam `entrar 1`, e ana digita `iniciar`.

## 5. Na partida

Ao iniciar, cada jogador conecta-se diretamente aos outros e avisa o host que está pronto. Isso é automático. Depois há uma **contagem de 3 segundos**, e as motos começam a andar sozinhas.

| Tecla | Ação |
|---|---|
| `W` | Cima |
| `A` | Esquerda |
| `S` | Baixo |
| `D` | Direita |
| `q` | Sair da partida (os outros veem sua moto ser eliminada) |

Não é preciso apertar Enter. Inverter o sentido (por exemplo, `A` indo para a direita) é ignorado. Dá para apertar duas curvas seguidas: elas acontecem em dois ciclos consecutivos. As teclas já funcionam durante a contagem, para preparar a primeira curva.

### A tela

~~~text
+----------------------------------------+   Fase: JOGANDO
|                                        |   Ciclo: 21
|   aaaaaaaaaaaaaaaaaaaaaA           b   |
|                                    b   |   A ana [host]: vivo
|                               Bbbbbb   |   B bia [você]: vivo
|                                        |   C caio: eliminado (parede)
|               Xcccccccccccc            |
+----------------------------------------+   Eventos: ...
~~~

- Letra maiúscula: a moto (A, B, C, D, uma cor por jogador).
- Letra minúscula: o rastro daquela moto.
- `X`: moto eliminada (o rastro continua na arena).
- À direita: fase, ciclo, situação de cada jogador (`[você]`, `[host]`) e os últimos eventos.

Uma moto é eliminada ao bater na parede, em qualquer rastro, ou ao entrar na mesma célula que outra moto (as duas saem). Vence o último sobrevivente. Se os últimos forem eliminados no mesmo ciclo, é empate. Quem foi eliminado continua assistindo até o fim.

No fim, a tela mostra o resultado global e o seu (`VOCÊ VENCEU!`, `EMPATE!` ou `Você perdeu.`). **Enter** volta ao lobby; **q** sai.

## 6. Cenários de falha (para a demonstração)

| Cenário | Como reproduzir | Comportamento esperado |
|---|---|---|
| Jogador cai | Durante a partida, aperte `q` ou feche o terminal de um jogador que não é host (ou `kill -9` no processo) | O host elimina a moto com motivo "desconexão"; a partida continua para os outros |
| Jogador trava sem fechar a conexão | Pause o processo (`kill -STOP PID`) | Sem mensagens por 3 s, o host considera falha e elimina a moto |
| Host cai | Feche o terminal do host (ou `kill -9`) | Todos veem "O host caiu. Partida encerrada para todos." Ninguém fica travado |
| Lobby cai | Encerre o lobby (Ctrl+C ou `kill -9`) durante a partida | Aparece "Conexão com o lobby perdida. A partida continua." e o jogo termina normalmente |
| Queda durante a contagem | Feche um jogador durante os 3 s da contagem | A moto é eliminada no primeiro ciclo e a partida segue |
| Queda antes de todos estarem prontos | Um jogador cai enquanto as conexões P2P são montadas (ou não fica pronto em 20 s) | O host cancela a partida para todos (`ABORT`) |

Para ver as falhas com calma, use ciclos mais lentos: `poetry run python -m src.lobby --tick-ms 300`.

## 7. Testes automáticos

~~~bash
poetry run python -m unittest -v
~~~

- `tests/test_arena.py`: regras do motor (paredes, rastros, colisão frontal, troca de posições, empate, desconexão).
- `tests/test_lobby.py`: registro, salas, limite de 4, só o criador inicia, troca de criador.
- `tests/test_match.py`: partidas reais com 3 processos lógicos em sockets locais (partida completa, queda de jogador, queda do host, queda do lobby).
- `tests/test_communication.py`: camada de comunicação.

Para testar só o lobby com mensagens escritas à mão (inclusive inválidas), use o cliente de teste:

~~~bash
poetry run python -m scripts.cliente_teste --port 5000
~~~

## 8. Mensagens usadas pelo jogo (resumo)

Todas as mensagens são JSON terminado por `\n`, com o envelope de `src/core/protocol.py`.

| Mensagem | De → para | Payload |
|---|---|---|
| `REGISTER` / `REGISTER_OK` | jogador ↔ lobby | `{nickname, peer_endpoint:{host,port}}` / `{player_id}` |
| `LIST_ROOMS`, `CREATE_ROOM`, `JOIN_ROOM`, `LEAVE_ROOM`, `START_MATCH` (+ `_OK`) | jogador ↔ lobby | conforme a tabela do lobby em `protocolo.md` |
| `ROOM_UPDATED` | lobby → jogadores da sala | `{room}` |
| `MATCH_CONFIG` | lobby → jogadores | `{config: {match_id, attempt_id, host_id, members, width, height, tick_ms, spawns}}` |
| `PEER_HELLO` / `PEER_HELLO_OK` | jogador ↔ jogador | identificação da conexão P2P |
| `READY` | jogador → host | `{}`: conexão com o host pronta |
| `COUNTDOWN` | host → todos | `{duration_ms: 3000}` |
| `MOVE` | jogador → host | `{direction: UP/DOWN/LEFT/RIGHT}` |
| `CYCLE` | host → todos | `{cycle, bikes, new_cells, eliminations, result}` |
| `MATCH_OVER` | host → todos | `{result}` |
| `ABORT` | host → todos | `{reason}`: cancelamento antes do início |
| `HEARTBEAT` | todos → todos, a cada 1 s | `{}`: detecção de falha por silêncio (3 s) |
| `ERROR` | qualquer | `{code, message}` |

Somente o host calcula os ciclos com o motor (`src/game/engine.py`). Os demais apenas aplicam os `CYCLE` recebidos, na ordem garantida pelo TCP. Por isso todos chegam ao mesmo resultado.
