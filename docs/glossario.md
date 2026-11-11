# Glossário do projeto

Use este arquivo como consulta. Os nomes dos campos do protocolo aparecem ao lado do conceito para facilitar a leitura do código.

## 1. As cinco palavras que mais causam confusão

| Termo | Significado | Exemplo |
|---|---|---|
| Comando | Pedido individual de mudança de direção | B pediu UP |
| Ciclo | Um passo de movimento do jogo | No ciclo 43, cada moto viva anda uma célula |
| Registro | Entrada que descreve uma decisão compartilhada | Resultado do ciclo 43 ou retirada de um votante |
| Posição no histórico, index | Número global de um registro | Registro 58 pode conter movimentos de vários jogadores |
| Época, epoch | Número de uma tentativa de liderança | A liderou na época 1; B tenta a 2 |

Não são três nomes para um contador.

Um comando pode nunca ser executado. Um ciclo reúne movimentos de várias motos. Uma posição pode guardar uma decisão sem movimento. A época muda sem reiniciar o ciclo.

~~~text
Comando de B: sequência 17, referência 42, época 2
Host reserva: ciclo 43
Histórico:
  posição 58, época 2: resultado do ciclo 43
  posição 59, época 2: configuração conjunta
  posição 60, época 2: configuração definitiva
  posição 61, época 2: resultado do ciclo 44
~~~

## 2. Rede

**Processo:** programa em execução, com sua própria memória. Dois jogadores no mesmo computador continuam precisando de processos e portas distintos.

**Nó ou peer:** processo participante da partida. Pode enviar e receber; não é somente cliente.

**Lobby:** serviço que registra jogadores e organiza salas. Não arbitra o jogo iniciado.

**Host ou líder:** jogador que atualmente propõe os registros e calcula os movimentos. Não é uma máquina externa obrigatória.

**Seguidor:** participante que recebe registros e pode votar numa eleição.

**Candidato:** participante tentando obter votos para liderar numa época.

**Socket:** objeto da API de rede usado para ouvir, conectar, enviar e receber bytes.

**Bind:** associar o socket a uma interface e porta locais. 0.0.0.0 significa ouvir nas interfaces disponíveis; não é endereço para anunciar aos pares.

**Endpoint:** endereço alcançável e porta. Exemplo: 192.168.1.10:6001.

**Malha completa:** conexão direta para cada par. Quatro processos exigem seis conexões bidirecionais.

**TCP:** transporte que entrega bytes em ordem por conexão e retransmite perdas. Não garante que cada recv corresponda a uma mensagem nem que os bytes cheguem dentro do prazo do jogo.

**UDP:** transporte por datagramas. Foi alternativa considerada; perda e ordenação precisariam de tratamento adicional. Não é o transporte escolhido.

**Framing ou enquadramento:** regra que separa mensagens dentro do fluxo TCP. Aqui, uma linha JSON termina em LF.

**Buffer de recepção:** bytes já recebidos, mas ainda não consumidos como mensagens completas.

**Fila de envio:** mensagens esperando escrita no socket. Impede um par lento de bloquear todos os outros.

**Handshake:** troca inicial de identificação e aceitação. PEER_HELLO é o handshake da aplicação; não se confunde com o estabelecimento interno do TCP.

**RTT:** tempo entre enviar uma medição e receber sua resposta. Usa ida e volta; não exige relógios sincronizados.

**Latência:** atraso de uma ação. O RTT é uma medida de rede; tecla até movimento oficial inclui também fila, tick, cálculo e confirmação.

**Jitter:** variação do atraso entre medições.

**TCP_NODELAY:** opção que desativa o agrupamento de pequenos envios pelo algoritmo de Nagle. Pode reduzir espera, mas não transforma a rede em tempo real garantido.

## 3. Partida e entrada

**Arena:** grade de células.

**Rastro:** ocupação permanente deixada por uma moto. Não desaparece ao eliminar o jogador.

**Estado:** dados necessários para representar o jogo naquele ponto: arena, motos, direções, condição e resultado.

**Estado confirmado:** estado obtido somente de decisões confirmadas.

**Estado candidato:** resultado calculado, ainda aguardando confirmação. Não deve sobrescrever a apresentação oficial.

**Motor determinístico:** função que produz o mesmo resultado a partir do mesmo estado e das mesmas entradas.

**Tick:** nome comum para a oportunidade periódica de avançar um ciclo. tick_ms é o intervalo; ciclo é o número do movimento.

**Fila de comandos:** sequência de mudanças solicitadas e ainda pendentes. O limite de dois inclui comandos enviados e não executados.

**command_seq:** sequência individual de comandos de um jogador. Não é index global do histórico.

**queue_version:** versão da fila individual. Muda ao limpar as pendências para impedir que mensagens antigas sejam aceitas depois.

**Ciclo de referência:** último ciclo oficial conhecido ao pressionar a tecla.

**Ciclo de execução:** ciclo reservado pelo host para aplicar o comando.

**Expiração:** descarte por idade lógica. Referência 42 e execução 45 dão idade 3, vencida. Três segundos parado não significam três ciclos.

**Contagem regressiva:** três segundos de preparação sem movimento.

**Janela de entrada:** últimos 500 ms dessa mesma contagem. Não aumenta sua duração.

**Espectador:** jogador cuja moto morreu e que continua acompanhando. Pode permanecer votante.

**Resultado global:** decisão compartilhada sobre vencedor ou empate. Cada aplicativo deriva vitória ou derrota de seu jogador.

## 4. Histórico e consenso

**Histórico ou log:** sequência ordenada de registros. Não é a lista de teclas nem o arquivo de mensagens de diagnóstico.

**Prefixo:** trecho inicial contínuo. Confirmar até 58 exige possuir 0 até 58.

**Sufixo:** trecho final do histórico. Um sufixo provisório pode ser substituído pelo líder válido.

**Lacuna:** posição ausente entre registros. Não confirmar sequência com lacunas.

**Registro provisório:** armazenado, mas ainda não conhecido como confirmado.

**Armazenar:** colocar o registro validado na memória da aplicação. O byte no buffer do sistema operacional ainda não atende a essa regra.

**ACK:** resposta de reconhecimento. Seu significado depende do tipo: APPEND_RESULT reconhece armazenamento; MATCH_OVER_ACK reconhece entrega do resultado.

**Confirmação ou commit:** decisão de que o registro e seu prefixo integram a sequência oficial pelas regras de quorum e época.

**commit_index:** maior posição que o processo sabe estar confirmada.

**last_applied:** maior posição já aplicada à sua arena. Pode estar atrás de commit_index enquanto o laço processa eventos, nunca à frente.

**Aplicar:** executar o efeito de um registro confirmado no estado. Não reaplicar o mesmo index.

**Maioria:** mais da metade de uma lista fixa. Em quatro, três; em três, dois; em dois, dois.

**Quorum:** conjunto suficiente para autorizar uma decisão. Nesta versão, maioria simples ou as duas maiorias da configuração conjunta.

**Votante:** processo integrante da configuração que pode conceder voto e contar na confirmação. Não depende de sua moto estar viva.

**Configuração de votantes:** lista que determina quais IDs contam. Não é a lista local de sockets conectados.

**Configuração conjunta:** fase em que decisões exigem maioria da lista antiga e maioria da nova. O mesmo ID pode contar nas duas.

**Versão da configuração:** número que identifica a composição e sua fase. Não é epoch nem cycle.

**Ranking de sucessão:** preferência compartilhada pela média de RTT. Não substitui votos e histórico elegível.

**Voto:** autorização eleitoral concedida a um candidato numa época. Não é voto sobre colisão ou justiça do resultado.

**Histórico mais atualizado:** comparação da época do último registro e, em empate, sua posição. Não significa simplesmente mais movimentos.

**Hash:** resumo calculado do conteúdo. Ajuda a verificar identidade de registros e encadeamento; sozinho não comprova maioria.

**Encadeamento:** cada registro referencia o hash anterior. Não permite inserir silenciosamente outro conteúdo no meio.

**Snapshot:** estado completo de uma posição confirmada, com âncora no histórico. Acelera a instalação da base durante migração; não cria autoridade por si só.

**Âncora:** posição, época e hash que ligam o snapshot ao histórico.

**Registro EPOCH_START:** entrada da época atual usada pelo novo líder para estabelecer e confirmar seu prefixo recuperado. Não move motos.

**Idempotência:** repetir uma mensagem não repete seu efeito. Um CYCLE já aplicado não anda a moto outra vez.

## 5. Falhas e tempo

**Heartbeat:** mensagem pequena de atividade enviada quando não há outro tráfego útil suficiente.

**Timeout:** prazo para iniciar uma ação de suspeita ou falha. Não prova que a máquina desligou.

**Relógio monotônico:** relógio para medir intervalos, que não é afetado por ajuste do horário civil.

**Partição de rede:** grupos de processos deixam de conseguir se comunicar. Não significa que todos do outro lado morreram.

**Split-brain:** participantes atuando como líderes incompatíveis. Épocas, votos e quorum impedem confirmação independente por grupos sem autorização suficiente.

**Segurança:** não confirmar decisões incompatíveis.

**Continuidade ou progresso:** conseguir avançar. Pode ser sacrificada ao perder quorum para preservar segurança.

**Transferência planejada:** host coopera para entregar liderança antes de sair.

**Migração por falha:** os participantes elegem e recuperam sem depender da cooperação do host anterior.

**Encerramento normal:** resultado confirmado entregue a todos os integrantes restantes, seguido de fechamento.

**Encerramento controlado:** o programa para sem ficar travado, informa a causa e não inventa resultado esportivo.

**Memória volátil:** dados desaparecem ao encerrar o processo. Por isso o retorno de processo reiniciado está fora desta versão.

**Log de diagnóstico:** texto sobre mensagens, tempos e transições para investigar problemas. Não é o histórico autoritativo replicado.

## 6. Como explicar em um minuto

“O jogador pede uma curva. O host decide em qual ciclo ela cabe, calcula todos os movimentos juntos e cria um registro. Os pares armazenam esse registro e respondem. Depois de obter o quorum, ele é confirmado e aplicado. Se o host falhar, a época muda, outro candidato precisa de votos e um histórico atualizado, e os registros são reconciliados. O estado confirmado é instalado antes da contagem de três segundos; o teclado abre apenas nos últimos 500 ms.”
