# Arquitetura do sistema — Tron P2P

## 1. Objetivo e situação do documento

Este documento consolida as decisões de arquitetura de um jogo Tron multijogador para a disciplina de Redes.

A solução utiliza lobby centralizado para descoberta e comunicação direta entre os jogadores durante a partida, com um participante atuando como host autoritário.

Este documento é uma base para implementação. Os formatos iniciais do lobby estão em protocolo.md. As mensagens P2P e os detalhes dos algoritmos distribuídos ainda precisam ser formalizados e testados.

As garantias descritas são objetivos da arquitetura; não representam uma implementação já validada.

## 2. Requisitos e decisões principais

| Tema | Decisão |
|---|---|
| Jogo | Tron em grade |
| Participantes iniciais | Mínimo de três e máximo de quatro |
| Execução | Um processo por jogador e processo independente para o lobby |
| Rede | Máquinas diferentes da mesma rede |
| Descoberta | Lobby centralizado |
| Partida | Comunicação direta entre pares |
| Topologia | Malha completa |
| Autoridade | Um jogador atua como host |
| Transporte | TCP com API de sockets |
| Serialização | JSON em UTF-8, uma mensagem por linha |
| Estado e histórico | Mantidos em memória |
| Processo reiniciado | Não retorna à mesma partida |
| Interface | Terminal |
| Configuração | Endereços, portas e parâmetros configuráveis |

A queda do lobby não pode interromper partidas iniciadas.

Bibliotecas auxiliares de terminal, JSON, configuração, hashes e logs podem ser utilizadas. A comunicação deve ser implementada diretamente com sockets.

O modelo discutido trata falhas e desconexões. Não foi definido um protocolo contra participantes maliciosos que forjem registros ou confirmações.

## 3. Organização do projeto

### core/

Configuração, tipos compartilhados, serialização, enquadramento das mensagens, validação estrutural e erros do protocolo.

### lobby/

Registro de jogadores, criação e listagem de salas, entrada e saída, distribuição de endpoints, consolidação dos RTTs e preparação inicial.

Não executa ciclos nem arbitra colisões durante a partida.

### game/

Motor isolado da rede.

Recebe o estado e os comandos de um ciclo, calcula movimentos e colisões e devolve o resultado. Não abre sockets nem realiza eleições.

### node/

Aplicativo do jogador: teclado, interface, conexões, filas, estados, replicação, liderança, recuperação e encerramento.

O mesmo aplicativo pode atuar como seguidor, candidato ou host.

## 4. Comunicação entre pares

Cada jogador abre sua porta de escuta antes de anunciar seu endpoint.

Para cada par, o menor ID inicia a conexão com o maior ID. Uma conexão TCP é bidirecional.

- Três participantes: três conexões.
- Quatro participantes: seis conexões.

Todos aceitam conexões na preparação, independentemente de quem será o host.

A porta usada para conectar ao lobby não é a porta de escuta P2P. Endereço de bind e endereço anunciado aos pares podem ser configurações diferentes.

## 5. Ranking inicial

Após estabelecer a malha, os jogadores medem o RTT até os demais usando mensagens de aplicação e relógio monotônico local.

Cada jogador envia suas medições ao lobby. O lobby consolida um ranking pela média de RTT de cada participante até os outros, com desempate por ID.

A quantidade de amostras é configurável e ainda precisa de um valor inicial.

O ranking:

- É compartilhado e consolidado antes da partida.
- Orienta a preferência de candidatura.
- Não autoriza assumir a liderança sozinho.
- Não substitui a verificação do histórico e a obtenção de maioria.

O criador da sala pode ser diferente do host da partida.

## 6. Preparação

1. O jogador abre sua porta P2P e se registra no lobby.
2. Cria ou entra em uma sala.
3. O criador solicita início com três ou quatro participantes.
4. A sala entra em PREPARANDO e congela a lista daquela tentativa.
5. O lobby distribui participantes e endpoints.
6. Os jogadores estabelecem a malha e medem RTT.
7. O lobby distribui ranking e configuração inicial.
8. Cada aplicativo envia prontidão automática após concluir sua preparação.
9. O host inicial aguarda todos sobre a mesma configuração.
10. Ocorrem a contagem e a janela de entrada antes do primeiro movimento.

A configuração contém participantes, arena, posições e direções iniciais, taxa de ciclos, parâmetros compartilhados e votantes iniciais.

São utilizados pontos de partida predefinidos. O lobby sorteia sua atribuição aos jogadores.

Cada tentativa possui identificação própria. Mensagens de tentativas antigas são ignoradas.

### Falha antes do início

Se alguém cair antes do primeiro ciclo:

- A tentativa e qualquer contagem são canceladas.
- A sala permanece em PREPARANDO, mesmo com participantes suficientes.
- A configuração é atualizada.
- O criador solicita uma nova tentativa; não há início automático.

Para receber novos jogadores, o criador cancela a preparação e reabre a sala em AGUARDANDO.

Se o criador sair, assume o integrante presente que entrou há mais tempo. Uma sala vazia é removida.

Se o lobby cair durante a preparação, a tentativa pode ser cancelada.

## 7. Entrada de comandos

### Validação local

A tecla é validada imediatamente em relação à última direção aceita pendente. Sem pendências, usa-se a direção oficial conhecida.

- Direção igual: ignorar como redundante.
- Direção oposta: rejeitar.
- Direção perpendicular: aceitar se houver espaço.
- Fila cheia: ignorar a nova tecla sem substituir anteriores.

Uma tecla rejeitada não altera a referência de validação. A repetição automática do teclado segue as mesmas regras.

### Capacidade

Limite inicial: dois comandos pendentes por jogador.

Esse total inclui comandos em trânsito e aceitos pelo host, mas ainda não executados.

O cliente mantém uma estrutura com os comandos pendentes e utiliza seu tamanho como contador.

A confirmação de aceitação não libera espaço. A execução oficialmente conhecida, rejeição ou descarte remove a pendência.

### Validação no host

O host verifica:

- Identidade associada à conexão.
- Partida e época de liderança.
- Versão da fila e sequência do comando.
- Direção, capacidade e validade.
- Estado da partida e condição da moto.

O host também valida a direção; a validação local não substitui a autoridade.

### Ciclo de referência e execução

O cliente informa o ciclo oficial conhecido quando a tecla foi aceita: o ciclo de referência.

O host reserva o primeiro ciclo ainda aberto e sem comando daquele jogador, respeitando ordem e validade.

A confirmação informa o ciclo de execução reservado.

Cada jogador executa no máximo uma mudança de direção por ciclo. Sem comando aplicável, mantém a direção.

O fechamento das entradas é comum a todos. Comandos processados depois dele só podem entrar em ciclos seguintes.

### Validade

O comando vence quando:

    ciclo_de_execucao - ciclo_de_referencia >= 3

Exemplo: referência 42 permite execução nos ciclos 43 e 44. No 45, venceu.

Verificar validade na reserva e antes da execução.

O prazo não é uma espera obrigatória. O comando deve executar no primeiro ciclo permitido.

### Limpeza

Uma rejeição ou expiração que comprometa a sequência limpa as pendências daquele jogador.

A limpeza:

- Não reverte movimentos oficiais.
- Atualiza a versão da fila.
- Invalida mensagens antigas ainda em trânsito.
- Exige reconciliar pendências e direção oficial antes de retomar os envios.

Moto eliminada não aceita novos movimentos.

A migração limpa as pendências de todos. Registros de ciclos recuperados não são comandos pendentes e podem precisar ser preservados.

### Host

O host utiliza o mesmo caminho de validação, reserva, capacidade e consumo. Sua tecla não modifica diretamente a simulação.

Permanece a vantagem natural de não atravessar a rede até a autoridade.

## 8. Motor do jogo

Em cada ciclo:

1. Selecionar até um comando por moto viva.
2. Determinar todas as direções e destinos sem alterar a arena.
3. Resolver conjuntamente as colisões.
4. Produzir movimentos, rastros e eliminações.
5. Avaliar o resultado.

Convenções:

- As células iniciais das motos já estão ocupadas.
- Rastros anteriores permanecem.
- Entrar em rastro ou sair da arena elimina a moto.
- Motos com o mesmo destino são todas eliminadas.
- Trocar de posições elimina ambas, pois os destinos já estavam ocupados.
- Um destino alcançado dentro da arena fica ocupado, inclusive numa colisão entre motos em célula antes vazia.
- Não se cria rastro fora da arena.
- Uma moto eliminada antes do movimento daquele ciclo não avança.
- Um sobrevivente vence; zero significa empate; dois ou mais continuam.

A ordem de processamento dos jogadores não pode afetar o resultado.

## 9. Histórico compartilhado

O histórico de teclas solicitadas é diferente do registro dos ciclos executados.

O registro compartilhado permite recuperar os comandos aplicados e seus efeitos: movimentos, rastros, eliminações e resultado.

Cada processo mantém em memória:

- Estado inicial e estado atual.
- Registros ordenados.
- Última posição armazenada.
- Última posição confirmada conhecida.
- Último registro aplicado.
- Época de liderança.
- Configuração de votantes.

Posição no registro e ciclo do jogo são diferentes. Registros de liderança e configuração não movimentam motos.

Confirmar até a posição N significa ter armazenado toda a sequência até N, sem lacunas. Registros ausentes são solicitados.

## 10. Confirmação dos ciclos

Fluxo normal:

1. O host calcula e registra o ciclo.
2. Distribui o registro.
3. Os participantes armazenam e respondem imediatamente.
4. O host obtém a maioria aplicável, contando sua própria cópia.
5. Confirma a sequência e anuncia o avanço.
6. Todos aplicam os registros confirmados em ordem, uma única vez.

A confirmação significa armazenamento, não uma votação sobre a justiça da colisão.

A apresentação inicial, inclusive no host, acompanha os ciclos confirmados.

Participantes podem exibir temporariamente ciclos diferentes por atraso, mas não podem confirmar resultados conflitantes.

A proposta inicial admite um ciclo de jogo aguardando confirmação por vez. A cadência normal é fixa; se não houver progresso suficiente, a simulação pausa para sincronização, sem inventar ciclos ou acelerar depois para compensar.

Os prazos exatos dessa pausa precisam ser formalizados.

## 11. Atividade e detecção de falhas

Ausência de teclas não significa desconexão.

Após três intervalos de ciclo sem enviar comandos, o jogador envia uma mensagem pequena de atividade, repetindo enquanto necessário.

Comandos e outras mensagens válidas também demonstram atividade.

O host já demonstra atividade pelas atualizações normais; durante pausas, envia atividade quando necessário.

Os prazos:

- Usam relógio monotônico.
- Continuam funcionando com a simulação pausada.
- Distinguem intervalo de atividade de timeout de suspeita.
- Devem tolerar mais de uma oportunidade de verificação.

TCP ajuda com fechamento e erros, mas uma conexão aparentemente aberta não prova que o processo está disponível.

Timeout gera suspeita; sozinho, não autoriza liderança nem remoção de votantes.

## 12. Eleição e recuperação

### Eleição

- Cada tentativa usa uma época superior à conhecida.
- Cada votante concede no máximo um voto por época.
- O ranking orienta a preferência.
- O candidato precisa de histórico elegível e maioria.
- O preferencial se atualiza ou outro candidato assume.
- A comparação considera épocas e posições dos registros.
- Reconhecida uma liderança válida superior, a autoridade anterior não é aceita.

Não basta selecionar o maior número de ciclo.

### Recuperação

Os participantes compartilham metadados e transferem registros ausentes.

A recuperação deve:

1. Preservar o prefixo confirmado.
2. Estabelecer uma sequência única compatível com a eleição.
3. Resolver registros pendentes sem substituir trechos confirmados.
4. Confirmar a sequência sob a nova liderança.
5. Sincronizar o estado de retomada.

Um ciclo confirmado pode ser desconhecido por alguns se o host caiu durante seu anúncio.

Algo existente somente na memória do host que caiu não é recuperável e não poderia ter sido confirmado por maioria.

### Registros pendentes

A proposta é preservar a sequência pendente compatível do líder eleito e confirmá-la antes da retomada.

O líder acrescenta um registro de estabelecimento da liderança na época atual, depois dos registros recuperados. A confirmação desse registro pelas regras vigentes confirma o prefixo anterior.

Esse registro não consome um ciclo. As épocas dos registros antigos não são reescritas.

Esse procedimento depende de regras completas de eleição, continuidade e confirmação. Não deve ser substituído por seleção arbitrária de histórico ou votação isolada de hashes.

### Retomada

1. Eleger.
2. Recuperar e confirmar.
3. Atualizar a arena e direções durante a pausa.
4. Registrar a eliminação da moto que falhou, quando aplicável.
5. Sincronizar os participantes restantes.
6. Contagem de três segundos, com entradas bloqueadas.
7. Janela de entrada de três segundos, com motos paradas.
8. Retomar no próximo ciclo.

Essas duas fases temporizadas, mantidas separadas, somam seis segundos. Unificá-las exige alterar explicitamente a regra de entrada durante a contagem.

Movimentos recuperados não são executados novamente. As filas antigas são descartadas.

Sem condições de liderança e confirmação seguras, aplica-se encerramento controlado, sem inventar vencedor ou empate.

## 13. Votantes e reconfiguração

Motos vivas e processos votantes são conjuntos diferentes.

Um eliminado pode continuar assistindo e votando. Um host eliminado pode continuar coordenando.

A lista de votantes integra o registro compartilhado.

Mudanças usam configuração conjunta:

- Durante a transição, exige-se maioria antiga e nova.
- Depois, confirma-se a configuração definitiva.
- Uma alteração por vez.
- Ninguém recalcula a composição apenas por sua percepção local.

Maiorias usuais:

- Três de quatro.
- Dois de três.
- Dois de dois.

Um processo restante não pode se declarar maioria de uma configuração de dois.

A ativação das configurações e suas mensagens ainda precisam ser formalizadas.

## 14. Saída voluntária

### Participante comum

1. Solicita saída e mantém a conexão.
2. Sua moto, se viva, é eliminada oficialmente.
3. A configuração é alterada com segurança.
4. Recebe autorização para desconectar.
5. Escolhe voltar ao lobby ou sair.

### Host

1. Conclui a confirmação do ciclo e pausa.
2. Limpa comandos pendentes.
3. Atualiza o sucessor.
4. O sucessor estabelece liderança com maioria.
5. A nova liderança confirma a eliminação da moto anterior, se necessária, e sua remoção dos votantes.
6. O antigo host recebe autorização de saída.
7. Os demais sincronizam e retomam.

A comunicação continua durante a pausa. Falha durante a transferência aciona recuperação.

## 15. Encerramento

1. O ciclo final inclui o resultado global e é confirmado.
2. O resultado é anunciado a todos.
3. Cada aplicativo apresenta vitória, derrota ou empate conforme seu jogador.
4. Entradas são bloqueadas e pendências limpas.
5. Todos ainda integrantes da sessão confirmam a entrega.
6. O host conclui o encerramento normal.
7. O usuário escolhe voltar ao lobby ou sair.

Quem morreu antes não passa a empatar com os últimos sobreviventes.

Timeout não equivale a confirmação. Falhas exigem tratamento e remoção confirmada quando possível.

Os registros permanecem disponíveis durante o encerramento. Se o host cair durante a entrega, a recuperação preserva ou conclui o resultado.

Quem não conseguir obter o resultado informa sua indisponibilidade, sem inventá-lo.

O lobby indisponível não altera o resultado nem impede fechar a partida. O aplicativo permite tentar novamente ou sair.

## 16. Estados

### Aplicativo

| Estado | Responsabilidade |
|---|---|
| DESCONECTADO | Sem sessão |
| CONECTANDO_LOBBY | Conexão e registro |
| NO_LOBBY | Listar, criar e entrar |
| NA_SALA | Aguardar o criador |
| PREPARANDO | Malha, RTT, configuração e prontidão |
| CONTAGEM | Entradas bloqueadas |
| JANELA_ENTRADA | Comandos permitidos; motos paradas |
| EM_PARTIDA | Ciclos confirmados |
| SINCRONIZANDO | Eleição, recuperação, transferência ou reconfiguração |
| ENCERRANDO | Resultado, entrega e fechamento |
| RESULTADO | Voltar ao lobby ou sair |

Informações independentes:

- Liderança: seguidor, candidato ou líder.
- Moto: viva ou eliminada.
- Votação: integrante ou não da configuração.
- Sala: criador ou participante comum.

### Sala

AGUARDANDO, PREPARANDO, EM_PARTIDA e FINALIZADA.

Somente AGUARDANDO aceita entradas.

## 17. Redução de latência

- Responder ao armazenamento imediatamente.
- Confirmar assim que houver maioria.
- Não bloquear o processamento por socket lento.
- Enviar o resultado uma vez e usar anúncio curto de confirmação.
- Configurar TCP_NODELAY nas conexões da partida.
- Montar a mensagem inteira antes do envio.
- Executar no primeiro ciclo permitido.

Medir:

- No cliente: tecla aceita até movimento oficial recebido.
- No host: recepção, cálculo e obtenção de maioria.

Taxa de ciclos, capacidade e validade são configuráveis e serão ajustadas nos testes.

## 18. Implementação e validação

Ordem sugerida:

1. Lobby e salas.
2. Motor determinístico.
3. Partida com host fixo e falha controlada.
4. Replicação e confirmação.
5. Transferência planejada.
6. Eleição e recuperação.
7. Reconfiguração e encerramento completo.

Testar:

- Três e quatro processos, inclusive em máquinas distintas.
- Colisões simultâneas e empate.
- Expiração, limpeza e mensagens antigas.
- Confirmação anunciada parcialmente.
- Falha antes e depois de obter maioria.
- Queda de jogador, host e candidato.
- Saídas sucessivas e configuração com dois votantes.
- Queda do lobby antes e depois do início.
- Entrega parcial do resultado.
- Atrasos, silêncio de rede e sockets lentos.

## 19. Pendências

Antes de considerar a migração concluída e o protocolo interoperável:

- Definir JSONs P2P e matriz completa de transições.
- Formalizar eleição, comparação de registros e épocas.
- Formalizar correspondência e substituição de sufixos não confirmados.
- Formalizar confirmação na nova liderança e snapshots.
- Definir ativação das configurações conjunta e definitiva.
- Especificar reconciliação após limpeza individual de fila.
- Definir timeouts, limites de mensagem e filas de rede.
- Definir encerramento controlado sem maioria.
- Escolher valores de arena, spawns, ciclos e amostras de RTT.

Essas pendências não devem ser preenchidas por decisões locais incompatíveis entre implementações.