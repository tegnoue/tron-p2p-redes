# Glossário

## Cinco termos essenciais

| Termo | Significado |
|---|---|
| Comando | Pedido de curva de um jogador; pode não executar |
| Ciclo | Um passo em que as motos avançam uma célula |
| Registro | Decisão compartilhada: resultado de ciclo ou controle |
| Posição, index | Número global do registro, não sequência de teclas |
| Época | Tentativa de liderança; muda sem reiniciar o ciclo |

Exemplo: comando 17 de B, referência 42, época 2 → reservado para ciclo 43 → registro 58. Registro 59 pode mudar votantes; 60 pode guardar outro controle; 61 pode conter ciclo 44.

## Rede

| Termo | Significado |
|---|---|
| Processo | Programa com memória própria; mesma máquina ainda exige processos/portas distintos |
| Nó, peer | Participante que envia e recebe |
| Lobby | Registro e salas; não arbitra jogo iniciado |
| Host, líder | Jogador que propõe registros e calcula movimentos |
| Seguidor / candidato | Recebe e vota / tenta liderar |
| Socket | Objeto para ouvir, conectar e trocar bytes |
| Bind | Associação local a interface/porta; 0.0.0.0 não é endpoint anunciado |
| Endpoint | Endereço alcançável e porta, como 192.168.1.10:6001 |
| Malha completa | Uma conexão por par; quatro processos usam seis conexões |
| TCP | Bytes ordenados e retransmissão; sem limite de mensagem ou prazo garantido |
| UDP | Datagramas; alternativa não escolhida, exigiria tratamento de perdas/ordem |
| Framing | Separação das mensagens; aqui JSON terminado em LF |
| Buffer de recepção | Bytes ainda não consumidos como mensagens completas |
| Fila de envio | Isola espera de um socket lento |
| Handshake | Identificação/aceitação inicial; PEER_HELLO é da aplicação |
| RTT | Ida e volta de uma medição com relógio local |
| Latência | Atraso; tecla→movimento inclui mais que rede |
| Jitter | Variação do atraso |
| TCP_NODELAY | Desativa agrupamento de pequenos envios por Nagle; não garante tempo real |

## Partida e entrada

| Termo | Significado |
|---|---|
| Arena / rastro | Grade / ocupação permanente, inclusive após eliminação |
| Estado | Arena, motos, direções, condição e resultado |
| Estado confirmado / candidato | Derivado de decisões oficiais / calculado aguardando confirmação |
| Motor determinístico | Mesmo estado e entradas produzem mesmo resultado |
| Tick | Oportunidade periódica; tick_ms é intervalo, ciclo é contador |
| Fila de comandos | Pendências, incluindo enviadas e não executadas |
| command_seq | Sequência individual do jogador |
| queue_version | Versão que invalida pendências anteriores à limpeza |
| Ciclo de referência / execução | Conhecido ao pressionar / reservado para aplicar |
| Expiração | Idade lógica; referência 42 e execução 45 dão idade 3 |
| Contagem | Três segundos sem mover motos |
| Janela de entrada | Últimos 500 ms da contagem; sem tempo extra |
| Espectador | Moto eliminada; processo pode continuar votando |
| Resultado global | Vencedor/empate comum; aplicativo deriva a situação individual |

## Histórico e consenso

| Termo | Significado |
|---|---|
| Histórico, log | Sequência de registros, não lista de teclas nem diagnóstico |
| Prefixo / sufixo | Trecho inicial contínuo / trecho final |
| Lacuna | Posição ausente; impede confirmar o prefixo |
| Registro provisório | Armazenado sem confirmação conhecida |
| Armazenar | Guardar validado na aplicação; bytes no sistema operacional não bastam |
| ACK | Reconhecimento cujo significado depende da mensagem |
| Commit, confirmação | Registro e prefixo tornam-se oficiais pelas regras de quorum/época |
| commit_index | Maior posição conhecida como confirmada |
| last_applied | Maior posição aplicada à arena; nunca acima de commit_index |
| Aplicar | Executar o efeito uma vez no estado |
| Maioria | Mais da metade: 3/4, 2/3, 2/2 |
| Quorum | Conjunto suficiente: maioria simples ou as duas maiorias conjuntas |
| Votante | Processo da configuração; não depende de moto viva |
| Configuração dos votantes | Lista compartilhada, não sockets locais disponíveis |
| Configuração conjunta | Exige maiorias antiga e nova; um ID pode contar nas duas |
| Versão da configuração | Identifica composição/fase; não é época ou ciclo |
| Ranking | Preferência por RTT; não autoriza liderança |
| Voto | Autoriza candidato numa época, não julga colisão |
| Histórico atualizado | Comparação (época do último registro, posição), permitindo igualdade |
| Hash | Resumo do conteúdo; identifica, mas não comprova maioria |
| Encadeamento | Cada registro referencia o hash anterior |
| Snapshot | Estado completo confirmado ligado ao histórico |
| Âncora | Posição, época e hash do snapshot |
| EPOCH_START | Registro atual que estabelece liderança e permite confirmar prefixo antigo |
| Idempotência | Repetir mensagem não repete efeito |

## Falhas e tempo

| Termo | Significado |
|---|---|
| Heartbeat | Atividade pequena na ausência de tráfego útil |
| Timeout | Prazo de suspeita/ação, não prova de morte |
| Relógio monotônico | Mede intervalos sem depender do horário civil |
| Partição | Grupos deixam de se comunicar, mesmo com processos vivos |
| Split-brain | Lideranças incompatíveis; votos/épocas/quorum impedem confirmação indevida |
| Segurança / continuidade, progresso | Não confirmar conflito / conseguir avançar |
| Transferência planejada | Host coopera antes de sair |
| Migração por falha | Eleição/recuperação sem sua cooperação |
| Encerramento normal | Resultado entregue aos integrantes e fechamento |
| Encerramento controlado | Para sem travar e sem inventar resultado |
| Memória volátil | Perdida ao encerrar; não há reentrada nesta versão |
| Log de diagnóstico | Eventos para investigação; não é histórico autoritativo |

## Explicando em um minuto

O jogador pede uma curva. O host reserva um ciclo, calcula os movimentos juntos e cria um registro. Os pares armazenam e respondem; com quorum, o registro é confirmado e aplicado. Na falha do host, outro candidato precisa de votos e histórico atualizado. A base recuperada é sincronizada antes da contagem de três segundos, cujo teclado abre só nos últimos 500 ms.
