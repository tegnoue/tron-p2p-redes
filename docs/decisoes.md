# Registro de decisões — Tron P2P

## 1. Como usar este arquivo

Este registro permite à equipe acompanhar as escolhas feitas na discussão, as alternativas consideradas e os motivos. Os outros documentos descrevem diretamente o contrato técnico.

- **Confirmada:** decisão explicitamente aceita, inclusive como parte de uma proposta.
- **Base inicial:** organização aceita para implementar e ajustar.
- **Escolha técnica inicial:** detalhe preenchido na especificação para tornar possível implementar; não é apresentado como fala ou decisão explícita do grupo.
- Aprovar uma ideia de arquitetura não significa que sua implementação distribuída esteja testada.

Requisitos do professor não são alternativas livres: lobby, comunicação direta, três ou quatro jogadores no início, processos separados, sockets, configuração e concordância do resultado são obrigações.

## 2. Rede e autoridade

| ID | Alternativas consideradas | Decisão e situação | Motivo e consequência |
|---|---|---|---|
| D01 | TCP; UDP com confiabilidade e ordem na aplicação | **Confirmada:** TCP no lobby e no jogo | Menor escopo de comunicação para poucos processos. A aplicação ainda precisa de framing, filas e prazos. |
| D02 | Conectar apenas ao host; malha completa | **Confirmada:** malha completa, uma conexão por par | Facilita recuperação e comunicação entre sucessores. Quatro jogadores usam seis conexões. |
| D03 | Host fixo; lockstep; host com migração | **Confirmada:** host autoritário com eleição e recuperação | Cálculo central facilita arbitragem, com possibilidade de continuar após falha. |
| D04 | Raft completo; protocolo específico | **Confirmada:** protocolo específico para este jogo | Raft completo foi considerado complexo para o escopo. Usaremos regras conhecidas de voto, época, log e maioria, sem alegar equivalência automática a Raft. |
| D05 | Ping até lobby; RTT entre pares; ordem por ID | **Confirmada:** ranking único pela média de RTT entre pares | A rede relevante é a da partida. O lobby consolida a preferência; votação continua obrigatória. |

O início usa a porta P2P aberta e identificada. O menor ID inicia cada conexão. Essa foi uma convenção técnica aceita para evitar duplicatas.

## 3. Comandos

| ID | Alternativas consideradas | Decisão e situação | Motivo e consequência |
|---|---|---|---|
| D06 | Esperar o host; validar na tecla | **Confirmada:** validação local imediata pela última direção aceita | Responsividade e sequência de curvas coerente. Tecla rejeitada não altera a referência. |
| D07 | Fila longa; um ou dois pendentes | **Confirmada:** dois pendentes no total | Permite antecipação sem acumular comandos por muitos segundos. Inclui enviados e não executados. |
| D08 | Contador separado; tamanho da estrutura | **Confirmada:** usar tamanho da fila de pendências | Evita divergência entre quantidade e conteúdo. Aceitação não libera espaço. |
| D09 | Cliente escolher execução; host reservar | **Confirmada:** referência do cliente e reserva pelo host | Separa momento da solicitação e aplicação real; no máximo uma curva por jogador por ciclo. |
| D10 | Rejeitar referência menor; vencer em dois ou três ciclos | **Confirmada:** vence ao atingir três ciclos | Dois ciclos, no critério de idade >= limite, impediriam duas curvas com a mesma referência. |
| D11 | Descartar só o inválido; manter resto; limpar sequência | **Confirmada:** limpar pendências quando perderem contexto | Evita curvas que dependiam da descartada e sensação de comandos antigos. |
| D12 | Preservar teclas da pausa; limpar; prioridade local do host | **Confirmada:** limpar na migração e aplicar mesmas regras ao host | Evita teclas acumuladas e privilégios criados pelo código. Resta a diferença natural de rede. |
| D13 | Parâmetros definitivos; ajustar com medições | **Confirmada:** parâmetros configuráveis e testes | Medir tecla até movimento distingue espera de tick, fila e rede. |

Referência 42 permite executar em 43 e 44. No 45, o comando venceu. Três ciclos são validade máxima, não espera.

A especificação usa versões de fila e ACK de limpeza. São mecanismos para cumprir D11; seus nomes de campos são escolhas técnicas iniciais.

## 4. Motor e histórico

| ID | Alternativas consideradas | Decisão e situação | Motivo e consequência |
|---|---|---|---|
| D14 | Atualizar uma moto por vez; calcular destinos juntos | **Confirmada:** transição simultânea | Ordem de processamento não favorece jogador. As regras esportivas vêm do enunciado. |
| D15 | Recuperar pelas teclas; pelos registros de resultados | **Confirmada:** registros de ciclos e controles | Teclas não informam o que chegou e foi aplicado. |
| D16 | Confirmar só no fim; durante o jogo | **Confirmada:** confirmar registros durante a partida por maioria | Permite recuperar uma falha anterior ao fim. Armazenamento, confirmação e aplicação são distintos. |
| D17 | ACK isolado; prefixo cumulativo | **Confirmada:** confirmar N exige todos até N | Impede histórico com lacunas. Registro ausente é solicitado. |
| D18 | Memória; persistência em disco | **Confirmada:** estado e histórico em memória | Escopo menor. A versão inicial não aceita retorno de processo reiniciado. |

Posição no histórico é global. Um registro pode conter movimentos de vários jogadores ou uma mudança de votantes. Não se confunde com a sequência de teclas de cada jogador.

## 5. Eleição e recuperação

| ID | Alternativas consideradas | Decisão e situação | Motivo e consequência |
|---|---|---|---|
| D19 | Sucessor assumir sozinho; pedir votos | **Confirmada:** fila de sucessão, histórico elegível e maioria | Ranking é preferência, não autorização. O preferencial se atualiza ou outro tenta. |
| D20 | Histórico estritamente melhor; igual também elegível | **Confirmada:** igualdade permite voto | Cópias idênticas não devem bloquear a eleição. Compara-se época do último registro e depois posição. |
| D21 | Mais de um voto; voto único por época | **Confirmada:** um voto por participante por época | Impede autorizações conflitantes na mesma tentativa. Guardar voto antes de responder. |
| D22 | Assumir após timeout; usar épocas e identidade | **Confirmada:** época distingue lideranças | Timeout suspeita; mensagem antiga não recupera autoridade. |
| D23 | Repetir indefinidamente; reduzir quorum; limitar tentativas | **Confirmada:** próximos candidatos e prazo total | Sem maioria suficiente, encerrar de forma controlada. Não inventar uma lista menor. |
| D24 | Apagar pendentes; impor matriz local; reconciliar logs | **Confirmada:** preservar confirmados e resolver provisórios | Uma confirmação pode ter sido anunciada parcialmente. |
| D25 | Escolher conflito confirmado por maioria; parar | **Confirmada:** verificar e abortar se o conflito for real | Um trecho confirmado não deve ser sobrescrito. É violação de segurança, não votação sobre a verdade. |
| D26 | Retomar ao eleger; recuperar antes | **Confirmada:** eleição, recuperação, sincronização e contagem | Evita apresentar curva recuperada inesperadamente depois da retomada. |
| D27 | Contagem + janela extra; uma contagem com janela no final | **Confirmada final:** três segundos totais, entrada só nos últimos 500 ms | Elimina a ambiguidade de seis segundos. As filas antigas são limpas antes; as novas teclas são preservadas. |

As regras preventivas aprovadas são: voto único, comparação de histórico, quorum da configuração correta, correspondência de prefixos, ACK após armazenamento, confirmação na época atual, imutabilidade e aplicação única.

O registro de estabelecimento da nova liderança permite confirmar o prefixo recuperado. Seu detalhamento usa o contrato de replicação; não é apenas uma mensagem dizendo “sou o líder”.

## 6. Votantes, atividade e saída

| ID | Alternativas consideradas | Decisão e situação | Motivo e consequência |
|---|---|---|---|
| D28 | Votantes fixos; decisão confirmada; recálculo local | **Confirmada:** composição alterada pelo histórico | Saídas não podem criar maiorias incompatíveis. |
| D29 | Mudança direta; fase conjunta | **Confirmada:** conjunta, depois definitiva | A entrada, decisões intermediárias e finalização exigem maiorias antiga e nova. Nova simples só após final confirmado. |
| D30 | Eliminado desconecta; espectador; escolha de saída | **Confirmada:** pode assistir ou sair com segurança | Moto eliminada e processo votante são condições diferentes. Host morto no jogo pode coordenar. |
| D31 | Fechar imediatamente; transferência e remoção | **Confirmada:** aguardar aprovação | Evita perder informação. Se o host cair no meio, segue recuperação. |
| D32 | Só TCP; só teclas; atividade explícita | **Confirmada:** mensagem pequena após três intervalos sem comandos | Inatividade no teclado não é desconexão; TCP pode demorar a detectar falhas. |
| D33 | Esperas até tick; resposta imediata | **Confirmada:** reduzir esperas artificiais | ACK e anúncio de confirmação não aguardam o próximo tick. |

Na fase conjunta, decisões usam as duas listas. Ao armazenar a transição, a versão inicial usa a exigência conjunta conservadora também para votar. Essa é uma escolha técnica da especificação para não relaxar quorum por falta de anúncio.

## 7. Lobby e encerramento

| ID | Alternativas consideradas | Decisão e situação | Motivo e consequência |
|---|---|---|---|
| D34 | Início automático; criador solicita | **Confirmada:** criador inicia com três ou quatro | Permite esperar pelo quarto ou jogar com três. |
| D35 | Entrada durante preparação; congelar tentativa | **Confirmada:** lista congelada | RTT, conexões, ranking e spawns usam o mesmo conjunto. |
| D36 | Botão pronto; sem confirmação; pronto automático | **Confirmada:** READY automático e aguardar todos | Sem ação extra do usuário, mas com verificação de preparação. |
| D37 | Começar com restantes; cancelar se alguém cair | **Confirmada:** cancelar antes do início e manter PREPARANDO | Mesmo com três, o criador solicita nova tentativa. |
| D38 | Resultados individuais na rede; resultado global | **Confirmada:** resultado global | Todos conhecem a mesma decisão; aplicativo mostra a situação individual. |
| D39 | Fechar ao enviar; maioria de entrega; todos | **Confirmada:** todos ainda integrantes confirmam entrega | Maioria confirma a decisão; todos confirmam recebimento antes do fechamento normal. Timeout não é ACK. |
| D40 | Lobby obrigatório; sair automático; escolha | **Confirmada:** lobby ou sair, opcional | A indisponibilidade do lobby não muda o resultado. |
| D41 | Documentos imutáveis; base revisável | **Base inicial:** estados e modelos de mensagens podem evoluir | A equipe aceitou uma proposta inicial de formatos e ajustes posteriores. |

## 8. Detalhes técnicos preenchidos na versão 1

Estes itens tornam o contrato implementável. São escolhas técnicas iniciais, não novas falas atribuídas ao grupo:

- SHA-256 e JSON canônico para identificar registros e snapshots.
- Envelope com IDs por conexão e correlação de respostas.
- Tipos e nomes de mensagens completos em protocolo.md.
- Padrão de 8 ciclos/s, timeouts e limites de buffers.
- Arena 40×30 e pontos de partida afastados das bordas.
- Cinco amostras de RTT por destino.
- Laço de sessão como único dono dos dados.
- Sem adição de jogadores ou reentrada durante partida.
- Eventos de saída aplicados entre movimentos, sem deslocar os demais.
- Registro START define o início lógico para mensagens atrasadas.
- Atualização de README para distinguir contrato de código implementado.

Os valores são calibráveis pelos testes. Alterações de campos incompatíveis exigem revisão do contrato.

## 9. Limites que precisam ser apresentados

A escolha por maioria implica um limite: dois votantes precisam de ambos. Se um falhar, não há quorum para confirmar vitória, remoção ou novo líder.

A documentação não afirma continuidade sob qualquer sequência de falhas. Esse cenário precisa ser demonstrado e avaliado frente ao requisito de continuidade de jogador comum. Não esconder essa limitação nem “resolvê-la” contando apenas quem responde.

Também não há prova de resistência a fraude, retorno de processo sem memória ou entrega de resultado a máquinas que desapareceram.

## 10. Revisões encerradas

| Assunto | Proposta anterior | Regra vigente |
|---|---|---|
| RTT | Medir só até o lobby | Medir entre jogadores |
| Validade | Reduzir para dois ciclos | Vence ao atingir três |
| Algoritmo | Dúvida sobre Raft completo | Protocolo específico |
| Prontidão | Etapa potencialmente manual | Automática |
| Retomada | Possíveis três segundos + três extras | Três segundos, últimos 500 ms aceitam teclas |
| Confirmação final | Prazo sem entrega de todos | Todos da sessão no encerramento normal |
| Eleição | Critérios ainda genéricos | Época, posição, igualdade, voto único e prazo definidos |

## 11. Como alterar uma decisão

Referenciar o ID, indicar regra antiga e nova, explicar o motivo, atualizar protocolo/arquitetura e acrescentar os testes afetados.

Questões de formato e implementação podem ser resolvidas pela proposta inicial autorizada. Mudanças de comportamento, como relaxar quorum, permitir reentrada ou alterar a janela de teclado, precisam ser registradas como revisão real.

O trabalho restante é implementar, executar os cenários e ajustar os valores com evidências. Não confundir ter um documento detalhado com ter validado o programa.
