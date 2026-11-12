# Arquitetura do Tron P2P

## 1. Funcionamento geral

O Tron P2P é um jogo em grade para três ou quatro jogadores, cada um em um processo separado. A cada ciclo, as motos avançam uma célula. As células percorridas ficam ocupadas pelo rastro, inclusive depois da eliminação. Vence a última moto sobrevivente; se as últimas forem eliminadas no mesmo ciclo, há empate.

O lobby registra os jogadores e organiza as salas. Depois da preparação, a comunicação do jogo ocorre diretamente entre os processos. Um jogador assume o papel de host e calcula os ciclos. Os demais armazenam os resultados e confirmam o recebimento pelo protocolo.

Essa organização permite desligar o lobby sem interromper uma partida iniciada. Também permite trocar o host, desde que os participantes disponíveis consigam eleger outro e recuperar o estado.

## 2. Responsabilidades dos componentes

O módulo core deve reunir configuração, tipos, serialização JSON, hashes e erros. O lobby deve cuidar das sessões, salas e preparação. Ele não deve calcular colisões nem fornecer o estado a cada ciclo.

O motor game deve receber um estado e as entradas de um ciclo e devolver o resultado. A mesma entrada sobre o mesmo estado deve produzir o mesmo resultado. Essa propriedade, chamada determinismo, permite testar as regras sem rede e conferir os registros recebidos.

O aplicativo node deve controlar conexões, teclado, interface e sessão. Sua camada de rede entrega mensagens; a sessão decide seus efeitos; a interface apresenta uma cópia do estado. Um único laço deve alterar arena, filas, votos e histórico, evitando que threads concorrentes produzam atualizações incompatíveis.

A divisão em arquivos pode variar. As responsabilidades não devem se misturar: uma tecla não altera diretamente a arena, e uma thread de socket não decide uma colisão.

## 3. Comunicação

Os jogadores devem formar uma malha completa: cada par mantém uma conexão TCP bidirecional. Três jogadores usam três conexões; quatro usam seis. O menor ID inicia a conexão de cada par para evitar duplicatas.

Todos devem abrir a porta P2P antes de anunciar seu endereço ao lobby. A porta de escuta é diferente da porta temporária usada para conectar ao servidor. O endereço anunciado precisa ser alcançável pelas outras máquinas. O endereço 0.0.0.0 permite ouvir nas interfaces locais, mas não deve ser anunciado como destino.

TCP entrega bytes em ordem, não mensagens completas nem prazos. Cada objeto JSON deve terminar com LF. O receptor deve guardar bytes até completar uma linha. O envio deve utilizar uma fila por conexão, para que um jogador lento não bloqueie os demais. TCP_NODELAY reduz esperas de agrupamento de mensagens pequenas.

A comunicação deve usar diretamente sockets. Bibliotecas auxiliares de terminal, JSON, configuração e logs são permitidas; frameworks de multiplayer não devem substituir a implementação do protocolo.

## 4. Preparação da partida

O criador solicita o início quando houver três ou quatro jogadores. O lobby congela essa lista e identifica a tentativa. A entrada de outro jogador exige cancelar a preparação e reabrir a sala.

Os pares estabelecem as conexões e medem RTT, o tempo entre uma mensagem de teste e sua resposta. O lobby recebe as amostras e produz um ranking único pela média de RTT de cada jogador até os demais, com desempate por ID. Medir somente o caminho até o lobby não avaliaria a rede utilizada na partida.

A configuração compartilhada deve incluir arena, posições e direções iniciais, ranking, participantes e parâmetros. O lobby sorteia a atribuição dos jogadores a pontos de partida predefinidos. Cada aplicativo envia READY automaticamente depois de concluir suas conexões e preparar a mesma configuração. O host inicial aguarda todos antes de conduzir o início.

Criador e host são papéis diferentes. O primeiro controla a sala; o segundo é escolhido pelo ranking e pelas regras de liderança.

Se ocorrer uma falha antes do início, a tentativa é cancelada e a sala permanece PREPARANDO, mesmo com três participantes restantes. O criador solicita outra tentativa ou reabre entradas. Se sair, assume o integrante presente que entrou há mais tempo. Sala vazia é removida.

Cada tentativa tem IDs próprios. Um relato atrasado não pode cancelar uma partida já iniciada: o registro START define o ponto lógico utilizado pelo protocolo. A indisponibilidade do lobby pode cancelar uma preparação, mas não uma partida cujo início já foi confirmado.

## 5. Contagem e comandos

A contagem deve durar três segundos, com as motos paradas. Nos primeiros 2,5 segundos, as teclas são ignoradas. Nos últimos 500 ms, o jogador pode preparar até dois comandos. Não existe uma segunda espera depois da contagem.

As filas antigas são limpas antes desse período. As novas teclas são preservadas para os primeiros ciclos. O host controla o tempo por relógio monotônico e anuncia as fases; os clientes não devem presumir relógios sincronizados. O atraso da rede pode reduzir a janela observada por um cliente.

### Validação e fila

A validação local deve ocorrer imediatamente. A referência é a última direção aceita pendente ou, sem pendências, a direção oficial da moto. Direção repetida ou oposta é ignorada. Uma tecla rejeitada não muda a referência da próxima.

Se a moto segue à direita e a fila contém cima, uma nova curva à esquerda é válida. As duas curvas não acontecem no mesmo instante: cada uma ocupa um ciclo.

O limite de dois pendentes inclui comandos enviados e ainda não executados. Receber MOVE_ACCEPTED não libera espaço. A estrutura local só é reduzida quando a execução oficial é conhecida ou quando uma rejeição/limpeza encerra a pendência. Com fila cheia, a nova tecla é ignorada sem substituir anteriores.

### Reserva e validade

O comando informa o ciclo oficial conhecido ao pressionar a tecla. O host reserva o primeiro ciclo ainda aberto, respeitando a fila. Cada jogador pode executar uma curva por ciclo; sem comando aplicável, mantém a direção.

O comando vence quando execução menos referência for maior ou igual a três. Uma referência 42 permite execução em 43 ou 44; em 45, venceu. Essa regra limita a idade, não obriga espera. A validade deve ser conferida na reserva e na execução.

Se uma rejeição comprometer a sequência, cliente e host devem limpar as pendências daquele jogador. Uma nova versão de fila invalida comandos antigos em trânsito. O host aguarda a confirmação da limpeza antes de aceitar a nova sequência.

Na migração, todas as pendências são descartadas. Isso não apaga movimentos que já façam parte de um registro recuperável. O host deve passar pelo mesmo caminho de entrada dos demais; sua vantagem natural é apenas não atravessar a rede para chegar à autoridade.

## 6. Cálculo dos movimentos

O motor deve selecionar até um comando por moto viva e calcular todos os destinos antes de alterar a arena. Depois resolve colisões, aplica rastros e eliminações e avalia o resultado. A ordem dos IDs não pode favorecer ninguém.

As posições iniciais já são ocupadas. Entrar em rastro ou sair da arena elimina a moto. Duas motos no mesmo destino são eliminadas; trocar de posição também elimina ambas, pois as células anteriores já estavam ocupadas.

Um destino interno alcançado deve ficar ocupado, mesmo numa colisão entre motos em célula antes vazia. Não deve existir célula fora da arena. Na colisão com parede, o estado guarda a última posição válida e o evento informa o destino tentado.

A saída de um jogador é uma decisão de controle entre movimentos. Ela elimina sua moto sem deslocar as outras e pode terminar a partida. O rastro permanece.

## 7. Histórico e confirmação

Um comando é uma solicitação individual. Um registro é uma decisão compartilhada: resultado de ciclo, mudança de liderança ou alteração dos votantes. O histórico é a sequência desses registros.

A posição index numera o histórico; cycle numera os movimentos; epoch identifica a tentativa de liderança. Por exemplo, o registro 58 pode conter o ciclo 43 e o 59 uma mudança dos votantes, sem novo movimento.

Cada processo deve manter a arena confirmada, o histórico provisório e confirmado, a última posição confirmada, a última aplicada, a época, o voto e os votantes. O host também acompanha até onde cada par armazenou. Um cálculo provisório não deve sobrescrever a apresentação oficial.

O host registra e distribui o resultado. O receptor valida a continuidade, armazena na aplicação e responde imediatamente. Depois de obter o quorum, o host anuncia a confirmação. Todos aplicam o prefixo confirmado em ordem, uma única vez. Confirmar N exige possuir todos os registros até N.

Armazenar não é confirmar. Confirmar não é aplicar. O ACK também não é uma votação sobre a justiça da colisão.

Somente um registro da época atual avança diretamente a confirmação; seu prefixo é confirmado junto. Por isso o novo líder registra EPOCH_START depois de reconciliar o histórico. A implementação admite no máximo um ciclo de movimento aguardando confirmação. Se a comunicação atrasar, a simulação pausa; não deve pular células nem acelerar para compensar.

## 8. Falha, eleição e recuperação

Ausência de teclas não indica desconexão. Após três intervalos de ciclo sem comandos enviados, o processo transmite atividade. Outras mensagens válidas também contam. O mecanismo deve funcionar nas pausas e usar relógio monotônico. Timeout inicia suspeita, não prova que a máquina desligou.

O ranking define uma fila repetível de candidatos. A época E corresponde à posição (E-1) módulo tamanho do ranking, pulando IDs removidos. Cada votante concede um voto por época. O candidato deve reunir maioria e apresentar um histórico pelo menos tão atualizado quanto o do votante, comparando época do último registro e depois posição. Igualdade permite voto.

O eleito deve completar registros ausentes e substituir somente sufixos provisórios incompatíveis. Um trecho confirmado não pode ser apagado. Se houver conflito confirmado, o sistema verifica o contexto e, persistindo o problema, encerra por inconsistência.

Uma confirmação pode ter chegado somente a B, enquanto C possui o mesmo registro sem conhecer o anúncio. Isso não torna o registro inválido. A recuperação deve preservar decisões já confirmadas. Um cálculo que permaneceu somente na memória do host perdido não pode ser recuperado.

Após confirmar a sequência, o líder produz um snapshot: a arena completa, motos, resultado e configuração, ligados a uma posição confirmada do histórico. Os participantes conferem essa âncora e confirmam a mesma base. Só então ocorre a contagem de retomada. Não se reaplica uma curva recuperada.

## 9. Votantes e saída segura

Votante é um processo autorizado a participar das confirmações e eleições. Sua moto não precisa estar viva. Um eliminado pode assistir e votar; um host eliminado pode continuar coordenando.

A lista de votantes deve mudar por registros. Primeiro é confirmada uma configuração conjunta, com listas antiga e nova. Durante a transição, decisões e eleições exigem maioria em ambas. A configuração definitiva também exige as duas maiorias; somente depois de confirmada vale a lista nova. Uma alteração por vez evita transições sobrepostas.

A restrição conjunta passa a ser usada ao armazenar sua entrada, mesmo antes de conhecer a confirmação. É uma medida conservadora para não relaxar quorum por informação atrasada. Versões identificam essas configurações.

Na saída voluntária, o participante permanece conectado até a eliminação de sua moto, a reconfiguração e LEAVE_APPROVED. O host deve confirmar sua pendência, pausar, atualizar o sucessor e transferir a liderança. Se falhar durante o processo, vale a recuperação normal; o antigo host não reassume sozinho.

## 10. Encerramento e limites

O resultado global deve estar em registro confirmado. Todos recebem o mesmo vencedor ou empate; cada aplicativo apresenta a situação individual. Quem foi eliminado antes não passa a empatar com os últimos sobreviventes.

O encerramento normal exige confirmação de entrega de todos ainda integrantes da sessão antes de SESSION_CLOSE. Timeout não conta como ACK. Quem não responde exige tratamento de falha e, quando possível, remoção confirmada. Os registros devem continuar disponíveis durante o fechamento.

Depois de um resultado terminal, controles de liderança e configuração não mudam o placar. Quem ainda não conhece o resultado tenta recuperá-lo; se não conseguir, informa indisponibilidade, sem inventar vitória ou empate. O usuário pode escolher lobby ou saída. A indisponibilidade do lobby não reabre a partida.

Maioria de quatro exige três; de três exige dois; de dois exige ambos. Com dois votantes e uma falha, não há autorização para continuar. O encerramento deve ser controlado. Essa limitação deve ser avaliada frente ao requisito de continuidade do trabalho; não existe garantia sob qualquer sequência de falhas.

O protocolo não prevê fraude nem retorno de processo reiniciado à mesma sessão. Estado e votos são voláteis; logs em disco servem para diagnóstico. Uma documentação detalhada também não substitui a validação com atrasos, quedas e máquinas distintas.

## 11. Estados da sessão

| Estado | Comportamento |
|---|---|
| DESCONECTADO | Sem sessão; pode conectar ou sair |
| CONECTANDO_LOBBY | Realiza conexão e registro |
| NO_LOBBY | Lista, cria ou entra em salas |
| NA_SALA | Aguarda o pedido do criador |
| PREPARANDO | Monta rede, mede RTT e prepara configuração |
| CONTAGEM | Primeiros 2,5 s, sem entrada |
| JANELA_ENTRADA | Últimos 500 ms, aceita comandos |
| EM_PARTIDA | Acompanha movimentos confirmados |
| SINCRONIZANDO | Eleição, recuperação, transferência ou reconfiguração |
| ENCERRANDO | Entrega resultado e fecha a sessão |
| RESULTADO | Mantém o resultado e oferece lobby ou saída |

A rede continua sendo processada nas pausas. Liderança, condição da moto, votação e controle da sala são informações independentes desse estado.

Os documentos de protocolo, implementação e glossário complementam esta arquitetura com campos, rotinas e vocabulário. Os conceitos necessários ao funcionamento geral estão definidos nesta página.
