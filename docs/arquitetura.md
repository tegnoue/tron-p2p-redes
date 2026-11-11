# Arquitetura do Tron P2P

## 1. O que o sistema faz

Cada jogador controla uma moto que avança uma célula por ciclo em uma arena retangular. As células percorridas viram obstáculos permanentes. Colisões eliminam motos; vence a última sobrevivente. Se as últimas forem eliminadas juntas, há empate.

O lobby registra jogadores e organiza salas. Depois da preparação, os próprios jogadores executam a partida. Um deles é o **host**, responsável por calcular os ciclos. Os demais recebem os resultados, guardam cópias e confirmam o armazenamento.

A proposta usa um protocolo específico para este jogo. Aproveita regras conhecidas de replicação e eleição, sem implementar todas as funcionalidades de Raft. Isso reduz o escopo, mas continua exigindo cuidado com épocas, votos, registros e mudanças dos votantes.

Leia [o glossário](glossario.md) quando encontrar um termo desconhecido. Os campos exatos e algoritmos estão em [protocolo.md](protocolo.md). [implementacao.md](implementacao.md) mostra como transformar o desenho em código.

## 2. Requisitos e limites

- Uma partida começa com três ou quatro processos de jogadores.
- O lobby é um processo separado; processos podem estar em máquinas da mesma rede.
- Comunicação diretamente por sockets TCP; JSON e bibliotecas de terminal são auxiliares permitidas.
- Endereços, portas e parâmetros são configuráveis.
- A partida iniciada não depende do lobby.
- Todos precisam concordar sobre movimentos oficiais, colisões e resultado.
- A falha de um jogador comum elimina sua moto, quando for possível confirmar essa decisão.
- A falha do host inicia eleição e recuperação; se não houver progresso seguro, ocorre encerramento controlado.
- Nenhum jogador entra em uma partida já iniciada. Um processo reiniciado não retorna à mesma sessão.
- Estado, votos e registros ficam em memória. Logs de diagnóstico podem ir para arquivos; não são recuperação persistente.
- Os participantes seguem o protocolo. Autenticação criptográfica e resistência a jogadores que forjem votos não fazem parte desta versão.
- A rede pode atrasar ou interromper conexões. Timeout representa suspeita, não prova de morte.

### Segurança e continuidade são propriedades diferentes

Segurança significa não confirmar resultados conflitantes. Continuidade significa conseguir avançar.

Uma maioria de quatro exige três; uma de três exige dois; uma de dois exige ambos. Se restarem somente dois votantes e um cair, não é possível continuar confirmando pelo protocolo. O participante restante encerra de forma controlada, sem inventar vitória.

Essa é uma limitação concreta: a continuidade após qualquer sequência de desconexões não é garantida. Ela deve ser apresentada e confrontada com a exigência de continuidade do enunciado. O grupo deve demonstrar os cenários suportados e não afirmar tolerância ilimitada.

## 3. Componentes

| Componente | Responsabilidade | Não deve fazer |
|---|---|---|
| core | Configuração, tipos, codec JSON, erros e identificadores | Calcular colisões |
| lobby | Sessões, salas e preparação | Executar partidas |
| game | Estado da arena e transição determinística | Abrir sockets ou ler teclado |
| node/network | Conexões, buffers e entrega de eventos | Alterar a arena |
| node/session | Estados, comandos, histórico, votos e liderança | Desenhar diretamente no terminal |
| node/ui | Teclas e apresentação de uma cópia do estado | Decidir o resultado |

Um único laço de sessão é dono dos dados mutáveis do protocolo. Threads de rede e teclado entregam eventos por filas. Isso evita duas threads alterarem votos ou a arena simultaneamente.

A divisão é uma orientação de organização: nomes de arquivos podem mudar, desde que as responsabilidades permaneçam separadas.

## 4. Rede e transporte

TCP entrega uma sequência de bytes ordenada por conexão. Não define mensagens nem prazo de entrega. Por isso cada JSON termina com LF e o receptor mantém um buffer.

Uma conexão é bidirecional. O menor ID inicia a conexão com o maior. Há três conexões com três jogadores e seis com quatro. Todos abrem a porta P2P antes do registro no lobby.

Use TCP_NODELAY e envio da linha completa. Um socket lento tem sua própria fila; não bloqueia os demais nem o relógio da simulação.

O endpoint anunciado deve ser alcançável pelas outras máquinas. Não anunciar 0.0.0.0; esse endereço é de bind. A porta de escuta P2P é diferente da porta temporária usada ao conectar ao lobby.

## 5. Preparação

1. Abrir a porta P2P; registrar-se no lobby.
2. Criar ou entrar em uma sala.
3. O criador pede início com três ou quatro participantes.
4. O lobby congela a lista e cria match_id e attempt_id novos.
5. Os pares se conectam e medem RTT.
6. Cada jogador envia as médias por destino. O lobby calcula a média de cada jogador até os demais, ordena e desempata por ID.
7. O lobby distribui a mesma configuração completa e seu hash.
8. Cada aplicativo envia READY automaticamente ao host inicial depois de preparar a arena.
9. O host espera todos. Estabelece o primeiro registro de liderança e sincroniza a base.
10. Conduz a contagem e inicia os ciclos.

O criador da sala não precisa ser o host. O ranking é fixado para a partida; orienta candidaturas futuras. Remoções não reordenam os sobreviventes.

Se qualquer participante falhar antes do primeiro ciclo, cancela-se a tentativa e a sala permanece PREPARANDO. Mesmo com três restantes, o criador pede outra tentativa. Para permitir novas entradas, usa CANCEL_PREPARATION e reabre a sala.

Se o criador sair antes do início, assume o presente que entrou há mais tempo. Sala vazia é removida. Se o lobby cair antes de a partida estar efetivamente iniciada, a tentativa é cancelada.

## 6. Contagem: três segundos no total

As filas antigas são limpas antes da preparação para o movimento.

| Tempo no host | Teclado | Motos |
|---|---|---|
| De 0 até 2,5 s | Entradas ignoradas | Paradas |
| De 2,5 até 3 s | Até dois comandos pendentes | Paradas |
| A partir de 3 s | Entrada normal | Ciclos normais |

A janela de entrada são os **últimos 500 ms da contagem**, não uma etapa adicional. Os comandos nela aceitos são preservados.

O host controla os instantes por relógio monotônico e anuncia as fases. Não se presume sincronização perfeita dos relógios das máquinas. Um cliente libera o teclado quando recebe INPUT_OPEN. O atraso de rede reduz sua janela observada; essa diferença será medida, não escondida.

## 7. Comandos

### Validação imediata

O cliente compara a tecla com a última direção aceita pendente. Se não houver pendências, usa a direção oficial.

- Mesma direção: ignorar.
- Oposta: rejeitar localmente.
- Perpendicular: aceitar se houver espaço.
- Fila cheia: ignorar sem substituir anteriores.

A tecla rejeitada não altera a referência. A repetição automática do teclado segue a mesma regra.

Há no máximo dois comandos pendentes, contando enviados e aceitos pelo host, mas ainda não conhecidos como executados. O tamanho da estrutura é o contador. MOVE_ACCEPTED não libera espaço.

### Referência, reserva e validade

O comando inclui o ciclo oficial conhecido quando a tecla foi aceita. O host reserva o primeiro ciclo ainda aberto sem comando desse jogador.

No máximo uma curva por jogador por ciclo. Sem comando aplicável, mantém a direção.

Um comando vence quando:

    ciclo_de_execucao - ciclo_de_referencia >= 3

Referência 42 permite execução em 43 e 44, não em 45. A validade é checada na reserva e antes de executar. É prazo máximo, não tempo de espera.

Um ponto único fecha as entradas do ciclo. Todos os comandos selecionados são retirados nesse ponto; não consultar as filas em momentos diferentes durante o cálculo.

### Limpeza

Quando uma rejeição compromete a sequência, limpam-se todas as pendências daquele jogador. O host aumenta queue_version, informa a direção oficial e espera QUEUE_RESET_ACK antes de aceitar novos comandos dessa versão.

Mensagens antigas são descartadas sem disparar novas limpezas. Na migração, muda a época e todas as filas são reiniciadas. Registros já produzidos pertencem à recuperação; não são apagados como se fossem teclas pendentes.

A entrada local do host passa pelo mesmo caminho. A vantagem natural é somente a ausência do trajeto de rede.

## 8. Motor determinístico

O estado contém dimensão, células ocupadas, motos e resultado.

Uma função step recebe esse estado e até uma direção por moto viva. Ela:

1. Valida as direções.
2. Calcula todos os destinos sem modificar a arena.
3. Resolve paredes, rastros e destinos iguais.
4. Produz o novo estado e o conjunto de alterações.
5. Avalia vitória ou empate.

Convenções:

- Posições iniciais já contam como ocupadas.
- Rastros permanecem após eliminações.
- Troca de posições elimina ambas: os destinos já estavam ocupados.
- Destinos iguais eliminam todas as motos envolvidas.
- Todo destino alcançado dentro da arena fica ocupado, mesmo numa colisão entre motos em célula antes vazia.
- Não gravar célula fora da arena.
- Ao sair da arena, a posição armazenada da moto eliminada permanece a última válida; o destino tentado aparece no evento de colisão.
- Uma eliminação por saída/desconexão é um evento de controle aplicado na fronteira entre movimentos. Não desloca as demais motos. Pode terminar a partida.
- Um sobrevivente vence; zero significa empate.

A regra de eliminação de controle evita mover motos durante uma pausa de transferência. O campo cycle continua identificando o último movimento aplicado.

## 9. Registros e estado em memória

**Comando** é a solicitação individual. **Registro** é uma decisão compartilhada. **Histórico** é a sequência de registros.

Cada registro tem index, epoch, kind, payload, prev_hash e hash. Registros CYCLE também incluem cycle. Outros tipos podem estabelecer liderança, retirar jogador ou mudar votantes.

Exemplo:

    posição 58: resultado do ciclo 43, com comandos de B e C
    posição 59: configuração conjunta
    posição 60: configuração definitiva
    posição 61: resultado do ciclo 44

Cada processo mantém:

- Configuração inicial e hash.
- Histórico, inclusive sufixo provisório.
- commit_index: até onde sabe que foi confirmado.
- last_applied: até onde aplicou ao estado oficial.
- current_epoch e voted_for.
- Configurações de votantes e liderança.
- Arena confirmada, filas e estado da sessão.

O host guarda também next_index/match_index de cada par. Estado candidato é separado do estado confirmado. Pode ser um delta, sem duplicar toda a matriz.

## 10. Replicação e confirmação

1. O líder calcula uma decisão e acrescenta o registro.
2. Envia APPEND aos demais.
3. Cada receptor confere prefixo e conteúdo, armazena e responde imediatamente.
4. O líder reúne a maioria exigida.
5. Avança commit_index e anuncia esse avanço.
6. Todos aplicam os registros confirmados em ordem.

Confirmar armazenamento não é votar se uma colisão foi justa. Receber bytes no sistema operacional também não é armazenar o registro na aplicação.

Um ACK cumulativo até N exige prefixo completo. Cada votante conta uma vez, para o conteúdo e a época corretos.

Somente registros da época atual podem avançar diretamente a confirmação. Confirmar um registro atual confirma seu prefixo anterior. Assim, uma nova liderança replica EPOCH_START depois dos registros recuperados antes de considerá-los oficiais.

A primeira implementação apresenta movimentos apenas depois de confirmados. A frequência normal é fixa; se a confirmação atrasar, a simulação pausa, sem saltar células nem acelerar para compensar. Mantém-se no máximo um ciclo de movimento não confirmado por vez.

## 11. Eleição

A fila é o ranking inicial. A época 1 pertence ao primeiro ID; época E corresponde a ranking[(E-1) % tamanho]. Épocas de IDs já removidos são puladas. Isso dá um único candidato previsto por época e permite percorrer a fila novamente.

Uma suspeita inicia pausa e ELECTION_NOTICE com época maior. O candidato daquela época pede votos. Se estiver atrás, solicita os registros faltantes sem apagar trecho confirmado; se não puder atualizar-se, deixa a tentativa expirar.

Votar exige:

- Candidato previsto e ainda votante.
- Época atual.
- Nenhum voto em outro candidato nessa época.
- Histórico ao menos tão atualizado quanto o local.

Comparar (last_log_epoch, last_log_index) lexicograficamente: primeiro época, depois posição. Igualdade permite voto. A época da eleição não reescreve épocas de registros antigos.

Um voto é guardado antes da resposta. Um processo que já conhece época superior rejeita autoridade inferior. O líder precisa da maioria apropriada, inclusive as duas maiorias na fase conjunta.

O vencedor ainda não libera o jogo: reconcilia registros, confirma EPOCH_START, resolve remoções necessárias e sincroniza a base. Eleição sem progresso percorre candidatos até o prazo total; depois cada processo encerra localmente de forma controlada.

Uma partição não garante que todos encerrem no mesmo instante. A propriedade exigida do algoritmo é não confirmar histórias incompatíveis, não provar que todos estão mortos.

## 12. Recuperação e snapshots

Encontrar o prefixo comum por index, epoch e hash:

- Falta registro: transferir o trecho.
- Registro idêntico: não reaplicar.
- Sufixo provisório incompatível: substituir pela sequência do líder elegível.
- Conflito com registro confirmado: pausar, verificar contexto e prova de confirmação; persistindo o conflito, abortar com diagnóstico.

Nunca sobrescrever posição menor ou igual a commit_index.

Após confirmar a sequência recuperada, o líder envia snapshot completo. Ele contém arena, ciclo, motos, resultado, última posição/época/hash aplicados e votantes. É produzido somente de estado confirmado.

O receptor valida a âncora contra seu histórico, aplica registros faltantes e compara o estado. Não aceita uma matriz arbitrária desconectada do histórico.

Todos os participantes que continuarão confirmam a mesma base. Só então começa a contagem. Quem não responde precisa ser tratado pelo procedimento de falha; não é removido apenas para liberar a espera.

## 13. Mudança dos votantes

Uma moto eliminada pode continuar assistindo e votando. A composição muda somente por registros.

Para retirar D de [A,B,C,D]:

1. Registrar CONFIG_JOINT: antiga [A,B,C,D], nova [A,B,C].
2. Confirmá-lo pelas duas maiorias.
3. Durante a transição, eleições e confirmações exigem ambas.
4. Registrar CONFIG_FINAL.
5. Confirmá-lo também pelas duas maiorias.
6. Depois de confirmado, somente [A,B,C] conta.

Um nó que já armazenou CONFIG_JOINT usa a regra conjunta para votar e aceitar confirmações, mesmo antes de conhecer seu commit. É uma restrição conservadora. CONFIG_FINAL não relaxa para a nova maioria antes de sua confirmação.

Não iniciar outra reconfiguração enquanto uma estiver pendente. Versões de configuração impedem contar respostas pelo grupo errado.

Se houver falha no meio, a recuperação preserva etapas confirmadas e trata o sufixo ainda provisório. Timeout não autoriza desfazer decisão confirmada.

## 14. Saída e transferência

Participante comum: pede saída, continua conectado, sua moto é retirada por registro PLAYER_LEFT e os votantes são reconfigurados. Só depois recebe LEAVE_APPROVED.

Host: confirma o registro em andamento, pausa e solicita a candidatura do próximo elegível. Continua como votante durante a transferência. A nova liderança resolve o histórico, retira a moto anterior, conclui sua remoção e autoriza saída.

Se a retirada terminar a partida, passa-se ao encerramento em vez de fazer uma retomada desnecessária.

Uma falha durante a transferência segue a recuperação normal. Não presumir que o antigo host pode reassumir sozinho porque a transferência demorou.

## 15. Encerramento

O registro terminal é confirmado como os demais. Normalmente é um CYCLE; pode ser PLAYER_LEFT quando uma saída elimina a última adversária entre movimentos.

O host envia o mesmo MATCH_OVER a todos. Cada aplicativo mostra seu resultado individual. Eliminados anteriores não passam a empatar com os últimos sobreviventes.

Todos ainda integrantes confirmam a entrega. Até lá, continuam atendendo rede e guardando os registros. O host só envia SESSION_CLOSE depois dos ACKs necessários ou de remoções confirmadas.

Timeout não é ACK. Se faltar maioria para remover alguém, o fechamento deixa de ser normal e passa a controlado.

Depois de um resultado terminal, novos controles de liderança ou configuração não alteram o resultado esportivo. Resultado conhecido e confirmado não é desfeito por queda posterior. Quem não o conhece tenta recuperar; se não conseguir, informa resultado indisponível, nunca inventa empate.

O usuário escolhe retornar ao lobby ou sair. A escolha pode ser feita enquanto o fechamento ocorre, mas o processo espera a aprovação normal antes de desconectar.

## 16. Estados

| Estado | Entrada/saída principal |
|---|---|
| DESCONECTADO | Conectar ou sair |
| CONECTANDO_LOBBY | REGISTER / REGISTER_OK |
| NO_LOBBY | Criar ou entrar |
| NA_SALA | Aguardar criador |
| PREPARANDO | Malha, RTT, configuração e READY |
| CONTAGEM | Primeiro 2,5 s; teclado bloqueado |
| JANELA_ENTRADA | Últimos 500 ms da mesma contagem |
| EM_PARTIDA | Movimento por registros confirmados |
| SINCRONIZANDO | Eleição, recuperação, transferência ou reconfiguração |
| ENCERRANDO | Resultado confirmado e entrega |
| RESULTADO | Lobby ou saída |

Moto viva/eliminada, líder/seguidor/candidato e votante/observador são dimensões independentes.

Receber uma época maior ou perder sincronização leva a SINCRONIZANDO. A próxima apresentação de movimento só ocorre após a sequência de recuperação e retomada.

## 17. O que demonstrar na apresentação

- Por que sockets TCP não eliminam a necessidade de framing e timeout.
- Como duas curvas são enfileiradas sem permitir inversão instantânea.
- Por que colisões são calculadas simultaneamente.
- Diferença entre comando, ciclo, registro, posição e época.
- Como armazenamento, confirmação e aplicação são separados.
- Por que ranking não substitui votação.
- Como recuperar um ciclo cuja confirmação chegou só a parte dos jogadores.
- Como sair sem deixar dois hosts e por que maioria não pode ser reduzida localmente.
- Qual cenário não consegue continuar por falta de quorum.

Use os roteiros e critérios de [implementacao.md](implementacao.md). A especificação orienta a construção; as garantias precisam ser verificadas nos testes da implementação.
