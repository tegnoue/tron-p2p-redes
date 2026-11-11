# Registro de decisões — Tron P2P

## Objetivo

Permitir que a equipe acompanhe as escolhas de arquitetura, as alternativas consideradas e os motivos apresentados na discussão.

Este documento complementa arquitetura.md e protocolo.md. Não substitui a especificação das mensagens nem significa que os mecanismos de consenso já estejam completamente definidos.

## Como interpretar

- **Confirmada:** escolha explicitamente aceita na discussão.
- **Base inicial:** proposta aceita para começar e revisar durante desenvolvimento e testes.
- **Em aberto:** assunto que ainda precisa de definição.
- As justificativas resumem os argumentos apresentados, não sendo necessariamente citações literais.
- As alternativas são caminhos considerados ou comparados na conversa; nem todas chegaram a constituir propostas completas.

## 1. Requisitos que vieram do enunciado

Estes pontos são obrigações do trabalho, não escolhas livres da equipe:

- Lobby para registro, criação/listagem de partidas e descoberta.
- Comunicação direta entre jogadores durante a partida.
- Partidas iniciadas com três ou quatro jogadores, em processos separados.
- Partidas em andamento independentes da disponibilidade do lobby.
- Concordância sobre colisões, ciclos e resultado.
- Queda de jogador comum elimina sua moto e permite continuar.
- Falha do coordenador permite, no mínimo, encerramento controlado.
- Endereços e portas configuráveis.
- Comunicação diretamente pela API de sockets.
- Protocolo documentado com mensagens, estados e tratamento de falhas.

A equipe escolheu buscar continuidade após a queda do host, além do mínimo permitido pelo enunciado.

## 2. Resumo das escolhas

| Tema | Escolha atual |
|---|---|
| Transporte | TCP com regras na camada de aplicação |
| Topologia | Malha completa |
| Autoridade | Host autoritário, com eleição e recuperação |
| Preferência de host | Ranking pela média de RTT entre os pares |
| Autorização de liderança | Histórico elegível e maioria |
| Entrada | Validação local imediata |
| Fila | Até dois comandos pendentes |
| Aplicação | Host reserva o ciclo; uma curva por jogador por ciclo |
| Validade | Vence ao atingir três ciclos de idade |
| Confirmação | Registros dos ciclos confirmados por maioria |
| Recuperação | Comparar registros, preservar confirmados e reconciliar pendentes |
| Votantes | Composição alterada por decisão confirmada |
| Armazenamento | Memória do aplicativo |
| Início | Solicitado pelo criador, com prontidão automática |
| Encerramento | Resultado global; todos da sessão confirmam a entrega |
| Depois da partida | Usuário escolhe lobby ou saída |
| Estados e JSONs iniciais | Base para desenvolvimento e revisão |

## 3. Rede e autoridade

### D01 — TCP

**Situação:** confirmada.

**Alternativas:** TCP; UDP com tratamento de perda, ordem e confiabilidade na aplicação.

**Decisão:** utilizar TCP no lobby e na partida, complementado por enquadramento, filas, identificação de mensagens, ciclos e timeouts na aplicação.

**Por quê:** para até quatro participantes numa rede local, oferece entrega ordenada e confiável com menor complexidade. Houve preferência explícita por TCP com ajustes na aplicação.

**Consequência:** TCP não oferece prazo de entrega. Precisamos tratar atraso e conexão aparentemente aberta sem atividade.

### D02 — Malha completa

**Situação:** confirmada; escolha já presente no contexto inicial.

**Alternativas:** conectar somente ao host atual; manter conexões entre todos.

**Decisão:** malha completa, com uma conexão TCP bidirecional por par. O menor ID inicia a conexão com o maior.

**Por quê:** os pares já podem se comunicar durante recuperação e transferência, sem estabelecer toda a rede depois da falha do host.

**Consequência:** três conexões com três participantes e seis com quatro. Todos precisam aceitar conexões na preparação.

A malha não distribui automaticamente a autoridade do jogo.

### D03 — Host autoritário com migração

**Situação:** confirmada como direção de arquitetura.

**Alternativas:** host fixo com encerramento controlado; lockstep entre pares; host com migração.

**Decisão:** um host calcula os ciclos; buscamos eleger outro e recuperar a partida se ele falhar.

**Por quê:** centralizar o cálculo simplifica a arbitragem de colisões. A migração permite continuar após a perda do coordenador.

**Consequência:** precisamos preservar registros e definir eleição e recuperação. Trocar apenas o endereço do host não basta.

**Em aberto:** não houve adoção formal de Raft completo nem fechamento de um algoritmo próprio equivalente. A maioria foi aceita; o algoritmo completo ainda exige especificação.

### D04 — Ranking pela média de RTT entre jogadores

**Situação:** confirmada.

**Alternativas:** ping até o lobby; medições entre os pares; ordem por ID. Também foi sugerido minimizar o pior RTT, mas a escolha final foi média.

**Decisão:** medir RTT entre os participantes e construir um ranking único pela média. O lobby consolida as informações durante a preparação.

**Por quê:** ping até o lobby mede outro caminho de rede. O ranking deve representar as conexões da partida e ser igual para todos.

**Consequência:** o ranking estabelece preferência. Histórico elegível e maioria continuam necessários. O candidato preferencial desatualizado se atualiza ou outro assume.

## 4. Comandos

### D05 — Validação local imediata

**Situação:** confirmada.

**Alternativas:** esperar resposta do host; decidir localmente na tecla e validar novamente no host.

**Decisão:** decidir imediatamente se a tecla entra na fila, considerando a última direção aceita pendente. Sem pendências, considerar a direção oficial conhecida.

**Por quê:** oferecer resposta imediata e permitir sequências como DIREITA → CIMA → ESQUERDA, executadas em ciclos distintos.

**Consequência:** tecla rejeitada não muda a referência. Direção repetida não ocupa espaço. O host também valida.

### D06 — Dois comandos pendentes

**Situação:** confirmada; valor ajustável nos testes.

**Alternativas:** fila longa; um ou dois pendentes; contador separado ou tamanho da estrutura.

**Decisão:** até dois pendentes no total, incluindo enviados e ainda não executados. Utilizar o tamanho da estrutura de pendências como contador.

**Por quê:** permitir antecipação sem acumular vários segundos de comandos antigos; evitar divergência entre contador e conteúdo.

**Consequência:** fila cheia ignora a nova tecla. A aceitação pelo host não libera espaço; execução oficialmente conhecida, rejeição ou descarte encerram a pendência.

### D07 — Referência do cliente e execução reservada pelo host

**Situação:** confirmada.

**Alternativas:** cliente determinar sozinho o ciclo; host executar conforme chegada sem registrar reserva; distinguir referência e execução.

**Decisão:** o cliente informa seu ciclo de referência. O host reserva o primeiro ciclo ainda aberto, respeitando ordem, capacidade e validade.

**Por quê:** reconhecer o trânsito pela rede e tornar explícito quando o comando será aplicado.

**Consequência:** uma mudança de direção por jogador por ciclo. Sem comando, mantém-se a direção. O fechamento das entradas é comum a todos.

### D08 — Expiração ao atingir três ciclos

**Situação:** confirmada; ajustável nos testes.

**Alternativas:** descartar toda referência inferior ao ciclo atual; validade de dois ciclos; validade de três.

**Decisão:** descartar quando:

    ciclo_de_execucao - ciclo_de_referencia >= 3

**Por quê:** referências inferiores podem resultar de trânsito normal. Dois ciclos, com esse critério, impediriam executar duas curvas geradas na mesma referência.

**Exemplo:** referência 42 permite execução em 43 e 44. No 45, venceu.

**Consequência:** validade não é espera obrigatória. Verificar na reserva e antes da execução.

### D09 — Limpar a sequência comprometida

**Situação:** confirmada; reconciliação ainda precisa de formato.

**Alternativas:** descartar só o comando inválido; manter os posteriores; limpar as pendências do jogador.

**Decisão:** quando rejeição ou expiração comprometer a sequência, limpar as pendências daquele jogador e recomeçar.

**Por quê:** comandos posteriores podem depender da curva descartada e produzir movimentos inválidos ou atrasados.

**Consequência:** cliente e host precisam concordar sobre a limpeza. Uma versão da fila invalida comandos antigos em trânsito.

### D10 — Limpeza na migração e tratamento do host

**Situação:** confirmada.

**Alternativas:** reaproveitar comandos após a pausa; descartar pendências; executar teclas locais do host diretamente.

**Decisão:** migração limpa todas as pendências. O host usa a mesma validação, fila e limite dos demais.

**Por quê:** evitar curvas acumuladas durante a pausa e prioridade criada pelo código.

**Consequência:** permanece a vantagem natural de latência do host. Movimentos incorporados ao histórico recuperado não são comandos pendentes.

### D11 — Ajustar controles por testes

**Situação:** confirmada como diretriz.

**Alternativas:** fixar parâmetros definitivamente; ajustar por medições.

**Decisão:** manter taxa de ciclos, capacidade e validade configuráveis e medir tecla até movimento oficial.

**Por quê:** reduzir atraso exige observar rede, cadência e espera na fila.

**Consequência:** mudanças precisam preservar a coerência entre capacidade e validade e ser compartilhadas por todos.

## 5. Ciclos e recuperação

### D12 — Calcular movimentos conjuntamente

**Situação:** confirmada como fluxo geral.

**Alternativas:** atualizar cada moto imediatamente; calcular todos os destinos antes de alterar a arena.

**Decisão:** selecionar comandos, calcular destinos, resolver colisões, aplicar efeitos e avaliar vitória ou empate.

**Por quê:** impedir que a ordem de processamento favoreça um jogador.

**Consequência:** os casos de colisão ficam documentados no motor e precisam de testes. As regras do enunciado não são escolhas novas da equipe.

### D13 — Registrar o que foi executado

**Situação:** confirmada.

**Alternativas:** recuperar pelas teclas enviadas; recuperar pelos registros dos ciclos calculados.

**Decisão:** manter registros ordenados de ciclos e decisões de controle, identificando comandos aplicados e seus efeitos.

**Por quê:** uma tecla pode ter sido rejeitada, vencido ou não chegado. Não basta para reconstruir o resultado.

**Consequência:** posição no registro e ciclo do jogo são conceitos diferentes. Não usaremos uma pilha para desfazer movimentos confirmados.

### D14 — Confirmar ciclos por maioria

**Situação:** confirmada em comportamento; algoritmo completo pendente.

**Alternativas:** confirmar somente no final; confirmar durante a partida. Esperar todos ou obter maioria.

**Decisão:** distribuir registros durante a partida, obter confirmações de armazenamento por maioria e anunciar o avanço confirmado.

Confirmar até N significa armazenar toda a sequência até N.

**Por quê:** permitir recuperação se o host cair durante a partida ou durante o anúncio de confirmação.

**Consequência:** confirmação não é votação sobre a colisão. Com quatro votantes, maioria de três; com três, de dois. Lacunas precisam ser preenchidas.

### D15 — Comparar e reconciliar os históricos

**Situação:** confirmada como política; regras exatas pendentes.

**Alternativas:** apagar tudo que algum participante desconheça como confirmado; impor o estado local do sucessor; comparar registros.

**Decisão:** consultar participantes, recuperar registros ausentes, preservar os ciclos confirmados e resolver os pendentes.

**Por quê:** o host pode ter confirmado um ciclo e caído antes de avisar todos. Não podemos apagar essa decisão.

**Consequência:** o atrasado recebe os registros ausentes. Não reenviamos teclas para inventar novamente o resultado.

Algo existente somente na memória do host perdido não pode ser recuperado.

### D16 — Recuperar antes de retomar

**Situação:** confirmada.

**Alternativas:** retomar assim que houver candidato; recuperar e sincronizar primeiro.

**Decisão:** eleger, recuperar, confirmar a sequência, sincronizar o estado e só depois preparar a retomada.

**Por quê:** todos precisam conhecer a posição e direção de onde continuarão. Uma curva recuperada deve aparecer durante a pausa.

**Consequência:** movimento recuperado não é executado novamente.

**Detalhe temporal a esclarecer:** foram aceitas uma contagem de três segundos e uma janela de entrada de três segundos. A organização proposta separou as fases, totalizando seis segundos.

A intenção de duas fases ou de uma única janela deve ser confirmada ao implementar a experiência de retomada.

### D17 — Minimizar a latência

**Situação:** confirmada como objetivo; técnicas são encaminhamentos.

**Alternativas:** esperar o próximo tick para confirmar; responder assim que os registros chegam.

**Decisão:** processar confirmações imediatamente, oficializar assim que houver maioria e evitar espera artificial.

**Por quê:** a confirmação já acrescenta comunicação entre tecla e movimento.

**Encaminhamentos:** envios sem bloquear outros pares, mensagens curtas, TCP_NODELAY e anúncio de confirmação sem reenviar toda a atualização.

A escolha entre threads, selectors ou outra organização com sockets permanece de implementação.

## 6. Votantes e saída

### D18 — Atualizar votantes por decisão confirmada

**Situação:** confirmada; procedimento completo pendente.

**Alternativas:** manter os originais; atualizar por decisão confirmada; cada processo recalcular quem responde.

**Decisão:** a composição faz parte do estado compartilhado e muda pelo protocolo.

**Por quê:** evitar participantes ausentes presos na composição e maiorias incompatíveis.

**Encaminhamento aceito na discussão:** configuração conjunta, com maiorias antiga e nova, uma mudança por vez.

**Consequência:** dois votantes exigem ambos. Sem condições de aprovar a mudança, ninguém se declara uma configuração menor.

### D19 — Separar eliminação e desconexão

**Situação:** confirmada.

**Alternativas:** eliminado desconecta; permanece espectador; escolhe sair com segurança.

**Decisão:** o eliminado pode continuar assistindo ou solicitar saída. O host pode coordenar mesmo com a moto eliminada.

**Por quê:** perder no jogo não equivale a falhar como participante do protocolo.

**Consequência:** eliminar a moto não remove automaticamente o processo da votação.

### D20 — Saída segura e transferência planejada

**Situação:** confirmada.

**Alternativas:** fechar imediatamente; aguardar transferência e remoção confirmadas.

**Decisão:** solicitar saída e manter conexão até aprovação. O host conclui ciclo, pausa, atualiza o sucessor e transfere a liderança.

**Por quê:** evitar perda de informações e permitir continuidade.

**Consequência:** se cair antes de concluir, aplica-se recuperação por falha. Esperar alguns segundos não comprova transferência.

### D21 — Verificação de atividade

**Situação:** confirmada; timeout exato pendente.

**Alternativas:** confiar apenas no TCP; interpretar ausência de comandos como falha; mensagens pequenas de atividade.

**Decisão:** após três intervalos de ciclo sem comandos, enviar atividade e repetir enquanto necessário.

**Por quê:** o jogador pode ficar sem teclas, e uma conexão TCP pode parecer aberta após interrupção.

**Consequência:** usar relógio monotônico, inclusive nas pausas. Intervalo de envio não é timeout de desconexão. Outras mensagens válidas também demonstram atividade.

### D22 — Histórico em memória

**Situação:** confirmada.

**Alternativas:** memória; persistência em disco ou banco.

**Decisão:** guardar estado e registros dentro do aplicativo, em memória.

**Por quê:** atende à recuperação entre processos ainda disponíveis sem adicionar persistência.

**Consequência:** reiniciar perde essa memória. O retorno do processo à mesma partida foi apresentado como fora do escopo inicial, mas ainda precisa ser formalizado como regra.

## 7. Lobby e início

### D23 — Criador solicita o início

**Situação:** confirmada.

**Alternativas:** início automático; criador solicitar com três ou quatro.

**Decisão:** o criador inicia a preparação.

**Por quê:** permitir começar com três ou esperar pelo quarto sob controle do grupo.

**Consequência:** criador e host são papéis independentes.

### D24 — Congelar participantes na preparação

**Situação:** confirmada.

**Alternativas:** permitir entradas durante a preparação; congelar a tentativa.

**Decisão:** fixar a lista em PREPARANDO, montar a malha, medir RTT e distribuir uma configuração compartilhada.

**Por quê:** conexões, ranking e posições precisam referir-se ao mesmo conjunto.

**Consequência:** tentativas têm identificações próprias. Respostas antigas não autorizam início.

### D25 — Prontidão automática

**Situação:** confirmada.

**Alternativas:** botão manual; iniciar sem confirmação; confirmação automática.

**Decisão:** cada aplicativo envia “estou pronto” após concluir conexões e preparar a configuração.

O host aguarda os participantes da tentativa.

**Por quê:** garantir preparação sem exigir ação extra do usuário. Enviar bytes não prova que o outro aplicativo terminou o processamento.

### D26 — Queda cancela a tentativa

**Situação:** confirmada.

**Alternativas:** começar com os restantes se ainda houver três; cancelar e exigir nova solicitação.

**Decisão:** cancelar a tentativa e permanecer PREPARANDO, mesmo com quantidade suficiente.

**Por quê:** a tentativa anterior usava outra lista e configuração; o início continua sob controle do criador.

**Consequência:** para receber novos jogadores, reabrir a sala. O protocolo inicial propõe CANCEL_PREPARATION.

Se o criador sair, a proposta é transferir ao integrante presente mais antigo.

## 8. Encerramento e evolução

### D27 — Resultado global e entrega confirmada por todos

**Situação:** confirmada.

**Alternativas:** resultados individuais; resultado global. Fechar imediatamente; aguardar confirmações.

**Decisão:** confirmar o ciclo final, distribuir resultado global e deixar cada aplicativo resolver sua apresentação.

O encerramento normal aguarda confirmação de todos ainda integrantes da sessão.

**Por quê:** todos usam a mesma decisão e a conexão não fecha antes da entrega.

**Consequência:** timeout não é confirmação. Falhas exigem tratamento e remoção segura quando possível.

A maioria confirma a decisão; todos da sessão confirmam sua entrega.

### D28 — Lobby ou saída por escolha

**Situação:** confirmada.

**Alternativas:** retorno obrigatório; fechamento automático; escolha do usuário.

**Decisão:** oferecer voltar ao lobby ou sair após o procedimento de encerramento.

**Por quê:** são intenções diferentes e nenhuma deve ser imposta.

**Consequência:** lobby indisponível não altera o resultado. Permitir tentar novamente ou sair.

### D29 — Estados e JSONs como base inicial

**Situação:** base inicial explicitamente aceita.

**Alternativas:** desenho imutável; revisão conforme implementação e testes.

**Decisão:** adotar os estados propostos e os JSONs iniciais do lobby, ajustando quando necessário.

**Por quê:** permitir avançar com um contrato comum sem presumir que todos os casos foram descobertos.

**Consequência:** atualizar documentos e implementações juntos. Os JSONs P2P ainda não foram todos discutidos e aprovados.

## 9. Evidências de decisões importantes

Trechos literais da conversa:

| Tema | Trecho |
|---|---|
| TCP | “Vejo o TCP com ajustes na camada de APlicação como a melhor forma.” |
| Capacidade | “Dois comandos pendentes está ótimo” |
| Consumo | “O host atribui o comando conforme a fila. COnsumindo apenas 1 por jogador” |
| Migração | “Se houver migração antes da execução, descartar todos os comandos.” |
| Limpeza | “Aí descarta tudo da fila de comandos do jogador e rrecomeça.” |
| Validade final | “vamos deixar em 3 ciclos mesmo então?” |
| RTT | “sendo ranqueados através da média de RTT” |
| Votantes dinâmicos | “A segunda é ideal por enquanto eu acredito” |
| Memória | “isso em memória dentro do aplicativo em si” |
| Início | “a partida deve ser iniciada pelo criador” |
| Encerramento | “ele deve confirmar com todos aantes de finalizar” |
| Depois da partida | “Ele deve voltar ao lobby ou sair do aplicativo, deve sr opcional” |

## 10. O que ainda não está fechado

Não apresentar estes itens como decisões completas:

- Adoção de Raft completo ou equivalência do protocolo específico.
- Predicado de elegibilidade e regras completas de voto e época.
- Tratamento de todos os conflitos de registros.
- Ativação das configurações conjunta e definitiva.
- JSONs e transições completas P2P.
- Timeouts, taxa de ciclos, arena, spawns e amostras de RTT.
- Limites de mensagem e tratamento de erros estruturais.
- Reconciliação após limpeza de fila.
- Encerramento sem maioria.
- Forma final da contagem e da janela de entrada.
- Regra formal para processo reiniciado.

O registro de nova liderança para confirmar o prefixo recuperado foi proposto e aceito como direção.

Seu funcionamento depende das regras completas de replicação e eleição. Uma mensagem de anúncio isolada não oferece essa garantia.

## 11. Como revisar uma decisão

1. Referenciar seu ID.
2. Registrar a nova escolha e o motivo.
3. Indicar se substitui a anterior.
4. Atualizar arquitetura.md e protocolo.md.
5. Definir os testes afetados.

Revisões já ocorridas:

- Ping até o lobby foi substituído por RTT entre pares.
- Validade de dois ciclos foi reconsiderada; ficou em três para acomodar dois comandos com a mesma referência.
- A prontidão foi definida como automática.
- A entrega final exige confirmação de todos ainda integrantes da sessão.

Decisões confirmadas podem mudar, mas a revisão precisa ser explícita para a equipe não implementar versões diferentes.