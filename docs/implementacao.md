# Implementação, testes e apresentação

Este guia divide o trabalho em entregas verificáveis. Os comandos de execução abaixo são a interface desejada ao final, não uma afirmação de que os módulos já estejam implementados.

## 1. Ambiente e execução

Usar Python e Poetry. Sockets, selectors, threading, queue, json, hashlib, uuid, time e unittest estão na biblioteca padrão.

Bibliotecas de terminal e configuração, como rich e python-dotenv, podem ser auxiliares. Não usar uma biblioteca que implemente o multiplayer ou o consenso no lugar da equipe.

Interface desejada:

~~~bash
poetry install
poetry run python -m src.lobby
poetry run python -m src.node --name Ana --peer-port 6001
poetry run python -m src.node --name Bruno --peer-port 6002
poetry run python -m src.node --name Carla --peer-port 6003
~~~

Ao implementar argparse, aceitar opções equivalentes para lobby host/port, bind host, endereço anunciado e peer port. Precedência: argumento de linha de comando, variável de ambiente, padrão local.

Configuração inicial sugerida:

~~~dotenv
LOBBY_HOST=127.0.0.1
LOBBY_PORT=5000
PEER_BIND_HOST=0.0.0.0
PEER_ADVERTISE_HOST=127.0.0.1
PEER_PORT=6001
~~~

Em máquinas diferentes, LOBBY_HOST é o IP real do servidor; cada PEER_ADVERTISE_HOST é o IP alcançável daquele jogador. Vários processos na mesma máquina usam portas diferentes.

O lobby também deve aceitar host/port configuráveis para bind.

## 2. Estrutura sugerida

~~~text
src/
  core/
    config.py
    codec.py
    messages.py
    hashing.py
    types.py
  lobby/
    __main__.py
    server.py
    rooms.py
  game/
    state.py
    engine.py
  node/
    __main__.py
    network.py
    session.py
    commands.py
    replication.py
    election.py
    membership.py
    ui.py
tests/
  test_codec.py
  test_engine.py
  test_commands.py
  test_replication.py
  test_election.py
  test_membership.py
  test_scenarios.py
~~~

Arquivos representam responsabilidades, não classes obrigatórias. Evitar um único arquivo de milhares de linhas. Evitar também criar abstrações antes de ter um fluxo funcional.

## 3. Dono do estado e eventos

Uma thread ou laço é o único dono de arena, filas, época, votos, histórico e configuração.

Outras threads podem:
- receber bytes e entregar mensagens;
- capturar teclado e entregar teclas;
- desenhar uma cópia imutável do estado.

Elas não alteram diretamente os dados do protocolo.

Eventos internos sugeridos:
MESSAGE(peer_id,message), KEY(direction), SOCKET_CLOSED(peer_id), TIMER(name), USER_ACTION(action).

A rede usa selectors ou threads por conexão. Em qualquer opção, o envio é serializado por conexão: duas threads nunca intercalam bytes de JSON diferentes.

Uma fila de envio acima de MAX_SEND_QUEUE_BYTES gera falha de par lento. Não descartar silenciosamente registros ou metade de uma mensagem.

## 4. Primeira entrega: codec TCP

Implementar antes do jogo.

~~~python
def encode_message(message):
    text = json.dumps(
        message, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    )
    return text.encode("utf-8") + bytes([10])
~~~

O decoder precisa:
1. Acrescentar bytes ao buffer.
2. Localizar todos os LF completos.
3. Validar tamanho.
4. Decodificar cada linha e validar JSON/envelope.
5. Entregar as mensagens completas.
6. Preservar o restante.

Não fazer json.loads(conn.recv(1024)). TCP não preserva esses limites.

Critérios:
- Uma mensagem dividida em qualquer byte funciona.
- Três mensagens numa leitura funcionam.
- UTF-8 dividido entre leituras funciona.
- Linha inválida ou grande tem comportamento definido.
- Fechamento de conexão não vira laço infinito de recv vazio.

## 5. Segunda entrega: lobby e preparação

Implementar registro, salas e autorização do criador.

Verificar:
- Quinto jogador não entra, inclusive em operações concorrentes.
- Jogador não participa de duas salas.
- Não criador não inicia.
- Dois jogadores não iniciam.
- Sala em PREPARANDO não aceita JOIN.
- Criador ausente é substituído pelo presente mais antigo.
- Queda durante preparação cancela, mesmo com três restantes.
- CANCEL_PREPARATION permite receber novo participante.

Depois acrescentar malha, RTT, configuração e READY. Primeiro testar três processos na mesma máquina; depois máquinas distintas.

Não começar a eleição aqui. O ranking inicial, o roster e a configuração precisam estar iguais antes da partida.

## 6. Terceira entrega: motor isolado

Representação possível:
- occupied: mapa (x,y) → owner_id;
- bikes: mapa player_id → Bike;
- cycle: inteiro;
- result: Result.

A função step deve devolver novo estado e resultado do ciclo, sem sockets.

Testes indispensáveis:
- Uma moto avança exatamente uma célula.
- Inversão não é aplicada.
- Todas as motos usam a ocupação anterior para verificar rastros.
- Mesma célula elimina todas.
- Troca de posições elimina ambas.
- Rastro de eliminado permanece.
- Parede não produz coordenada inválida na matriz.
- Últimas motos eliminadas juntas produzem empate.
- Ordem de iteração dos IDs não muda o resultado.
- PLAYER_LEFT não desloca as outras motos.

Usar uma arena pequena nos testes, não a interface completa.

## 7. Quarta entrega: comandos

Guardar um OrderedDict ou estrutura equivalente para os pendentes do cliente, identificados por CommandRef.

No host, cada jogador tem:
- versão da fila;
- estado aguardando reset ACK;
- sequência recebida;
- até duas reservas (execution_cycle,command).

Pseudocódigo:

~~~text
ao receber tecla:
    se fase não aceita entrada ou moto morreu: ignorar
    se dois pendentes: ignorar
    referência = última direção pendente ou direção oficial
    se tecla igual ou oposta à referência: ignorar
    criar comando com sequência nova e ciclo oficial conhecido
    adicionar aos pendentes
    enviar MOVE_INTENT

ao receber comando no host:
    validar contexto, versão, sequência e moto
    reservar primeiro ciclo livre daquele jogador
    se idade >= 3: limpar a fila pelo protocolo
    senão guardar reserva e enviar MOVE_ACCEPTED

ao aplicar registro CYCLE confirmado:
    atualizar arena
    remover pendências referenciadas em moves
~~~

Não liberar capacidade em MOVE_ACCEPTED.

Testar limpeza com mensagens antigas ainda em trânsito. Testar duas curvas com a mesma referência: primeira no ciclo seguinte, segunda no posterior.

## 8. Quinta entrega: histórico e replicação

Começar com host fixo; isso permite depurar o registro antes de acrescentar eleição.

Variáveis mínimas:
current_epoch, voted_for, leader_id, log, commit_index, last_applied,
next_index, match_index, configuration.

Pseudocódigo do líder:

~~~text
produzir decisão:
    construir registro usando último hash
    guardar na memória
    atualizar a própria posição armazenada
    enviar APPEND aos pares

ao receber APPEND_RESULT:
    verificar época, hash, configuração e identidade
    atualizar posição daquele par
    procurar posição atual com quorum apropriado
    se puder confirmar:
        avançar commit_index
        aplicar prefixo ainda não aplicado
        anunciar COMMIT
~~~

Pseudocódigo do receptor:

~~~text
ao receber APPEND:
    conferir líder e época
    conferir âncora anterior
    verificar hashes e continuidade
    substituir somente sufixo provisório conflitante
    armazenar
    responder
    aplicar somente até a posição confirmada e validada
~~~

Não usar apenas “três respostas chegaram”. Verificar quem respondeu, para qual registro e sob qual configuração.

A confirmação de uma entrada atual pode confirmar o prefixo antigo. Não confirmar entrada antiga diretamente só porque aparece em duas telas.

## 9. Sexta entrega: eleição e recuperação

Testar voto único e épocas sem interface.

Casos:
- Dois pedidos diferentes na mesma época: no máximo um voto concedido.
- Candidato igual em frescor: pode receber voto.
- Candidato com último registro de época menor: não vence a comparação só por ter mais posições.
- Candidato com época eleitoral nova não reescreve seu histórico.
- APPEND antigo não recupera autoridade.
- Host isolado não confirma sozinho.
- Candidato indisponível dá lugar ao próximo slot.
- Prazo total acaba sem laço infinito.

Depois simular:
1. Host calcula mas não distribui.
2. Distribui só a um.
3. Obtém quorum mas não anuncia.
4. Anuncia a um e cai.
5. Cai durante snapshot.
6. Cai nos primeiros 2,5 s da contagem.
7. Cai na janela de 500 ms.
8. Cai durante transferência.

O oráculo do teste compara registros confirmados por posição. Participantes podem conhecer comprimentos diferentes; posições confirmadas em comum não podem diferir.

Uma implementação útil de simulador mantém uma fila de mensagens em memória e permite entregar, atrasar ou descartar conexões entre processos simulados. Ele não substitui testes com sockets reais.

## 10. Sétima entrega: configuração dos votantes

Testar quatro para três e três para dois.

Durante a fase conjunta:
- ACK de participante novo/antigo é contado nas listas corretas.
- CONFIG_FINAL ainda precisa das duas maiorias.
- Uma mensagem de configuração antiga não relaxa a exigência.
- Outra alteração não começa.
- Falha no meio não apaga CONFIG_JOINT confirmado.
- Sem quorum, não remover localmente alguém para destravar.

Todos os snapshots de retomada têm configuração simples; terminar a transição antes de criar a base.

Cenário de limite: dois votantes e uma falha. O resultado esperado é encerramento controlado por falta de quorum, não vitória automática.

## 11. Encerramento

Verificar:
- MATCH_OVER corresponde a registro terminal confirmado.
- Cliente atrasado busca o log antes de ACK.
- Host espera todos ainda integrantes.
- Timeout não é entrega.
- Saída normal não fecha a conexão prematuramente.
- Host cai após entrega parcial: o resultado é recuperado se houver condições.
- Resultado já conhecido permanece mesmo se transporte fechar.
- Lobby desligado não impede encerrar ou sair.
- Retornar ao lobby é escolha do usuário.

## 12. Temporizadores sem travar o aplicativo

Usar time.monotonic_ns e deadlines. Não usar sleep de três segundos dentro da thread que processa sockets.

O laço calcula o próximo deadline e processa eventos até ele. COUNTDOWN começa em t0:
- abrir entrada em t0 + 2500 ms;
- terminar em t0 + 3000 ms.

Contagem tem round_id. Eventos atrasados de uma contagem anterior são ignorados.

Se um ciclo não foi confirmado a tempo, não produzir uma rajada de movimentos para alcançar o relógio. Pausar, manter tráfego de rede e resolver a causa.

## 13. Diagnóstico e métricas

Logs estruturados por linha, por exemplo:

~~~json
{
  "event": "commit_advanced",
  "match_id": "m1",
  "player_id": "p1",
  "epoch": 2,
  "index": 59,
  "cycle": 43,
  "config_version": 1
}
~~~

Não misturar index com cycle no mesmo nome.

Medir no cliente:
- instante local da tecla aceita;
- instante local de recebimento/aplicação da execução;
- diferença total.

Medir no host:
- recepção do comando;
- reserva;
- cálculo do ciclo;
- obtenção de quorum.

Não subtrair relógios de máquinas diferentes sem sincronização. Medições locais e RTT bastam para a primeira análise.

## 14. Plano de demonstração

| Demonstração | O que explica |
|---|---|
| Lobby e três processos | Descoberta, portas e isolamento de processos |
| Quarto entra; quinto é recusado | Capacidade e estado da sala |
| Criador inicia; READY automático | Preparação compartilhada |
| Contagem com teclado só no final | Temporizadores e comandos |
| Colisão simultânea | Motor determinístico |
| Lobby desligado durante jogo | Independência do plano de jogo |
| Jogador comum encerra | Suspeita, eliminação e configuração |
| Host encerra | Eleição, época e recuperação |
| Host sai voluntariamente | Transferência e autorização de saída |
| Dois votantes, um falha | Limite do quorum e encerramento controlado |
| Jogo termina, lobby ausente | Resultado independente e escolha de saída |

Preparar injeções de falha controladas para pausar o host depois de APPEND e antes de COMMIT. Matar o processo em um momento aleatório não demonstra todos os casos.

## 15. O que cada integrante deve conseguir explicar

1. Por que um recv não equivale a uma mensagem.
2. Por que ausência de tecla não significa falha.
3. Por que fila local e fila autoritária precisam se reconciliar.
4. Por que dois comandos não significam duas curvas no mesmo ciclo.
5. Por que “aceito” não é “executado” nem “confirmado”.
6. Por que época não é ciclo.
7. Por que o ranking não basta para ser host.
8. Como uma cópia de registro desconhecida por outros ajuda a recuperar.
9. Por que configuração de votantes é uma decisão compartilhada.
10. Qual garantia o projeto mantém quando perde continuidade.

## 16. Definição de pronto

Um módulo está pronto quando possui comportamento verificável, tratamento de erro e integração documentada.

A entrega completa exige:
- testes unitários do motor, codec, filas e quorum;
- cenários de falha entre cada etapa relevante;
- execução real em máquinas distintas;
- métricas iniciais de latência;
- protocolo atualizado com o código;
- limitações demonstradas sem alegar garantia não testada.

Os valores padrão podem mudar pelos resultados. Se mudar pending_limit ou a idade, revisar os testes que dependem da capacidade e da reserva.
