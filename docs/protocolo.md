# Protocolo de aplicação — Tron P2P

## 1. Situação do documento

Versão: rascunho inicial consolidado.

Este documento contém:

- Formatos iniciais adotados para o lobby.
- Regras acordadas de comandos e confirmação.
- Catálogo proposto de mensagens P2P.
- Pendências para concluir a especificação.

Os esquemas completos P2P e os algoritmos distribuídos ainda não estão fechados. Este documento ainda não permite, sozinho, implementar um participante totalmente interoperável.

Consulte arquitetura.md para os fluxos e responsabilidades.

## 2. Transporte e enquadramento

- TCP por sockets.
- JSON em UTF-8.
- Um objeto por mensagem.
- Delimitador: LF real, U+000A.
- Na rede, cada JSON ocupa uma linha.
- Os exemplos formatados abaixo são apenas para leitura.

O receptor acumula bytes e extrai linhas completas. Um recv pode conter uma parte, uma ou várias mensagens.

Decodificar somente a mensagem completa evita problemas com caracteres UTF-8 divididos entre leituras.

O limite de mensagem e dos buffers deve ser configurado; seus valores e tratamento ainda precisam ser definidos.

## 3. Envelope do lobby

~~~json
{
  "version": 1,
  "type": "REGISTER",
  "request_id": 1,
  "payload": {}
}
~~~

| Campo | Tipo | Significado |
|---|---|---|
| version | inteiro | Inicialmente 1 |
| type | string | Tipo da mensagem |
| request_id | inteiro ou null | Correlação da solicitação |
| payload | objeto | Conteúdo específico |

O cliente usa request_id crescente, sem reutilização na conexão. A resposta repete o identificador.

Notificações espontâneas usam null.

Uma nova conexão inicia outro espaço de identificação. Reenvio automático de operações mutáveis exige política adicional de deduplicação; não é autorizado apenas pela existência de request_id.

## 4. Identidades

- player_id: atribuído pelo lobby.
- nickname: apresentação.
- room_id: sala.
- room_version: revisão da sala.
- match_id: partida.
- attempt_id: tentativa de preparação.
- Época de liderança: distingue autoridades.
- Versão da fila: distingue sequências após limpeza.

A identidade declarada em uma mensagem deve corresponder à conexão identificada.

O retorno ao lobby cria uma nova sessão. A continuidade ou reatribuição de player_id entre sessões ainda precisa ser especificada, sem alterar identidades da partida anterior.

## 5. Erros

~~~json
{
  "version": 1,
  "type": "ERROR",
  "request_id": 6,
  "payload": {
    "code": "NOT_ENOUGH_PLAYERS",
    "message": "São necessários pelo menos três jogadores."
  }
}
~~~

O aplicativo decide pelo code; message é apresentação.

Se a solicitação não puder ser identificada, request_id pode ser null.

| Código | Significado |
|---|---|
| INVALID_MESSAGE | Estrutura ou campo inválido |
| INVALID_STATE | Operação inválida na fase atual |
| ALREADY_REGISTERED | Conexão já registrada |
| ALREADY_IN_ROOM | Jogador já está em sala |
| ROOM_NOT_FOUND | Sala inexistente |
| ROOM_FULL | Sem vaga |
| ROOM_NOT_JOINABLE | Sala fora de AGUARDANDO |
| NOT_ROOM_CREATOR | Operação exclusiva do criador |
| NOT_ENOUGH_PLAYERS | Menos de três para iniciar |

A reação a JSON inválido, excesso de tamanho e versão incompatível precisa ser detalhada.

## 6. Representação da sala

~~~json
{
  "room_id": "r1",
  "room_version": 1,
  "name": "Partida da turma",
  "state": "AGUARDANDO",
  "creator_id": "p1",
  "min_players": 3,
  "max_players": 4,
  "players": [
    {
      "player_id": "p1",
      "nickname": "Ana"
    }
  ]
}
~~~

A lista de jogadores segue a ordem de entrada.

room_version aumenta quando a sala muda. O cliente substitui sua representação pela versão mais recente e ignora versões antigas.

Os estados são AGUARDANDO, PREPARANDO, EM_PARTIDA e FINALIZADA.

Somente AGUARDANDO aceita novos participantes.

## 7. Registro

### REGISTER

Cliente para lobby, antes de estar registrado.

A porta P2P deve estar aberta.

~~~json
{
  "version": 1,
  "type": "REGISTER",
  "request_id": 1,
  "payload": {
    "nickname": "Ana",
    "peer_endpoint": {
      "host": "192.168.1.10",
      "port": 6001
    }
  }
}
~~~

Validações:

- Apelido não vazio.
- Endpoint estruturalmente válido.
- Porta inteira entre 1 e 65535.
- Conexão ainda não registrada.

Os limites de tamanho das strings serão definidos.

A validade estrutural do endpoint não garante conectividade; a preparação verifica isso.

### REGISTER_OK

~~~json
{
  "version": 1,
  "type": "REGISTER_OK",
  "request_id": 1,
  "payload": {
    "player_id": "p1"
  }
}
~~~

Associa a conexão ao jogador e leva o aplicativo a NO_LOBBY.

O cliente não precisa reenviar seu player_id em toda operação de lobby.

## 8. Criação de sala

### CREATE_ROOM

Cliente registrado e fora de outra sala.

~~~json
{
  "version": 1,
  "type": "CREATE_ROOM",
  "request_id": 2,
  "payload": {
    "name": "Partida da turma"
  }
}
~~~

### CREATE_ROOM_OK

~~~json
{
  "version": 1,
  "type": "CREATE_ROOM_OK",
  "request_id": 2,
  "payload": {
    "room": {
      "room_id": "r1",
      "room_version": 1,
      "name": "Partida da turma",
      "state": "AGUARDANDO",
      "creator_id": "p1",
      "min_players": 3,
      "max_players": 4,
      "players": [
        {
          "player_id": "p1",
          "nickname": "Ana"
        }
      ]
    }
  }
}
~~~

O criador entra automaticamente. O aplicativo passa a NA_SALA.

Erros principais: INVALID_MESSAGE, INVALID_STATE e ALREADY_IN_ROOM.

As configurações do jogo podem inicialmente vir da configuração do servidor. Permitir ajustes pelo criador é uma extensão a especificar.

## 9. Listagem

### LIST_ROOMS

Cliente registrado.

~~~json
{
  "version": 1,
  "type": "LIST_ROOMS",
  "request_id": 3,
  "payload": {}
}
~~~

### LIST_ROOMS_OK

~~~json
{
  "version": 1,
  "type": "LIST_ROOMS_OK",
  "request_id": 3,
  "payload": {
    "rooms": [
      {
        "room_id": "r1",
        "name": "Partida da turma",
        "state": "AGUARDANDO",
        "player_count": 3,
        "max_players": 4
      }
    ]
  }
}
~~~

Lista vazia é resposta normal.

Salas em preparação ou partida podem ser exibidas com seu estado, mas não aceitam entrada.

## 10. Entrada na sala

### JOIN_ROOM

Cliente registrado e fora de outra sala.

~~~json
{
  "version": 1,
  "type": "JOIN_ROOM",
  "request_id": 4,
  "payload": {
    "room_id": "r1"
  }
}
~~~

O lobby verifica existência, estado e capacidade.

### JOIN_ROOM_OK

payload.room contém a representação completa atualizada.

Efeitos:

- Incluir o jogador.
- Incrementar room_version.
- Levar o aplicativo a NA_SALA.
- Notificar os demais por ROOM_UPDATED.

A verificação de vaga e a inclusão precisam ser atômicas.

Erros: ROOM_NOT_FOUND, ROOM_FULL, ROOM_NOT_JOINABLE, ALREADY_IN_ROOM, INVALID_STATE e INVALID_MESSAGE.

## 11. Atualização da sala

### ROOM_UPDATED

Lobby para integrantes, com request_id null.

payload.room contém a representação completa.

Usada quando alguém entra, sai, o criador muda ou o estado da sala é alterado.

O cliente só aplica uma versão mais recente.

Não modifica a configuração P2P de uma partida já iniciada.

## 12. Saída antes da partida

### LEAVE_ROOM

~~~json
{
  "version": 1,
  "type": "LEAVE_ROOM",
  "request_id": 5,
  "payload": {}
}
~~~

### LEAVE_ROOM_OK

~~~json
{
  "version": 1,
  "type": "LEAVE_ROOM_OK",
  "request_id": 5,
  "payload": {}
}
~~~

Efeitos:

- Remover o jogador e levá-lo a NO_LOBBY.
- Transferir o controle da sala ao presente mais antigo, se necessário.
- Remover sala vazia.
- Atualizar a sala e notificar.
- Invalidar preparação ativa, mantendo a sala em PREPARANDO.

Durante partida iniciada, a saída pertence ao protocolo P2P.

## 13. Solicitação de início

### START_MATCH

Somente o criador.

Pré-condições:

- Três ou quatro participantes.
- Sala em AGUARDANDO ou PREPARANDO.
- Nenhuma tentativa ativa incompatível.

~~~json
{
  "version": 1,
  "type": "START_MATCH",
  "request_id": 6,
  "payload": {}
}
~~~

### START_MATCH_OK

~~~json
{
  "version": 1,
  "type": "START_MATCH_OK",
  "request_id": 6,
  "payload": {
    "match_id": "m1",
    "attempt_id": "a1"
  }
}
~~~

A identificação apresentada é a proposta inicial.

A resposta confirma o começo da preparação, não o início dos movimentos.

O lobby:

- Congela os participantes.
- Coloca a sala em PREPARANDO.
- Distribui PREPARE_MATCH.
- Atualiza a representação da sala.

A política de reutilização de match_id entre tentativas precisa ser definida. attempt_id sempre distingue a tentativa.

## 14. Reabrir a sala

### CANCEL_PREPARATION

Somente o criador, antes da partida e com sala em PREPARANDO.

~~~json
{
  "version": 1,
  "type": "CANCEL_PREPARATION",
  "request_id": 7,
  "payload": {}
}
~~~

### CANCEL_PREPARATION_OK

~~~json
{
  "version": 1,
  "type": "CANCEL_PREPARATION_OK",
  "request_id": 7,
  "payload": {}
}
~~~

Efeitos:

- Invalidar a tentativa.
- Cancelar contagem.
- Voltar a AGUARDANDO.
- Permitir entradas.
- Notificar a sala.
- Exigir outro START_MATCH.

O aviso de cancelamento precisa identificar a tentativa invalidada; seu esquema será definido na preparação.

## 15. Preparação: mensagens a detalhar

Os nomes seguintes são propostas, ainda sem esquema completo.

| Mensagem | Direção e finalidade |
|---|---|
| PREPARE_MATCH | Lobby distribui partida, tentativa, participantes e endpoints |
| PEER_HELLO | Pares identificam a conexão |
| RTT_PING | Inicia uma medição |
| RTT_PONG | Responde à medição correspondente |
| RTT_REPORT | Jogador informa medições ao lobby |
| MATCH_CONFIG | Lobby distribui configuração consolidada |
| READY | Aplicativo informa prontidão ao host inicial |
| PREPARATION_CANCELLED | Invalida uma tentativa |
| COUNTDOWN | Host conduz contagem |
| INPUT_WINDOW | Abre a janela de entrada |
| MATCH_STARTED | Autoriza o primeiro ciclo |

Regras:

- Malha com conexão iniciada pelo menor ID.
- RTT medido com relógio local monotônico.
- Ranking único pela média de RTT.
- READY automático, vinculado à configuração e tentativa.
- Todos precisam estar prontos para iniciar.
- Qualquer queda antes do primeiro ciclo cancela a tentativa.
- A sala permanece PREPARANDO até decisão do criador.
- Tentativas antigas não autorizam início.
- O ponto exato de transição para partida iniciada ainda precisa ser formalizado.

## 16. Comandos: contrato comportamental

### Campos necessários

O esquema final deve identificar:

- Partida.
- Época de liderança.
- Versão da fila.
- Sequência do comando.
- Direção.
- Ciclo de referência.

A identidade é conferida com a conexão.

### Mensagens propostas

| Mensagem | Finalidade |
|---|---|
| MOVE_INTENT | Solicitar direção |
| MOVE_ACCEPTED | Informar aceitação e ciclo reservado |
| MOVE_REJECTED | Informar rejeição e motivo |
| QUEUE_RESET | Estabelecer nova versão e base da fila |

A execução é informada pelo registro confirmado do ciclo.

### Regras

- Dois pendentes por jogador, incluindo os enviados.
- Aceitação não libera espaço.
- Validar pela última direção aceita pendente.
- Ignorar direção repetida, inversão e tecla com fila cheia.
- Host reserva o primeiro ciclo aberto.
- No máximo uma curva por jogador por ciclo.
- Sem comando, manter direção.
- Expirar se execução menos referência for maior ou igual a três.
- Validar na reserva e antes da execução.
- Limpar pendências quando uma rejeição comprometer a sequência.
- Nova versão impede reaparecimento de comandos antigos.
- Moto eliminada não aceita comandos.
- Migração limpa pendências de todos.
- Host usa o mesmo fluxo.

A confirmação de QUEUE_RESET e a reconciliação antes de liberar entradas ainda precisam ser especificadas.

## 17. Registro e confirmação

### Estrutura necessária

Cada registro distingue:

- Posição no histórico.
- Época de criação.
- Tipo: ciclo ou controle.
- Ciclo, quando aplicável.
- Conteúdo da transição.
- Referência ao prefixo anterior.

Posição no registro não é número de ciclo.

A identificação do conteúdo por hash e seu algoritmo ainda precisam ser definidos. Hash não substitui consenso.

### Resultado de ciclo

Precisa representar:

- Comandos efetivamente aplicados.
- Direções e movimentos.
- Novos rastros.
- Eliminações e motivos.
- Resultado final, se houver.

A decisão de tráfego é evitar matriz completa em todo ciclo.

A forma exata entre comandos determinísticos e deltas explícitos ainda será formalizada.

### Mensagens propostas

| Mensagem | Finalidade |
|---|---|
| APPEND_ENTRIES | Distribuir registros e referência ao prefixo |
| APPEND_ACK | Confirmar sequência armazenada |
| LOG_REQUEST | Solicitar trecho ausente |
| LOG_ENTRIES | Transferir registros |
| COMMIT_UPDATE | Anunciar posição confirmada |
| SNAPSHOT | Transferir estado completo e sua posição/configuração |

### Confirmação

- Confirmar imediatamente após armazenar e validar.
- Confirmar N exige todos os registros até N.
- O host conta sua cópia.
- Usar maioria da configuração vigente.
- Durante transição, exigir maioria antiga e nova.
- Não esperar todos para confirmar ciclos.
- Aplicar e apresentar somente sequência confirmada.
- Não aplicar registro duas vezes.
- Não esperar o próximo tick para responder ACK ou anunciar confirmação.

## 18. Eleição e recuperação

### Mensagens propostas

| Mensagem | Finalidade |
|---|---|
| LOG_STATUS_REQUEST | Consultar metadados |
| LOG_STATUS | Informar posições e épocas conhecidas |
| REQUEST_VOTE | Solicitar votos com metadados de histórico |
| VOTE_RESPONSE | Conceder ou negar |
| LEADER_ESTABLISHED | Informar liderança estabelecida |
| SYNC_STATE | Distribuir base recuperada |
| SYNC_ACK | Confirmar instalação |

O estabelecimento da liderança também integra o registro.

### Regras acordadas

- Timeout é suspeita.
- Nova tentativa usa época superior.
- Um voto por votante por época.
- Ranking orienta a prioridade.
- Histórico do candidato precisa ser elegível.
- Preferencial desatualizado se atualiza ou outro assume.
- Maioria é obrigatória.
- Prefixo confirmado é preservado.
- Registros pendentes são reconciliados antes da retomada.
- Registros antigos não têm sua época reescrita.
- Comandos pendentes são descartados.
- Arena e direções são atualizadas durante a pausa.
- Sem progresso seguro, encerrar de forma controlada.

### Pendências obrigatórias

- Predicado exato de elegibilidade.
- Tratamento de épocas menores, iguais e maiores.
- Prazos e tentativas de eleição.
- Correspondência e conflitos entre registros.
- Substituição segura de sufixos não confirmados.
- Confirmação na época atual e do prefixo anterior.
- Instalação de snapshots.
- Eleições durante configuração conjunta.
- Mensagens tardias da liderança anterior.

Não implementar como simples seleção do maior ciclo ou votação isolada de hashes.

## 19. Saída e configuração

### Mensagens propostas

| Mensagem | Finalidade |
|---|---|
| LEAVE_REQUEST | Solicitar saída |
| LEADERSHIP_TRANSFER | Iniciar transferência planejada |
| CONFIG_JOINT | Registrar configuração conjunta |
| CONFIG_FINAL | Registrar configuração definitiva |
| LEAVE_APPROVED | Autorizar desconexão |

As decisões de configuração pertencem ao registro replicado.

### Regras

- Eliminação da moto não remove automaticamente o votante.
- Espectador conectado pode continuar votante.
- Saída voluntária mantém conexão até aprovação.
- Moto viva é eliminada oficialmente.
- Uma reconfiguração por vez.
- Transição exige maiorias antiga e nova.
- Timeout local não muda composição.
- Host sai após transferência e remoção.
- Falha na transferência usa recuperação.
- Sem maioria, não se inventa configuração menor.

O instante de ativação das configurações ainda precisa ser formalizado.

## 20. Atividade

Mensagem proposta: HEARTBEAT.

Deve carregar apenas os identificadores necessários ao contexto, sem arena.

Regras:

- Enviar após três intervalos sem comandos.
- Repetir enquanto necessário.
- Considerar outras mensagens válidas como atividade.
- Atualizações normais demonstram atividade do host.
- Manter atividade nas pausas.
- Usar tempo monotônico.
- Timeout distinto e maior que o intervalo de verificação.
- Aproveitar erros e fim de leitura do TCP.

Envelope mínimo, resposta explícita e timeouts ainda precisam ser definidos.

## 21. Encerramento

### Mensagens propostas

| Mensagem | Finalidade |
|---|---|
| MATCH_OVER | Anunciar resultado confirmado |
| MATCH_OVER_ACK | Confirmar entrega |
| SESSION_CLOSE | Concluir fechamento normal |
| MATCH_ABORTED | Encerramento controlado sem inventar resultado |

### Resultado global

Inclui:

- Partida e época.
- Ciclo final.
- Referência ao registro confirmado.
- Vitória ou empate.
- Vencedor, quando houver.

Todos recebem o mesmo resultado. Cada aplicativo resolve sua apresentação.

### Fluxo

1. Confirmar ciclo final.
2. Distribuir resultado e registros ausentes.
3. Bloquear entradas e limpar pendências.
4. Receber confirmação de todos ainda integrantes.
5. Concluir fechamento.
6. Permitir voltar ao lobby ou sair.

Timeout não é confirmação.

Falhas exigem tratamento e remoção confirmada quando possível. Sem progresso seguro, usar encerramento controlado.

Resultado confirmado não é desfeito por desconexão posterior. Quem não conseguir recuperá-lo informa indisponibilidade.

A disponibilidade do resultado durante fechamento e falhas ainda precisa ser formalizada.

Não se promete entrega a todos sob perda arbitrária de processos.

Voltar ao lobby é opcional. Sua indisponibilidade não reabre a partida.

## 22. Parâmetros

| Parâmetro | Decisão |
|---|---|
| Participantes iniciais | Três ou quatro |
| Máximo | Quatro |
| Pendências por jogador | Duas inicialmente |
| Expiração | Idade maior ou igual a três ciclos |
| Atividade sem comando | Três intervalos |
| Contagem | Três segundos |
| Janela de entrada | Três segundos, após a contagem |
| Taxa de ciclos | Configurável |
| Arena e spawns | A definir |
| Amostras de RTT | A definir |
| Timeouts | A definir |
| Limite de mensagem | A definir |
| Endereços e portas | Configuráveis |

Os parâmetros de partida precisam ser compartilhados. Processos não podem usar limites incompatíveis por configuração local.

## 23. Critérios para concluir a especificação

- Todos os campos têm tipos, limites e exemplos.
- Cada mensagem possui emissores, receptores e estados válidos.
- Respostas, erros e mensagens antigas têm tratamento.
- Cada espera possui prazo e consequência.
- Toda transição define efeitos sobre filas, votos e registros.
- Eleição, replicação e reconfiguração formam um algoritmo coerente.
- Armazenamento, confirmação e aplicação são distintos.
- O ciclo final segue a mesma confirmação.
- Sockets lentos não bloqueiam os demais.
- Os cenários de falha possuem resultados esperados.

Os nomes P2P propostos podem mudar no detalhamento. Documento e implementações devem ser atualizados juntos.