# Decisões do projeto

Registro das escolhas feitas na discussão. **Confirmada**: aceita pelo grupo. **Base inicial**: adotada para implementar e ajustar. Detalhes preenchidos pela especificação não são atribuídos ao grupo.

Requisitos do professor — lobby, comunicação direta, três/quatro jogadores iniciais, processos separados, sockets, configuração e resultado consistente — não são escolhas livres.

## 1. Rede e autoridade — confirmadas

| ID | Alternativas | Escolha | Motivo/efeito |
|---|---|---|---|
| D01 | TCP / UDP com confiabilidade na aplicação | TCP | Menor escopo; ainda exige framing, fila e prazo |
| D02 | Só host / malha completa | Malha, uma conexão por par | Sucessores já se comunicam; seis conexões com quatro |
| D03 | Host fixo / lockstep / migração | Host autoritário com recuperação | Arbitragem simples com possibilidade de continuidade |
| D04 | Raft completo / protocolo específico | Protocolo específico | Escopo acadêmico; usa regras conhecidas sem alegar equivalência automática a Raft |
| D05 | Ping ao lobby / RTT dos pares / IDs | Média de RTT entre pares | Mede a rede real; ranking único não substitui votos |

Convenção aceita: porta P2P aberta antes de registrar; menor ID inicia a conexão.

## 2. Comandos — confirmadas

| ID | Alternativas | Escolha | Motivo/efeito |
|---|---|---|---|
| D06 | Esperar host / validar na tecla | Validação local imediata | Comparar última direção aceita; host revalida |
| D07 | Fila longa / um / dois | Dois pendentes totais | Antecipação sem acúmulo de comandos antigos |
| D08 | Contador separado / tamanho | Tamanho da estrutura | Evita divergência; aceitação não libera espaço |
| D09 | Cliente fixa ciclo / host reserva | Referência do cliente e reserva do host | Uma curva por jogador/ciclo, ordem explícita |
| D10 | Referência menor sempre inválida / validade 2 / 3 | Vence ao atingir três ciclos | Acomoda duas curvas com a mesma referência |
| D11 | Descartar só inválido / manter resto / limpar | Limpar sequência comprometida | Evita curva dependente da descartada |
| D12 | Reaproveitar pausa / limpar; privilégio do host | Limpar na migração; mesmas regras ao host | Sem teclas acumuladas ou prioridade criada pelo código |
| D13 | Parâmetros fixos / medições | Configuráveis e testes | Distinguir atraso de rede, tick e fila |

Referência 42 permite execução em 43/44, não 45. Validade não é espera. Versão de fila e ACK implementam a limpeza. Registros recuperáveis não são teclas pendentes. Fila cheia ignora a nova tecla. Host mantém apenas a vantagem natural de rede.

## 3. Motor e histórico — confirmadas

| ID | Alternativas | Escolha | Motivo/efeito |
|---|---|---|---|
| D14 | Mover uma por vez / destinos juntos | Transição simultânea | Ordem dos jogadores não favorece ninguém |
| D15 | Recuperar teclas / registros | Registros de resultados e controles | Tecla não informa se chegou ou executou |
| D16 | Confirmar no fim / durante o jogo | Registros confirmados por maioria | Recuperação antes do término; separar armazenamento, commit e aplicação |
| D17 | ACK isolado / prefixo cumulativo | Confirmar N exige todos até N | Sem lacunas |
| D18 | Memória / disco | Memória | Escopo menor; versão inicial não aceita processo reiniciado |

Posição é global e pode conter controles sem movimento; sequência de teclas é individual.

## 4. Eleição e recuperação — confirmadas

| ID | Alternativas | Escolha | Motivo/efeito |
|---|---|---|---|
| D19 | Sucessor assume / pede votos | Ranking + histórico elegível + maioria | Preferencial se atualiza ou outro tenta |
| D20 | Estritamente melhor / igualdade | Igualdade permite voto | Cópias idênticas não bloqueiam eleição; comparar época do último registro e posição |
| D21 | Múltiplos / um voto | Um por época | Guardar antes de responder |
| D22 | Timeout autoriza / época e identidade | Época distingue liderança | Silêncio suspeita; host antigo não recupera autoridade |
| D23 | Espera infinita / reduzir quorum / limitar | Próximos candidatos e prazo total | Sem progresso, encerrar; não inventar lista menor |
| D24 | Apagar / impor matriz local / reconciliar | Preservar confirmados e resolver provisórios | Confirmação pode ter anúncio parcial |
| D25 | Maioria escolhe conflito confirmado / parar | Verificar e abortar se real | Não sobrescrever confirmação |
| D26 | Retomar ao eleger / recuperar antes | Eleição → recuperação → sincronização → contagem | Estado recuperado aparece durante pausa |
| D27 | Contagem + janela extra / janela no final | 3 s totais, entrada nos últimos 500 ms | Sem seis segundos; limpar antes e preservar novas teclas |

Prevenções aceitas: voto único, frescor, configuração correta, prefixos, ACK após armazenamento, confirmação na época atual, imutabilidade e aplicação única. EPOCH_START confirma o prefixo recuperado pelo contrato de replicação; não basta anunciar liderança.

## 5. Votantes e saída — confirmadas

| ID | Alternativas | Escolha | Motivo/efeito |
|---|---|---|---|
| D28 | Fixos / alteração confirmada / recálculo local | Alteração pelo histórico | Impede maiorias incompatíveis |
| D29 | Direta / conjunta | Conjunta e definitiva pelas duas maiorias | Nova simples só após final confirmado |
| D30 | Morto desconecta / assiste / escolhe | Pode assistir ou sair com segurança | Moto e processo votante são independentes |
| D31 | Fechar / esperar transferência e remoção | Aguardar aprovação | Falha no meio usa recuperação |
| D32 | Só TCP / só teclas / heartbeat | Atividade após três intervalos sem comandos | Silêncio no teclado não é falha; TCP pode demorar |
| D33 | Esperar tick / responder imediatamente | ACK e anúncio imediatos | Reduz espera artificial |

Ao armazenar a conjunta, a versão inicial usa sua restrição conservadora para votar; é detalhe técnico para não relaxar quorum sem anúncio. Host eliminado pode coordenar e, após abdicar, não reassume sozinho.

## 6. Lobby e encerramento

Todas confirmadas, exceto D41, **base inicial**.

| ID | Alternativas | Escolha | Motivo/efeito |
|---|---|---|---|
| D34 | Automático / criador inicia | Criador com três/quatro | Pode esperar pelo quarto |
| D35 | Entradas durante preparação / congelar | Congelar tentativa | RTT, conexões e spawns usam mesmo conjunto |
| D36 | Botão / sem ACK / automático | READY automático, todos | Sem ação extra, com verificação |
| D37 | Começar com restantes / cancelar | Cancelar e manter PREPARANDO | Criador pede outra tentativa mesmo com três |
| D38 | Resultados individuais / global | Global | Aplicativo deriva resultado individual |
| D39 | Fechar ao enviar / maioria / todos | Todos da sessão confirmam entrega | Maioria decide; todos recebem no fechamento normal |
| D40 | Lobby obrigatório / sair / escolha | Lobby ou saída opcionais | Lobby ausente não altera resultado |
| D41 | Contrato imutável / revisar | Estados e modelos revisáveis | Atualizar documentos, código e testes juntos |

Timeout não é ACK. Eliminações anteriores não passam a empatar com os finalistas. Saída normal aguarda autorização; para receber novos jogadores, reabrir a sala; controle passa ao presente mais antigo se o criador sair.

## 7. Escolhas técnicas iniciais da especificação

Sem atribuí-las como novas falas do grupo:
- SHA-256, JSON canônico, IDs/correlação de mensagens.
- Modelos completos em protocolo.md, limite de buffers e timeouts.
- 8 ciclos/s, arena 40×30, spawns afastados e cinco amostras RTT/destino.
- Um laço dono dos dados; sem adição/reentrada durante partida.
- Saída entre movimentos sem deslocar demais; START como início lógico.
- Configuração aplicada distinta da conservadora; versões identificam transições.
- Comandos de execução documentados como interface a construir.

Calibrar valores em testes. Mudança incompatível de campos revisa o contrato.

## 8. Limites, revisões e manutenção

Com dois votantes, perder um impede quorum. Não há continuidade sob qualquer sequência de falhas; demonstrar o limite frente ao enunciado. Não contornar contando apenas quem responde. Não há resistência a fraude, recuperação de processo sem memória ou entrega a máquinas desaparecidas.

Revisões encerradas: RTT ao lobby → entre pares; idade 2 → 3; dúvida Raft → protocolo específico; prontidão → automática; duas fases de 3 s → uma com 500 ms finais; entrega final → todos; eleição genérica → regras de época, frescor, voto e prazo.

Para revisar: referenciar ID, registrar regra antiga/nova e motivo, atualizar arquitetura/protocolo e testes. Formatos podem seguir a proposta inicial autorizada; relaxar quorum, permitir reentrada ou alterar janela é mudança real de comportamento. Documentação detalhada não equivale a programa validado.
