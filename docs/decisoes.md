# Decisões de arquitetura

Este documento apresenta as escolhas que orientam a implementação do Tron P2P. Cada decisão explica o problema, as alternativas e o comportamento esperado. Os identificadores D01 a D41 permitem localizar uma decisão quando o projeto precisar de revisão.

O jogo começa com três ou quatro processos. O lobby organiza as salas; um jogador atua como host e calcula a partida. Os outros processos mantêm cópias do estado. Uma moto pode ser eliminada sem encerrar o processo de seu jogador.

Cinco conceitos são usados ao longo do texto. Um **comando** é um pedido individual de curva. Um **ciclo** é um passo de movimento. Um **registro** descreve uma decisão compartilhada, como o resultado de um ciclo. A **posição** numera os registros do histórico. A **época** identifica uma tentativa de liderança. Esses contadores têm funções diferentes e não devem ser intercambiados.

## Rede e coordenação

### D01 — Transporte TCP

O sistema deve usar TCP tanto no lobby quanto entre os jogadores. UDP permitiria receber dados recentes sem esperar retransmissões anteriores, mas exigiria tratamento adicional de perda, ordem e confiabilidade na aplicação.

TCP foi escolhido para reduzir esse trabalho em uma partida pequena, executada em rede local. Sua entrega ordenada não dispensa protocolo: cada JSON deve terminar com uma quebra de linha, e a aplicação deve tratar mensagens incompletas, filas e prazos. Uma conexão aberta também não comprova que o processo remoto continua respondendo.

### D02 — Conexões em malha completa

Cada jogador deve manter uma conexão direta com cada um dos demais. A alternativa seria conectar todos somente ao host e estabelecer novas conexões durante uma troca de liderança.

A malha permite que os sobreviventes já tenham canais para eleição e recuperação. Com quatro jogadores são seis conexões bidirecionais. O menor ID inicia a conexão de cada par, evitando duplicatas; todos devem abrir a porta de escuta antes do registro no lobby.

### D03 — Host autoritário com recuperação

Um host deve calcular os movimentos e as colisões. A alternativa de lockstep distribui a execução, mas exige coordenar as entradas de todos antes de cada avanço. Um host fixo simplificaria a entrega, porém sua falha encerraria a partida.

O projeto deve permitir a eleição de outro host e a recuperação do estado. Essa continuidade depende de registros compartilhados e votos; trocar apenas o endereço do coordenador não recupera decisões que estavam em trânsito.

### D04 — Protocolo específico

O projeto deve implementar um protocolo específico para a partida, em vez de Raft completo. O escopo inclui liderança por épocas, votos, registros replicados e alterações dos participantes que votam.

Essa escolha reduz funcionalidades que não são necessárias ao jogo, como persistência e reentrada. Entretanto, não elimina os problemas de consenso. As regras de eleição e confirmação devem funcionar juntas, e a implementação não deve alegar as garantias de Raft apenas por utilizar alguns de seus conceitos.

### D05 — Ranking pela média de RTT

O ranking deve considerar o tempo de ida e volta das mensagens entre jogadores. Medir somente a conexão até o lobby avaliaria um caminho diferente do utilizado durante a partida.

Cada processo mede os demais e envia as amostras ao lobby, que distribui uma classificação única pela média, com desempate por ID. O ranking define a preferência de candidatura. Um jogador bem classificado ainda precisa ter histórico adequado e obter votos para assumir.

## Entrada de comandos

### D06 — Validação imediata

O cliente deve decidir no momento da tecla se ela entra na fila. Esperar uma resposta do host para essa primeira validação tornaria o controle menos responsivo.

A comparação deve usar a última direção aceita pendente ou, sem pendências, a direção oficial da moto. Se a direção atual for direita e já houver uma curva para cima, uma curva seguinte para esquerda é válida. Cada uma será executada em um ciclo distinto. O host deve repetir a validação antes da aplicação.

### D07 — Dois comandos pendentes

A fila deve comportar até dois comandos ainda não executados, incluindo os já enviados ao host. Uma fila longa permitiria acumular vários segundos de curvas antigas; uma única posição reduziria a possibilidade de preparar duas curvas próximas.

Com duas pendências, novas teclas devem ser ignoradas sem substituir as anteriores. O limite deve representar o total do jogador, e não duas posições no cliente mais duas no host.

### D08 — Quantidade derivada da estrutura

A quantidade pendente deve ser obtida pelo tamanho da estrutura que guarda os comandos. Um contador separado poderia divergir do conteúdo após uma rejeição ou limpeza.

Receber a confirmação de aceitação não deve retirar o comando dessa estrutura. A pendência termina quando a execução oficial é conhecida ou quando o comando é rejeitado ou descartado.

### D09 — Ciclo de referência e reserva

O comando deve informar o último ciclo oficial conhecido pelo cliente ao pressionar a tecla. O host deve reservar o primeiro ciclo ainda aberto para aquele jogador, respeitando a ordem e a validade.

Separar referência e execução permite reconhecer o trânsito normal pela rede. O host deve consumir no máximo uma curva por jogador por ciclo; sem curva disponível, a moto mantém a direção. A seleção das entradas deve ser fechada para todos no mesmo ponto do processamento.

### D10 — Validade de três ciclos

O comando deve vencer quando a diferença entre execução e referência atingir três. Uma referência inferior ao ciclo atual não basta para rejeitar, pois a mensagem pode ter atravessado uma fronteira de ciclo durante o trânsito.

Com referência 42, duas curvas podem executar em 43 e 44; em 45, estão vencidas. O limite de dois ciclos foi descartado porque impediria essa sequência. A validade deve ser verificada na reserva e antes da execução, sem obrigar o comando a esperar.

### D11 — Limpeza de sequência comprometida

Se uma rejeição ou expiração invalidar o contexto das curvas seguintes, o sistema deve limpar as pendências daquele jogador. Descartar apenas uma curva pode tornar a próxima uma inversão proibida.

A limpeza deve ter uma nova versão de fila. Cliente e host devem reconciliar a direção oficial e confirmar essa versão antes de novos envios. Comandos antigos ainda em trânsito não podem reaparecer na fila.

### D12 — Migração e tratamento do host

A migração deve limpar os comandos pendentes de todos. Reaproveitar teclas acumuladas durante a pausa poderia produzir curvas inesperadas na retomada.

A entrada local do host deve passar pela mesma validação, reserva e limite. Sua vantagem deve se restringir à ausência do trajeto de rede. Um movimento que já esteja em um registro recuperável não deve ser confundido com uma tecla pendente e apagado pela limpeza.

### D13 — Ajuste dos controles

Taxa de ciclos, capacidade e validade devem ser configuráveis e avaliadas nos testes. A percepção de atraso depende da rede, da espera pelo próximo ciclo e das curvas anteriores.

O cliente deve medir o intervalo entre tecla aceita e movimento oficial. Alterações precisam preservar a coerência entre capacidade e validade e ser iguais para todos da partida.

## Motor e histórico

### D14 — Movimentos simultâneos

O motor deve calcular todos os destinos antes de modificar a arena. Atualizar uma moto e usar sua nova posição para calcular a seguinte daria importância indevida à ordem dos jogadores.

Após determinar os destinos, o motor resolve paredes, rastros e colisões entre motos, aplica os efeitos e verifica o resultado. Com um sobrevivente há vitória; sem sobreviventes, empate.

### D15 — Histórico de decisões executadas

A recuperação deve usar registros dos ciclos e das decisões de controle. Uma lista de teclas enviadas não informa quais chegaram, foram aceitas ou executadas.

Uma posição do histórico pode conter movimentos de vários jogadores. Outra pode alterar a configuração dos votantes sem movimentar motos. Por isso a posição global não é a sequência individual de comandos nem o número do ciclo.

### D16 — Confirmação durante a partida

O host deve distribuir e confirmar registros ao longo do jogo, e não somente ao identificar um vencedor. Isso permite recuperar falhas anteriores ao encerramento.

Os participantes armazenam e respondem; o host obtém o quorum e anuncia a confirmação. Armazenar, confirmar e aplicar são etapas diferentes. A apresentação deve acompanhar os registros confirmados, inclusive no host.

### D17 — Confirmação de prefixo completo

Uma confirmação até a posição N deve significar que todos os registros anteriores estão disponíveis, sem lacunas. Caso contrário, o processo poderia declarar um histórico que não consegue reproduzir.

O participante deve solicitar os trechos ausentes antes de avançar a confirmação. Registros repetidos não devem ser aplicados novamente.

### D18 — Armazenamento em memória

Estado, votos e registros devem permanecer na memória dos aplicativos. Persistência em disco acrescentaria recuperação de processos e tratamento de dados antigos ao escopo.

A continuidade depende dos processos ainda disponíveis. Um processo reiniciado não deve retornar à mesma sessão sem suas informações de época, voto e histórico. Logs de diagnóstico podem ser gravados, mas não substituem esse estado.

## Eleição e recuperação

### D19 — Sucessão com autorização

O próximo candidato deve seguir o ranking compartilhado. Assumir apenas por ser o próximo permitiria dois líderes se os jogadores percebessem a falha em momentos diferentes.

O candidato deve apresentar um histórico elegível e reunir maioria. Se estiver atrasado, pode obter registros compatíveis antes de tentar; se não conseguir, a tentativa deve dar lugar ao próximo.

### D20 — Comparação dos históricos

Um candidato com histórico igual ao do votante deve poder receber voto. Exigir que fosse estritamente melhor impediria eleições quando as cópias fossem idênticas.

A comparação deve considerar primeiro a época do último registro e depois sua posição. Uma época eleitoral nova não transforma registros antigos em novos. A recuperação também deve preservar os registros confirmados, mesmo que alguns participantes ainda desconheçam a confirmação.

### D21 — Um voto por época

Cada participante deve conceder no máximo um voto por época e guardá-lo antes de responder. Permitir votos para candidatos diferentes na mesma tentativa poderia autorizar lideranças incompatíveis.

Uma repetição do pedido do mesmo candidato pode repetir a resposta, mas não criar um segundo voto. Uma época superior inicia outra tentativa, com nova possibilidade de voto.

### D22 — Identificação da liderança

As mensagens de autoridade devem identificar a época e o líder. O ID ter passado na fila não apaga as mensagens que o host antigo ainda possui.

Ao reconhecer uma época superior pelo protocolo, o processo deve abandonar a autoridade anterior e rejeitar suas mensagens antigas. Timeout inicia suspeita; não comprova desligamento nem autoriza liderança sozinho.

### D23 — Falta de maioria

Uma tentativa sem vencedor deve expirar e permitir o próximo candidato em nova época. O episódio inteiro deve ter prazo para evitar espera indefinida.

A maioria não deve ser reduzida para incluir apenas quem responde. Sem progresso seguro, o aplicativo deve encerrar de forma controlada, informando a falta de quorum em vez de declarar um empate esportivo.

### D24 — Recuperação do histórico

O novo líder deve comparar os registros dos sobreviventes, completar o que falta e resolver os trechos provisórios. Não deve impor sua matriz local sem essa verificação.

Se o host confirmou um ciclo e avisou somente B, C ainda pode ter armazenado seu conteúdo sem conhecer o anúncio. Essa cópia deve ser considerada. Um cálculo existente apenas no host perdido não é recuperável.

### D25 — Conflito confirmado

Um registro confirmado não deve ser sobrescrito por votação sobre qual versão parece correta. O sistema deve primeiro verificar partida, posição, época e se houve confirmação real.

Se persistir um conteúdo incompatível com um trecho confirmado, a partida deve ser interrompida por inconsistência. As proteções incluem voto único, correspondência de prefixos, ACK após armazenamento, quorum correto, imutabilidade e aplicação única.

### D26 — Recuperação antes da retomada

A eleição deve ser seguida de reconciliação, confirmação e instalação do estado. Só depois começa a contagem.

Essa ordem permite mostrar durante a pausa a posição e a direção recuperadas. O jogador não deve ver uma curva antiga surgir inesperadamente depois de voltar a jogar. Um registro EPOCH_START da nova época permite confirmar o prefixo recuperado; seu anúncio isolado não basta.

### D27 — Janela nos últimos 500 ms

A contagem deve durar três segundos no total. Nos primeiros 2,5 segundos, as teclas são ignoradas. Nos últimos 500 ms, o jogador pode preparar até dois comandos, ainda com a moto parada.

Uma janela adicional de três segundos foi descartada. As filas antigas devem ser limpas antes da contagem, e as novas teclas devem permanecer para os primeiros ciclos.

## Votantes e saída

### D28 — Composição confirmada

Os processos autorizados a votar formam uma configuração compartilhada. Essa lista não deve ser recalculada localmente conforme os sockets que respondem.

Uma lista fixa até o fim dificultaria saídas sucessivas. Alterações confirmadas permitem remover participantes sem permitir que cada grupo crie sua própria maioria.

### D29 — Transição conjunta

Uma remoção deve passar por uma configuração conjunta. Nessa fase, decisões exigem maioria tanto da lista antiga quanto da nova; o mesmo processo pode contar nas duas.

A entrada na fase conjunta e sua conclusão também devem exigir ambas. Somente depois da confirmação definitiva vale a nova lista. Uma transição por vez evita configurações sobrepostas. A regra conservadora passa a valer ao armazenar a conjunta, para não relaxar a exigência por desconhecimento do anúncio.

### D30 — Moto e processo independentes

O jogador eliminado deve poder continuar assistindo ou solicitar saída. Sua moto morta não implica que seu aplicativo deixou de responder.

Enquanto integrar a configuração, esse processo pode votar. Um host eliminado pode continuar coordenando. Essa separação evita uma troca de liderança desnecessária a cada colisão do host.

### D31 — Saída aprovada

Um participante deve manter a conexão até sua retirada e a configuração estarem resolvidas. Se for host, deve confirmar a pendência, pausar, atualizar o sucessor e transferir a liderança.

Apenas esperar alguns segundos não comprova transferência. Se o host cair durante o procedimento, a recuperação normal deve preservar o que já foi confirmado. O antigo líder não pode reassumir sozinho.

### D32 — Verificação de atividade

Após três intervalos de ciclo sem comandos enviados, o processo deve enviar uma mensagem pequena de atividade. Outras mensagens válidas também podem demonstrar disponibilidade.

O prazo de suspeita deve ser maior que o intervalo de verificação e funcionar nas pausas, usando relógio monotônico. Ausência de teclas não significa falha; TCP também pode demorar a detectar uma interrupção.

### D33 — Respostas sem espera artificial

ACKs e anúncios de confirmação devem ser enviados assim que suas condições forem satisfeitas, sem aguardar o próximo ciclo.

A confirmação já acrescenta comunicação ao caminho da tecla. Filas por conexão e mensagens curtas evitam espera adicional criada pelo código. A aplicação ainda deve medir a latência real.

## Lobby e encerramento

### D34 — Início pelo criador

O criador deve solicitar o início com três ou quatro jogadores. Começar automaticamente impediria controlar se a sala espera pelo quarto.

O papel de criador pertence à organização da sala e não determina o host, escolhido pelo ranking inicial.

### D35 — Participantes congelados

A preparação deve usar uma lista fixa. Permitir entradas durante a medição faria RTT, conexões e posições se referirem a conjuntos diferentes.

Cada tentativa deve possuir identificação própria. Respostas de tentativas anteriores não podem autorizar o início.

### D36 — Prontidão automática

Cada aplicativo deve informar automaticamente que concluiu as conexões e preparou a configuração. Um botão manual acrescentaria uma ação desnecessária ao usuário.

O host deve aguardar todos da tentativa. Conseguir enviar bytes pelo TCP não demonstra que o receptor terminou de preparar sua arena.

### D37 — Falha na preparação

Se um participante cair antes do início, a tentativa deve ser cancelada e a sala permanecer em preparação, mesmo com três restantes.

O criador deve solicitar outra tentativa. Para receber novos jogadores, deve reabrir a sala. Se sair, o participante presente mais antigo assume o controle.

### D38 — Resultado global

O host deve enviar o mesmo vencedor ou empate para todos. Mensagens individuais de vitória e derrota poderiam dificultar a conferência da decisão comum.

Cada aplicativo deve derivar a situação do seu jogador. Quem foi eliminado antes não passa a empatar com os últimos sobreviventes.

### D39 — Confirmação de entrega

O encerramento normal deve aguardar confirmação de todos ainda integrantes da sessão. A maioria confirma a decisão do jogo; todos confirmam sua entrega antes de fechar as conexões.

Timeout não deve ser contado como ACK. Falhas exigem tratamento e remoção confirmada quando possível; sem condições de progresso, o fechamento passa a ser controlado.

### D40 — Escolha após a partida

O usuário deve escolher entre retornar ao lobby e sair. Nenhuma das ações deve ser obrigatória.

Se o lobby estiver indisponível, o aplicativo deve preservar o resultado e permitir nova tentativa ou saída. Isso não deve reabrir a partida.

### D41 — Especificação inicial revisável

Estados e modelos de mensagens são a base inicial da implementação. Os formatos podem ser ajustados quando testes revelarem uma necessidade, desde que participantes e documentação sejam atualizados juntos.

Alterações de comportamento, como relaxar quorum, permitir reentrada ou mudar a janela de teclado, devem ser registradas como revisões de decisão.

## Detalhes técnicos e limites

SHA-256, JSON canônico, campos das mensagens, timeouts, buffers, arena 40×30, oito ciclos por segundo e cinco amostras de RTT são escolhas técnicas iniciais da especificação. Elas tornam o contrato implementável, mas não representam novos requisitos do professor. Os valores devem ser calibrados em testes.

O sistema deve separar configuração aplicada e configuração conservadora de votação. Saídas devem ser aplicadas entre movimentos, sem deslocar as demais motos. O registro START define o início lógico para relatos atrasados.

Dois votantes exigem ambos. Se um falhar, não há quorum para confirmar remoção, liderança ou vitória. A solução não garante continuidade sob qualquer sequência de falhas; essa limitação deve ser demonstrada diante da exigência do trabalho, sem contar apenas quem responde.

Uma revisão deve identificar a decisão, explicar a mudança e atualizar protocolo, arquitetura e testes. A validação exige execução entre máquinas, falhas injetadas e medições; a existência deste documento não comprova o comportamento do programa.
