# Implementação em 11 dias

Objetivo: integrar cedo e reservar tempo para falhas e execução em máquinas distintas. Os comandos abaixo são a interface a construir, não código já disponível.

## 1. Plano de trabalho

| Dias | Entrega | Critério de conclusão |
|---|---|---|
| 1–2 | Codec TCP, configuração, lobby e motor isolado | Mensagens fragmentadas funcionam; salas e colisões testadas |
| 3–4 | Malha, RTT, READY, teclado e host fixo | Partida com três/quatro processos, inclusive em máquinas distintas |
| 5–6 | Histórico, ACK, confirmação e filas | Ciclos aplicados uma vez; expiração e limpeza corretas |
| 7–8 | Eleição, recuperação e snapshot | Queda antes/depois de quorum preserva prefixo confirmado |
| 9 | Reconfiguração e transferência | Saída voluntária e mudança de votantes sem quorum local inventado |
| 10–11 | Integração, medições e apresentação | Encerramento, lobby ausente e cenários de falha demonstrados |

Não esperar a interface completa para testar rede. Não começar eleição antes de explicar comando, ciclo, registro, posição e época.

## 2. Ambiente e organização

Python + Poetry. Usar socket, selectors ou threads, queue, json, hashlib, uuid, time e unittest. Rich/python-dotenv podem auxiliar; não substituir o protocolo por framework de multiplayer ou RPC.

Interface desejada:
~~~bash
poetry install
poetry run python -m src.lobby
poetry run python -m src.node --name Ana --peer-port 6001
~~~

Repetir o último comando com outros nomes/portas. Precedência: argumento CLI → variável de ambiente → padrão.

~~~dotenv
LOBBY_HOST=127.0.0.1
LOBBY_PORT=5000
PEER_BIND_HOST=0.0.0.0
PEER_ADVERTISE_HOST=127.0.0.1
PEER_PORT=6001
~~~

Em máquinas distintas, usar IPs reais alcançáveis. Lobby também aceita bind configurável; processos na mesma máquina usam portas diferentes.

| Diretório | Arquivos sugeridos |
|---|---|
| core | config, codec, messages, hashing, types |
| lobby | server, rooms, __main__ |
| game | state, engine |
| node | network, session, commands, replication, election, membership, ui, __main__ |
| tests | codec, engine, commands, replication, election, membership, scenarios |

Nomes são orientação; evitar monólitos e abstrações prematuras. Um laço de sessão é dono dos dados; rede/teclado entregam MESSAGE, KEY, SOCKET_CLOSED, TIMER e USER_ACTION por filas. Serializar escritas por conexão. Fila acima de MAX_SEND_QUEUE_BYTES gera falha de par lento, nunca descarte silencioso de registro.

## 3. Núcleo da implementação

### Transporte

~~~python
def encode_message(message):
    text = json.dumps(message, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)
    return text.encode("utf-8") + bytes([10])
~~~

No decoder: acumular bytes → extrair LF → validar limite → decodificar/validar → entregar mensagens → preservar sobra. Nunca usar json.loads(conn.recv(1024)).

### Motor e comandos

Estado sugerido: occupied[(x,y)] = owner_id; bikes[player_id] = Bike; cycle e result. step não conhece rede.

Cliente: validar tecla/fase → conferir duas pendências → criar sequência/referência → guardar e enviar.
Host: validar → reservar primeiro ciclo livre → rejeitar/resetar se idade >= 3 → guardar e responder.
Ao aplicar CYCLE confirmado, atualizar arena e remover os CommandRef executados. MOVE_ACCEPTED não libera espaço.

Cada fila do host guarda versão, espera de reset ACK, sequência e até duas reservas. Mensagens antigas não recriam comandos.

### Histórico

Guardar current_epoch, voted_for, leader_id, log, commit_index, last_applied, configuração e, no host, next_index/match_index por par.

Líder: criar registro encadeado → guardar → distribuir → validar ACKs → confirmar se registro atual e quorum correto → aplicar e anunciar.
Receptor: validar líder/época/prefixo → tratar somente conflito provisório → guardar → responder → aplicar apenas o confirmado.

Não contar “três respostas” sem conferir IDs, hash, época e configuração. Configuração aplicada e conservadora têm funções distintas; veja [protocolo](protocolo.md).

### Tempo e diagnóstico

Usar time.monotonic_ns e deadlines, sem sleep de 3 s no laço de rede. Abrir teclado em t0+2500 ms, terminar em t0+3000 ms. Round antigo não reinicia timers. Ciclo atrasado não gera rajada para compensar.

Logar event, match_id, player_id, epoch, index, cycle e config_version. Medir no cliente tecla→execução oficial; no host recepção→reserva→cálculo→quorum. Não subtrair relógios de máquinas diferentes.

## 4. Testes indispensáveis

| Área | Casos |
|---|---|
| Codec | Fragmentação em qualquer byte, várias mensagens juntas, UTF-8 dividido, linha inválida/grande, recv vazio sem laço infinito |
| Lobby | Quinta entrada concorrente, duas salas por jogador, início por não criador/com dois jogadores, JOIN em PREPARANDO, herança do criador, cancelar/reabrir, queda mesmo com três restantes |
| Motor | Uma célula/ciclo, inversão, ocupação anterior, destinos iguais, troca de posições, rastro de morto, parede sem célula inválida, empate, ordem dos IDs irrelevante, PLAYER_LEFT sem mover demais |
| Comandos | Duas curvas na mesma referência, fila cheia, expiração, ACK de aceitação sem liberar capacidade, limpeza com mensagens antigas em trânsito |
| Replicação | Lacuna, ACK duplicado/errado, registro provisório, imutabilidade confirmada, aplicação única, confirmação do prefixo por entrada atual |
| Eleição | Um voto/época, frescor igual/menor, época nova sem reescrever log, autoridade antiga, isolamento do host, candidato ausente, prazo total |
| Configuração | 4→3 e 3→2; duas maiorias até final; versão antiga não relaxa; uma transição; falha no meio; dois votantes/uma falha encerra |
| Encerramento | Terminal confirmado, cliente atrasado antes do ACK, todos da sessão, timeout sem entrega, saída prematura, host cai na entrega, lobby ausente e resultado preservado |

Injetar queda do host: antes de distribuir; após um destinatário; após quorum; após anúncio parcial; durante snapshot; primeiros 2,5 s; janela de 500 ms; transferência. Comparar posições confirmadas comuns entre processos: conteúdos não podem diferir.

Um simulador com fila de mensagens permite atrasar/entregar eventos de forma reproduzível. Complementar com sockets reais; matar processo aleatoriamente não cobre todos os pontos.

## 5. Demonstração e entrega

Demonstrar: três processos; quarto entra/quinto recusa; criador e READY; janela final; colisão simultânea; lobby desligado; saída comum; queda do host; transferência voluntária; falta de quorum; encerramento com lobby ausente.

Cada integrante deve explicar framing/timeout, fila e reserva, cálculo simultâneo, os cinco termos do glossário, aceito × armazenado × confirmado × aplicado, ranking × voto, recuperação e limite do quorum.

Concluir com testes de módulos e falhas, execução entre máquinas, métricas de atraso, comandos realmente disponíveis e documentação alinhada ao código. Calibrar valores com evidências; mudar capacidade/idade exige revisar reservas e testes. A documentação não substitui essa validação.
