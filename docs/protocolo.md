# Protocolo de aplicação TAPP — versão 1

Este é o contrato inicial de implementação do Tron P2P. Define mensagens, tipos, estados e ações. Os valores padrão são pontos de partida para testes. Mudanças de campos ou semântica precisam atualizar todos os processos e a versão quando houver incompatibilidade.

O protocolo é específico para a partida. Sua segurança depende do conjunto das regras, especialmente voto único por época, prefixo do histórico, confirmação na época atual e configuração conjunta. Não é suficiente implementar apenas os exemplos JSON.

## 1. Convenções

- Transporte: TCP; codificação: UTF-8; uma mensagem JSON por linha, terminada por LF.
- Não inserir LF físico no JSON; escapar dentro de strings.
- Receptor acumula bytes e separa linhas antes de decodificar.
- JSON com chaves duplicadas, NaN ou infinito é inválido.
- Campo desconhecido: rejeitar com INVALID_MESSAGE, salvo objeto explicitamente definido como mapa.
- Campos opcionais são indicados por "?"; se ausentes, usam o padrão informado.
- Não converter strings em números nem aceitar booleano onde se exige inteiro.
- IDs são strings opacas não vazias, até 64 caracteres; nickname até 24 e nome da sala até 48.
- Hash: SHA-256 hexadecimal minúsculo, 64 caracteres.
- Coordenadas e contadores são inteiros; tempos em milissegundos, RTT em microssegundos.
- Arrays de IDs não admitem duplicatas.
- Limite físico de linha: 1.048.576 bytes, incluindo LF. Linha maior fecha a conexão e gera diagnóstico.
- Timeout e erro de TCP geram suspeita; não alteram sozinhos os votantes.

### 1.1. Envelope

Todos os campos abaixo estão presentes:

~~~json
{
  "version": 1,
  "type": "MOVE_INTENT",
  "id": 17,
  "reply_to": null,
  "sender_id": "p1",
  "match_id": "m1",
  "attempt_id": "a1",
  "epoch": 2,
  "payload": {
    "queue_version": 0,
    "command_seq": 7,
    "reference_cycle": 42,
    "direction": "UP"
  }
}
~~~

| Campo | Regra |
|---|---|
| version | Inteiro 1 |
| type | Nome exato da mensagem |
| id | Inteiro positivo crescente por emissor em cada conexão |
| reply_to | ID da mensagem respondida ou null |
| sender_id | ID do jogador, "lobby" para servidor, null em REGISTER |
| match_id / attempt_id | IDs do contexto ou null fora de uma tentativa |
| epoch | Época corrente do emissor; null em mensagens de lobby, 0 no estabelecimento P2P antes da configuração |
| payload | Objeto definido nas tabelas seguintes |

A resposta tem seu próprio id e referencia o pedido em reply_to. Eventos usam reply_to=null. O mesmo id pode existir em conexões diferentes.

Para repetição de uma solicitação na mesma conexão, reutilizar sua mensagem inteira. Guardar as últimas 256 respostas; responder novamente sem executar a operação. Um id antigo fora desse cache recebe STALE_REQUEST. Para eventos/respostas duplicados, não repetir seus efeitos.

sender_id é confrontado com a conexão identificada por REGISTER ou PEER_HELLO. O campo não permite agir em nome de outro jogador. Não há autenticação criptográfica nesta versão.

### 1.2. Tratamento comum

1. Validar limite, UTF-8, JSON, envelope e payload.
2. Conferir identidade, partida e tentativa.
3. Descartar contexto antigo com STALE_CONTEXT, sem mudar estado.
4. Em mensagens do consenso, processar época antes da ação específica somente se o emissor ainda for elegível na configuração conservadora. Observador/removido não aumenta a época dos votantes.
5. Conferir estado e papel permitidos.
6. Executar a transição em um único laço de sessão.
7. Responder ou registrar o evento.

Erro bem formado:

~~~json
{
  "version": 1,
  "type": "ERROR",
  "id": 12,
  "reply_to": 6,
  "sender_id": "lobby",
  "match_id": null,
  "attempt_id": null,
  "epoch": null,
  "payload": {
    "code": "NOT_ENOUGH_PLAYERS",
    "message": "São necessários três ou quatro participantes."
  }
}
~~~

JSON malformado sem id recuperável: ERROR com reply_to=null e fechar. Erros semânticos de uma mensagem válida mantêm a conexão, salvo conflito confirmado ou identidade inconsistente.

Códigos: INVALID_MESSAGE, UNSUPPORTED_VERSION, INVALID_STATE, INVALID_SENDER, STALE_REQUEST, STALE_CONTEXT, STALE_EPOCH, ALREADY_REGISTERED, ALREADY_IN_ROOM, ROOM_NOT_FOUND, ROOM_FULL, ROOM_NOT_JOINABLE, NOT_ROOM_CREATOR, NOT_ENOUGH_PLAYERS, PREPARATION_ACTIVE, PEER_UNREACHABLE, CONFIG_MISMATCH, LOG_GAP, LOG_CONFLICT, CONFIRMED_LOG_CONFLICT, NO_QUORUM.

message explica o problema para o usuário; o código orienta o programa.

## 2. Tipos compartilhados

### 2.1. Endpoint, jogador e sala

- Endpoint = {host: string, port: inteiro de 1 a 65535}.
- Member = {player_id: ID, nickname: string, endpoint: Endpoint}.
- Room = {room_id: ID, room_version: inteiro positivo, name: string, state: enum, creator_id: ID, players: array de Member, min_players: 3, max_players: 4}.
- RoomSummary = {room_id, name, state, player_count: inteiro, max_players: 4}.
- state da sala: AGUARDANDO, PREPARANDO, EM_PARTIDA ou FINALIZADA.

players é ordenado por entrada. O presente mais antigo herda o controle da sala. A representação completa é distribuída apenas aos integrantes; a listagem usa resumos.

### 2.2. Direções e arena

Direções: UP=(0,-1), DOWN=(0,1), LEFT=(-1,0), RIGHT=(1,0).

Origem (0,0) no canto superior esquerdo; x cresce à direita e y para baixo.

Cell = {x: inteiro, y: inteiro, owner_id: ID}.
Bike = {player_id: ID, x: inteiro, y: inteiro, direction: enum, alive: booleano}.
CommandRef = {player_id: ID, epoch: inteiro, queue_version: inteiro, command_seq: inteiro}.

Posição fora da arena só aparece em attempted_x/attempted_y de um evento, nunca na matriz.

### 2.3. Resultado

Result = {status: "ONGOING" | "WINNER" | "DRAW", winner_id: ID|null, finalists: array de ID}.

ONGOING usa winner_id=null e finalists=[].
WINNER usa um winner_id e finalists=[vencedor].
DRAW usa winner_id=null; finalists são as motos vivas no início do evento que eliminou as últimas.

Quem foi eliminado antes continua com derrota individual.

### 2.4. Configuração inicial

MatchConfig contém exatamente:

- members: array de três ou quatro Member.
- ranking: permutação dos IDs de members.
- rtt_scores_us: mapa player_id → inteiro não negativo.
- width, height: inteiros entre 15 e 50.
- spawns: array de {player_id,x,y,direction}, um por participante.
- settings: objeto da tabela de parâmetros da seção 16.
- initial_voters: IDs de members.
- config_version: 1.

O lobby sorteia uma permutação de jogadores para os pontos:
(3,3,RIGHT), (width-4,height-4,LEFT), (width-4,3,DOWN), (3,height-4,UP).
Com três jogadores, usar os três primeiros pontos. Gravar o resultado, não exigir que cada cliente reproduza o sorteio.

### 2.5. Serialização para hashes

Use JSON canônico para os objetos que entram em hash:

~~~python
json.dumps(
    objeto,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
).encode("utf-8")
~~~

Não incluir floats no histórico. RTT permanece inteiro em microssegundos.

Arrays que representam conjuntos são ordenados: IDs lexicograficamente; células por (y,x,owner_id); motos por player_id.

config_hash = SHA256(JSON canônico de MatchConfig).

## 3. Lobby

O lobby serializa alterações de salas para impedir quinta entrada ou início concorrente. O estado de conexão antes de REGISTER não permite outras operações.

Nesta tabela, "objeto vazio" significa {}. Respostas de sucesso usam reply_to do pedido.

| Pedido e payload | Resposta e payload | Estado/efeito |
|---|---|---|
| REGISTER {nickname, peer_endpoint: Endpoint} | REGISTER_OK {player_id} | Conexão ainda não registrada; cria ID UUID e sessão |
| LIST_ROOMS {} | LIST_ROOMS_OK {rooms: array de RoomSummary} | Registrado; não muda participação |
| CREATE_ROOM {name} | CREATE_ROOM_OK {room: Room} | Fora de sala; criador entra automaticamente |
| JOIN_ROOM {room_id} | JOIN_ROOM_OK {room: Room} | Fora de sala, destino AGUARDANDO e com vaga |
| LEAVE_ROOM {} | LEAVE_ROOM_OK {} | Antes de iniciar; remove e atualiza criador |
| START_MATCH {} | START_MATCH_OK {match_id, attempt_id} | Criador, 3–4 jogadores; congela e inicia tentativa |
| CANCEL_PREPARATION {} | CANCEL_PREPARATION_OK {} | Criador em PREPARANDO; reabre AGUARDANDO |
| MATCH_STATUS {status, start_index: inteiro|null} | MATCH_STATUS_OK {} | Host informa RUNNING ou FINISHED; atualização administrativa |

Cada nova tentativa usa novos match_id e attempt_id. Pode haver histórico de tentativa cancelada somente para diagnóstico; o aplicativo descarta sua sessão P2P.

Notificações:

| Tipo | Payload | Ação |
|---|---|---|
| ROOM_UPDATED | {room: Room} | Substituir somente se room_version maior |
| PREPARE_MATCH | {members, creator_id, settings, width, height} | Abrir/identificar malha; envelopes contêm a tentativa |
| MATCH_CONFIG | {config: MatchConfig, config_hash} | Validar, criar registro inicial e preparar READY |
| PREPARATION_CANCELLED | {reason: string, room: Room} | Invalidar tentativa e contagem; manter sala PREPARANDO |
| ROOM_CLOSED | {room_id, reason} | Limpar sala e voltar ao lobby |

Antes do primeiro movimento, qualquer falha detectada cancela a tentativa. O ponto lógico que impede cancelamento por um relato atrasado é a confirmação do registro START, imediatamente antes do primeiro CYCLE. Depois desse ponto, aplicar falha da partida, mesmo que um cliente atrasado ainda não tenha visto o movimento.

O lobby não cancela uma tentativa que possa ter START confirmado apenas porque um cliente desconhece seu estado: consulta o host/participantes. Se não for possível determinar o estado, bloqueia reutilização daquela tentativa e permite encerramento controlado; não reutiliza seus IDs.

Após START confirmado, MATCH_STATUS não é requisito para continuar. Queda da conexão de lobby não elimina jogador de uma partida iniciada.

## 4. Conexões e RTT

| Tipo | Payload | Resposta/ação |
|---|---|---|
| PEER_HELLO | {player_id, initiated_by: ID} | PEER_HELLO_OK {} depois de confrontar roster |
| RTT_PING | {sample_id: inteiro de 0 a 4} | RTT_PONG com mesmo sample_id |
| RTT_PONG | {sample_id} | Emissor calcula RTT com relógio monotônico |
| RTT_REPORT | {measurements: array de Measurement} | Lobby armazena relatório da tentativa |
| PREPARE_FAILED | {peer_id: ID|null, reason} | Lobby cancela tentativa se ainda não houve START |

Measurement = {peer_id, samples_us: array de cinco inteiros não negativos}.
Cada jogador reporta todos os outros exatamente uma vez. Tempo máximo por amostra: rtt_sample_timeout_ms. Qualquer amostra ausente cancela a tentativa; não atribuir RTT zero.

score(p) = soma de todas as amostras reportadas por p / quantidade de amostras, com divisão inteira. Ordenar por (score, player_id). A medição pode ser assimétrica; cada score usa os RTTs medidos pelo próprio candidato.

Conexão duplicada: manter somente a iniciada pelo menor ID. Uma conexão não identificada expira após hello_timeout_ms.

READY {config_hash, last_index: 0, last_hash: hash de INIT} é enviado automaticamente ao primeiro do ranking. Ao aceitar a configuração, cada jogador inicia current_epoch=1 e voted_for=primeiro do ranking.

O host espera READY de todos, confirma EPOCH_START e faz a sincronização inicial. READY não é um botão da interface.

## 5. Histórico e registros

### 5.1. Estrutura

~~~json
{
  "index": 58,
  "epoch": 2,
  "kind": "CYCLE",
  "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "payload": {
    "cycle": 43,
    "moves": [],
    "bikes_after": [],
    "added_cells": [],
    "eliminations": [],
    "result": {
      "status": "ONGOING",
      "winner_id": null,
      "finalists": []
    }
  },
  "hash": "0000000000000000000000000000000000000000000000000000000000000000"
}
~~~

Esse exemplo mostra a forma, não uma cadeia válida nem um ciclo completo. Os hashes de exemplos isolados precisam ser calculados com seus predecessores.

hash = SHA256(JSON canônico do objeto sem o campo hash). prev_hash é o hash da posição anterior.

Registro INIT é a posição 0, época 0, prev_hash de 64 zeros e payload={config,config_hash}. É a âncora comum; commit_index=last_applied=0.

Não truncar o histórico nesta versão. Snapshots não removem registros.

### 5.2. Tipos e payloads exatos

| kind | Payload |
|---|---|
| INIT | {config: MatchConfig, config_hash} |
| EPOCH_START | {leader_id, config_version: inteiro} |
| START | {round_id: ID, cycle: 0, config_hash} |
| CYCLE | {cycle, moves, bikes_after, added_cells, eliminations, result} |
| PLAYER_LEFT | {player_id, reason: "VOLUNTARY"|"FAILURE", cycle, bikes_after, result} |
| CONFIG_JOINT | {version, old: array de ID, new: array de ID} |
| CONFIG_FINAL | {version, joint_index, voters: array de ID} |

moves é array de {player_id: ID, command: CommandRef|null, direction, target_x, target_y}, um por moto viva no início do movimento. command=null indica direção mantida sem novo comando.

eliminations é array de {player_id, reason: "WALL"|"TRAIL"|"HEAD_ON", attempted_x, attempted_y}.
bikes_after contém todas as motos, inclusive eliminadas. added_cells é array de Cell novas, sem duplicatas; em colisão entre donos na mesma célula, owner_id é o menor ID envolvido, apenas para representação.

CYCLE sempre é cycle aplicado + 1. Validar seu resultado recalculando step a partir do estado anterior. Motivos de colisão seguem prioridade WALL, depois TRAIL, depois HEAD_ON; isso evita motivos diferentes para o mesmo estado. Para destino interno, armazenar a posição tentada mesmo se eliminada; para WALL, manter a última posição válida. Se houver divergência, não confirmar o registro; iniciar diagnóstico e interromper, pois maioria não corrige motor inconsistente.

PLAYER_LEFT é aplicado entre movimentos, com cycle igual ao último ciclo aplicado. Mantém posições/rastros, marca a moto morta e recalcula resultado. Não permite reaparecimento de jogador removido.

START usa round_id somente para o início. Retomadas usam round_id novo nos eventos de sincronização, sem reiniciar o número de ciclo.

### 5.3. Invariantes

- index cresce de um em um.
- Registros confirmados são imutáveis.
- Igual index e epoch exigem igual hash.
- Cada registro só é aplicado uma vez.
- last_applied <= commit_index <= last_index.
- Comparação de frescor usa (last_log_epoch,last_log_index), nunca cycle.
- current_epoch é a época eleitoral; não altera epoch dos registros existentes.

## 6. APPEND e confirmação

### 6.1. Mensagens

| Tipo | Payload |
|---|---|
| APPEND | {config_version, prev_index, prev_epoch, prev_hash, entries: array de Record, leader_commit} |
| APPEND_RESULT | {ok: booleano, match_index: inteiro, match_hash: hash, next_index: inteiro, reason: string|null, config_version} |
| COMMIT | {commit_index, commit_hash, config_version} |
| LOG_STATUS_REQUEST | {} |
| LOG_STATUS | {last_index, last_epoch, last_hash, commit_index, commit_hash, config_version} |
| LOG_FETCH | {from_index, max_entries: inteiro de 1 a 64} |
| LOG_BATCH | {entries: array de Record, next_index, done: booleano} |

Record é o objeto da seção 5. APPEND e LOG_BATCH devem caber no limite físico; reduzir lote antes de serializar.

Uma versão de configuração superior no APPEND pode ser introduzida pelas próprias entradas recebidas; validar a transição em ordem, sem rejeitar só por o número ser novo. Não relaxar a regra conservadora por um número menor.

APPEND vazio também mantém contato e propaga leader_commit. COMMIT acelera o anúncio, mas não é a única forma de aprender a confirmação.

### 6.2. Receptor

1. Conferir época e líder: APPEND só é autoridade do líder reconhecido nessa época.
2. Localizar prev_index e conferir epoch/hash.
3. Se não existir ou não corresponder, responder ok=false e sugerir next_index menor.
4. Para cada entrada, conferir index, prev_hash e hash.
5. Entrada já idêntica é ignorada, sem novo efeito.
6. Se index e epoch coincidirem mas o hash diferir, interromper por inconsistência. Um líder não pode produzir dois conteúdos para a mesma posição e época. Nos demais conflitos provisórios, apagar o sufixo a partir da posição e acrescentar a sequência do líder.
7. Em conflito numa posição confirmada, emitir CONFIRMED_LOG_CONFLICT e abortar após verificação.
8. Responder ok=true somente depois de atualizar o histórico em memória. match_index é a última posição comprovadamente correspondente ao APPEND, não um sufixo local extra.
9. Avançar confirmação somente até min(leader_commit, último índice que corresponde ao prefixo enviado/validado). Não confirmar um sufixo local desconhecido pelo líder.

Se apenas faltar prefixo, não abortar: solicitar sincronização.

LOG_BATCH serve para diagnóstico e atualização de candidato. Não dá autoridade para substituir prefixo confirmado nem para instalar um sufixo conflitante antes da eleição. O candidato pode acrescentar um prefixo comprovadamente compatível; caso contrário, espera outro candidato.

### 6.3. Líder

Guardar next_index e match_index por par. APPEND_RESULT só conta para a época corrente e para hash correspondente ao histórico local. Não contar resposta duplicada.

Para avançar commit_index até N:

- O registro N é da época atual.
- Há armazenamento da sequência até N pelo quorum exigido.
- A regra de quorum considera qualquer transição de configuração no prefixo que está sendo confirmada.

O ACK do próprio líder é sua cópia em memória. Não aguardar tick para enviar resposta, nem todos para obter maioria.

Se N for confirmado, seu prefixo também é. Isso preserva registros antigos recuperados quando EPOCH_START da nova época é replicado.

## 7. Eleição

### 7.1. Contexto e fila

epoch começa em 1. O candidato previsto para E é ranking[(E-1) % len(ranking)]. Se não estiver na configuração conservadora corrente, pular aquela época. Não recalcular ranking por observações locais.

A configuração conservadora é:
- configuração simples vigente, se não existe transição armazenada;
- união da antiga e nova para elegibilidade e as duas maiorias para votação, a partir do armazenamento de CONFIG_JOINT;
- nova simples somente depois de CONFIG_FINAL confirmado.

### 7.2. Mensagens

| Tipo | Payload |
|---|---|
| ELECTION_NOTICE | {suspected_leader_id, reason} |
| REQUEST_VOTE | {candidate_id, last_log_index, last_log_epoch, last_log_hash, config_version} |
| VOTE | {candidate_id, granted: booleano, reason: string|null, config_version} |
| LEADER | {leader_id, voters: array de ID, config_version} |
| TRANSFER_REQUEST | {target_id, reason: "VOLUNTARY"} |

epoch no envelope identifica a tentativa. LEADER contém IDs dos votos obtidos; os destinatários confrontam com os votos e participantes conhecidos. No modelo sem fraude, é anúncio do resultado, não certificado criptográfico.

### 7.3. Regras de época e voto

Uma mensagem eleitoral de época maior, de participante válido, faz:
current_epoch = recebida; voted_for = null; role = FOLLOWER; state = SINCRONIZANDO; bloquear teclado.
Não modificar registros por causa dessa mudança.

Mensagens menores recebem STALE_EPOCH. Na mesma época, não votar novamente em outro candidato.

Conceder voto se:
- candidate_id é o previsto e ainda elegível;
- pedido está na época corrente;
- configuração é compatível; se o receptor possui transição mais restritiva, ela precisa ser satisfeita;
- voted_for é null ou o próprio candidato;
- (last_log_epoch,last_log_index) do candidato >= a dupla local.

Se a dupla for igual e hashes diferentes, negar por LOG_CONFLICT e investigar. A verificação do prefixo ocorre na replicação; não basta um número alto.

Guardar voted_for antes de enviar VOTE. Um voto negado por atraso inclui LOG_STATUS em mensagem separada para permitir atualização.

### 7.4. Tentativas e vencedor

Após host_timeout_ms sem atividade válida do líder:
- pausar simulação e limpar filas;
- avançar época para o próximo slot elegível e enviar ELECTION_NOTICE;
- o candidato previsto consulta metadados e pede votos;
- se estiver atrás e não conseguir atualizar prefixo compatível, deixa expirar e avança o slot;
- após election_slot_ms, sem vencedor, avançar novamente;
- após election_total_ms sem recuperação, ABORT_NOTICE e encerramento local controlado.

Receber uma época maior atualiza o slot, mas não reinicia o prazo total do mesmo episódio de falha. A evidência de progresso pode reiniciar o prazo somente quando EPOCH_START é confirmado.

Ao obter quorum, anunciar LEADER, reconciliar os logs e acrescentar EPOCH_START. Não gerar CYCLE antes de confirmar esse registro e sincronizar os participantes. Se recuperar resultado terminal, seguir diretamente sua entrega e fechamento, sem contagem ou novos movimentos.

## 8. Configuração dos votantes

Apenas remoções são permitidas durante a partida; não há adição ou reentrada.

quorum(V, A) = quantidade de IDs distintos em V interseção A >= floor(len(V)/2)+1.

Na fase conjunta, quorum é verdadeiro nas duas listas separadamente. O mesmo ID pode contar nas duas.

CONFIG_JOINT versão v+1:
- old igual à configuração simples atual;
- new igual a old menos um participante;
- new não vazio;
- nenhuma outra transição pendente;
- confirmar a própria entrada pelas duas maiorias.

Ao armazenar CONFIG_JOINT, usar a restrição conjunta em votos e confirmação, mesmo que o anúncio de commit não tenha chegado. Não voltar à regra simples apenas por timeout.

CONFIG_FINAL versão v+2:
- joint_index aponta para o CONFIG_JOINT confirmado;
- voters igual a new;
- confirmar pelas duas maiorias;
- somente depois de confirmar, usar a nova maioria simples.

Manter duas noções no código: configuração aplicada ao estado e configuração conservadora usada pelo consenso. config_version nas mensagens de voto/ACK identifica a conservadora. CONFIG_FINAL pode ter versão 3 no payload enquanto a regra de quorum ainda é a conjunta de versão 2; só depois de confirmar passa a 3.

ACKs incluem config_version. O líder mantém metadados por índice para não contar um ACK sob uma regra incompatível. Uma eleição em transição exige as duas maiorias; o candidato transfere os registros da transição antes de pedir votos a quem não os tem.

Se uma transição não confirmada for descartada por líder eleito válido, recomputar a regra conservadora a partir do histórico restante. Nunca descartar etapa confirmada.

## 9. Comandos

| Tipo | Payload |
|---|---|
| MOVE_INTENT | {queue_version, command_seq, reference_cycle, direction} |
| MOVE_ACCEPTED | {queue_version, command_seq, execution_cycle} |
| MOVE_REJECTED | {queue_version, command_seq, reason} |
| QUEUE_RESET | {queue_version, base_cycle, base_direction, reason} |
| QUEUE_RESET_ACK | {queue_version} |

A identidade completa é (player_id,epoch,queue_version,command_seq).
queue_version começa em 0 por época; command_seq começa em 1 e cresce, mesmo se a fila for limpa.

Rejeições: DEAD, INPUT_CLOSED, EXPIRED, INVALID_DIRECTION, QUEUE_FULL, STALE_QUEUE, INVALID_SEQUENCE.

STALE_QUEUE e época antiga são ignorados/rejeitados sem outra limpeza. INVALID_DIRECTION, EXPIRED ou sequência comprometida limpam a fila vigente. QUEUE_FULL é erro de sincronização: resetar, pois clientes corretos mantêm no máximo dois pendentes.

Após reset, o host bloqueia novas entradas até QUEUE_RESET_ACK. O cliente limpa tudo, usa a direção oficial recebida, envia ACK e então libera entradas se a fase permitir. ACK e novos comandos seguem a mesma conexão, nessa ordem.

O host reserva:
execution_cycle = max(primeiro ciclo ainda aberto, último ciclo reservado ao jogador + 1).
Se execution_cycle-reference_cycle >= command_max_age_cycles, rejeitar e resetar.

Durante os últimos 500 ms da contagem, o primeiro ciclo aberto é last_cycle+1. O tempo parado não aumenta a idade lógica.

No ponto de fechamento de cada ciclo, congelar a seleção de todos os jogadores numa única operação. Revalidar direção e idade. Remover da fila do host o selecionado; a pendência do cliente só desaparece quando vê o registro confirmado correspondente.

A geração de nova época limpa filas, bloqueia entrada e invalida todos os MOVE anteriores. Não apagar registros recuperáveis.

## 10. Snapshot, prontidão e contagem

SnapshotState = {cycle, width, height, bikes: array de Bike, occupied: array de Cell, result: Result, config_version, voters: array de ID}.

O snapshot só é produzido sem reconfiguração pendente, após aplicados os registros até commit_index. A lista de votantes é simples; resolver a transição antes de enviar.

| Tipo | Payload |
|---|---|
| SNAPSHOT | {round_id, anchor_index, anchor_epoch, anchor_hash, state: SnapshotState, state_hash} |
| SNAPSHOT_ACK | {round_id, anchor_index, anchor_hash, state_hash} |
| COUNTDOWN | {round_id, duration_ms: 3000} |
| INPUT_OPEN | {round_id, next_cycle, window_ms: 500} |
| RUN | {round_id, next_cycle} |

state_hash é SHA256 do estado canônico. O receptor obtém os logs faltantes, valida âncora e compara o estado reconstruído. Não substituir uma base confirmada incompatível por confiança no remetente.

SNAPSHOT_ACK exige exatamente a base recebida e validada. O host espera todos os integrantes que continuarão. Falta de resposta exige investigação e remoção confirmada, seguida de novo snapshot/round_id.

Ao enviar COUNTDOWN, o host inicia seu relógio de três segundos. Em 2500 ms envia INPUT_OPEN; em 3000 ms envia RUN. O cliente não estima horário por relógio de parede.

Na primeira partida, após a contagem, o host confirma START antes de propor CYCLE 1. Essa confirmação pode acrescentar atraso de rede, mas nunca antecipa movimento nem cria uma janela extra de três segundos.

Na retomada, EPOCH_START e a base já estão confirmados antes da contagem. RUN autoriza os ciclos; resultados ainda seguem confirmação normal. Não limpar os comandos aceitos na janela ao enviar RUN.

Mensagens de round_id antigo não abrem teclado nem reiniciam timers.

## 11. Atividade e pausa

| Tipo | Payload |
|---|---|
| HEARTBEAT | {leader_id: ID|null, commit_index, config_version} |
| HEARTBEAT_ACK | {commit_index, config_version} |
| PAUSE | {round_id, reason} |

HEARTBEAT é enviado a cada três intervalos sem tráfego útil no sentido de saída da conexão. MOVE e APPEND podem substituí-lo, desde que recebidos e válidos. Atualizar last_rx_valid somente com mensagens do contexto atual.

O líder envia atividade também a espectadores. Clientes respondem, permitindo detecção independente das teclas.

Falha de um socket de par é reportada ao líder por PEER_SUSPECT {player_id,reason}; o relato não é voto de remoção. O líder tenta contato direto antes de iniciar PLAYER_LEFT e reconfiguração.

PAUSE é evento do líder corrente; bloqueia novas entradas e mantém a rede ativa. Remover somente teclas pendentes, não o sufixo de log. Após commit_timeout_ms sem quorum, o líder pausa, abdica e permite próxima eleição. Se não houver quorum, não confirma uma remoção para “resolver” o quorum.

## 12. Saída planejada

LEAVE_REQUEST {action: "LOBBY"|"EXIT"} só pode ser enviado pelo próprio jogador.
LEAVE_APPROVED {action, final_config_version} autoriza encerrar sua participação.

Participante comum:
1. Congelar sua entrada e confirmar PLAYER_LEFT.
2. Se não houver resultado terminal, concluir CONFIG_JOINT/FINAL.
3. Enviar LEAVE_APPROVED.
4. Se a partida ficou terminal, seguir entrega do resultado antes da aprovação.

Host:
1. Confirmar pendência e enviar PAUSE.
2. Enviar TRANSFER_REQUEST para o próximo elegível.
3. Os pares avançam época e realizam a eleição normal.
4. O antigo host continua votando/replicando, sem autoridade.
5. O sucessor confirma PLAYER_LEFT e reconfiguração.
6. Aprovar saída; snapshot e contagem se o jogo continua.

Se a transferência falhar, o antigo host não retoma sozinho. Pode voltar a ser candidato em um slot futuro e precisa obter votos.

## 13. Encerramento

| Tipo | Payload |
|---|---|
| MATCH_OVER | {final_index, final_hash, final_cycle, result: Result} |
| MATCH_OVER_ACK | {final_index, final_hash} |
| SESSION_CLOSE | {final_index, acknowledged: array de ID, removed: array de ID} |
| ABORT_NOTICE | {reason, last_known_commit_index, detail} |

MATCH_OVER exige registro terminal confirmado, normalmente CYCLE ou PLAYER_LEFT. final_index aponta para o primeiro registro que tornou o resultado terminal, mesmo que registros de liderança/configuração sejam acrescentados depois. Após o resultado terminal, não produzir CYCLE nem PLAYER_LEFT que altere o resultado; somente controles para recuperar, entregar e fechar a sessão. O receptor com lacunas solicita histórico antes de ACK.

O host reenvia a solicitação aos pendentes após delivery_retry_ms. Isso não altera o registro nem conta o mesmo ACK duas vezes.

SESSION_CLOSE exige ACK de todos ainda na sessão. Remover alguém exige o mesmo protocolo de configuração, não somente timeout.

Após SESSION_CLOSE, pode fechar as conexões. Se o host cair e o resultado já estiver confirmado localmente, preservar a tela de resultado; o fechamento pode terminar por timeout controlado sem alterar o resultado. Se o resultado ainda é desconhecido, tentar recuperação.

ABORT_NOTICE é aviso técnico, não registro esportivo confirmado. Pode ser enviado na impossibilidade de quorum ou inconsistência. Cada receptor verifica seu contexto; não traduz para DRAW nem altera um resultado já confirmado.

O aplicativo mantém o resultado enquanto tenta voltar ao lobby. Falha do lobby permite tentar novamente ou sair.

## 14. Matriz resumida de estados

| Estado | Mensagens que produzem progresso |
|---|---|
| CONECTANDO_LOBBY | REGISTER_OK ou ERROR |
| NO_LOBBY | CREATE_ROOM_OK, JOIN_ROOM_OK, LIST_ROOMS_OK |
| NA_SALA | ROOM_UPDATED, PREPARE_MATCH, LEAVE_ROOM_OK |
| PREPARANDO | PEER_HELLO, RTT, MATCH_CONFIG, READY, SNAPSHOT |
| CONTAGEM | COUNTDOWN, INPUT_OPEN, PAUSE |
| JANELA_ENTRADA | MOVE, RUN, PAUSE |
| EM_PARTIDA | MOVE, APPEND, COMMIT, LEAVE_REQUEST, MATCH_OVER |
| SINCRONIZANDO | Eleição, LOG, APPEND, configuração, SNAPSHOT |
| ENCERRANDO | MATCH_OVER, ACK, configuração, SESSION_CLOSE |
| RESULTADO | Novo REGISTER ou saída |

HEARTBEAT, ERROR e suspeitas válidas podem ser tratados enquanto existe sessão. APPEND/COMMIT necessários para preservar o histórico continuam sendo processados durante pausa e encerramento. Uma época maior válida sempre interrompe autoridade anterior.

Mensagem inesperada recebe INVALID_STATE e não modifica a arena. Mensagem velha de tentativa, round, fila ou época não reabre estado anterior.

## 15. Exemplo completo de perda do host

1. Ciclo 42 está confirmado nos quatro processos.
2. A produz registro 58, época 1, ciclo 43.
3. B e C armazenam; D está atrasado.
4. A confirma por maioria, anuncia só a B e cai.
5. B tem commit 58; C tem registro 58 provisório; D vai até 57.
6. A época 2 indica B. B apresenta histórico atualizado e obtém votos.
7. B replica 58 a D e acrescenta EPOCH_START em 59, época 2.
8. Confirma 59 por maioria, confirmando também o prefixo.
9. Todos aplicam 58 uma vez. A retirada de A e a reconfiguração são registradas.
10. Snapshot comum, contagem e retomada.

C não perde seu registro por desconhecer o anúncio. D não vota contra o conteúdo só porque ainda não o recebeu.

## 16. Parâmetros iniciais

Valores distribuídos em MatchConfig.settings:

| Campo | Padrão | Unidade/validação |
|---|---|---|
| tick_ms | 125 | Inteiro >= 50 |
| pending_limit | 2 | Nesta versão, exatamente 2 |
| command_max_age_cycles | 3 | Nesta versão, exatamente 3 |
| idle_heartbeat_cycles | 3 | Inteiro >= 1 |
| host_timeout_ms | 1500 | Maior que dois intervalos de heartbeat |
| election_slot_ms | 2000 | Inteiro positivo |
| election_total_ms | 15000 | Maior que election_slot_ms |
| commit_timeout_ms | 2000 | Maior que tick_ms |
| sync_timeout_ms | 5000 | Inteiro positivo |
| delivery_retry_ms | 500 | Inteiro positivo |
| shutdown_timeout_ms | 10000 | Inteiro positivo |
| countdown_ms | 3000 | Exatamente 3000 |
| input_window_ms | 500 | Exatamente 500 |
| rtt_sample_timeout_ms | 1000 | Inteiro positivo |
| hello_timeout_ms | 3000 | Inteiro positivo |
| prepare_timeout_ms | 15000 | Inteiro positivo |
| max_frame_bytes | 1048576 | Máximo físico desta versão |

Configuração local inicial: width=40, height=30, samples=5, MAX_SEND_QUEUE_BYTES=4*max_frame_bytes por conexão.

Todos os prazos usam relógio monotônico. Valores experimentais não autorizam cada processo a usar settings diferentes na mesma partida. Alterar configurações compartilhadas somente antes de iniciar.

## 17. Critérios para considerar a implementação compatível

- Entender framing com mensagens fragmentadas e concatenadas.
- Validar campos, limites e estados.
- Calcular o motor de forma determinística.
- Manter voto único, épocas e confirmação do prefixo.
- Rejeitar conflito confirmado.
- Tratar limpeza e comandos atrasados.
- Completar transição conjunta sem reduzir quorum localmente.
- Recuperar após quedas em cada etapa da replicação.
- Encerrar sem bloquear indefinidamente.
- Medir a latência e demonstrar limites do quorum.

Os testes de [implementacao.md](implementacao.md) são parte da conclusão do projeto. Esta especificação não substitui execução, análise de falhas nem demonstração.
