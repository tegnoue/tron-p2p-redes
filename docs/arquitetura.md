# Arquitetura do Tron P2P

## 1. Visão geral

Três ou quatro processos de jogadores iniciam uma partida numa grade. A cada ciclo, motos avançam uma célula e deixam rastro permanente. Colisões eliminam; vence a última sobrevivente, ou há empate se as últimas caírem juntas.

O lobby registra e organiza salas. A partida usa malha completa TCP, independente do lobby. Um jogador é o host: calcula ciclos e replica registros para confirmação. Há protocolo próprio de eleição e recuperação, sem implementar Raft completo.

Endereços/portas são configuráveis; usar diretamente sockets. JSON, terminal, hashes, configuração e logs admitem bibliotecas auxiliares. Estado/histórico ficam em memória; diagnóstico pode ir para disco. Não há entrada tardia, reentrada de processo reiniciado ou proteção contra fraude nesta versão.

**Limite:** maioria de dois exige ambos. Sem quorum, encerrar de forma controlada, sem inventar vencedor. Não garantir continuidade sob qualquer sequência de desconexões; apresentar esse limite frente ao enunciado.

## 2. Componentes e rede

| Área | Responsabilidade |
|---|---|
| core | Tipos, configuração, codec, hashes e erros |
| lobby | Sessões, salas e preparação; não calcula partidas |
| game | Motor determinístico sem sockets/teclado |
| node/network | Conexões, buffers e filas de envio |
| node/session | Comandos, estados, histórico, votos e liderança |
| node/ui | Teclas e apresentação de uma cópia do estado |

Um laço é dono dos dados; outras threads entregam eventos. Arquivos podem variar. O menor ID inicia a conexão bidirecional: três conexões com três jogadores, seis com quatro. Todos abrem a porta P2P antes de registrar.

TCP entrega bytes, não mensagens nem prazos. Usar JSON+LF, buffer, TCP_NODELAY e fila por conexão. Anunciar endereço alcançável, não 0.0.0.0; porta de conexão ao lobby não é a de escuta.

## 3. Preparação e contagem

Criador solicita início → congelar participantes/tentativa → montar malha → medir RTT → lobby distribui ranking/configuração → READY automático de todos → confirmar base e liderança → contagem.

Ranking usa média RTT entre pares, com desempate por ID; fica fixo e não substitui votos. Configuração compartilha arena, spawns sorteados entre pontos predefinidos, parâmetros e votantes. Criador pode não ser host.

Falha antes de iniciar cancela tentativa e mantém PREPARANDO, mesmo com três restantes. Criador pede outra ou reabre entradas por CANCEL_PREPARATION. Se sair, assume o presente mais antigo; sala vazia é removida. IDs antigos não valem. START é o marco lógico definido no protocolo; queda do lobby só pode cancelar preparação ainda não iniciada.

**Contagem total de 3 s:** motos paradas; teclado bloqueado nos primeiros 2,5 s e liberado nos últimos 500 ms. Limpar filas antes; preservar novas teclas. Host anuncia fases por relógio monotônico. Atraso da rede pode reduzir a janela observada.

## 4. Comandos e motor

Validação local imediata pela última direção aceita, ou oficial sem pendências. Repetida/oposta é ignorada. Dois pendentes incluem enviados; aceitação não libera espaço. Fila cheia ignora nova tecla. Host revalida, reserva primeiro ciclo aberto e aplica uma curva/jogador/ciclo; sem comando, mantém direção.

    execução - referência >= 3 → vencido

Referência 42 permite 43/44, não 45. Verificar reserva/execução; não esperar para vencer. Fechar entradas de todos no mesmo ponto. Sequência comprometida limpa fila e muda versão com ACK. Migração limpa todas as pendências, não registros recuperáveis. Host segue mesmas regras, com vantagem natural de rede.

O motor calcula todos os destinos antes de alterar a arena. Resolve paredes, rastros e destinos iguais; aplica efeitos e resultado. Posições iniciais/rastros ficam ocupados, inclusive após eliminação. Troca de posições elimina ambas. Destino interno alcançado ocupa célula, mesmo em colisão; parede não cria célula externa. Saída é controle entre movimentos, sem deslocar demais. Casos exatos: protocolo §2 e §5.

## 5. Histórico, confirmação e recuperação

Comando é pedido; ciclo conta movimentos; registro é decisão; index é sua posição global; época conta tentativas de liderança. Controles ocupam posições sem mover motos.

Processos guardam estado confirmado, log provisório/confirmado, commit_index, last_applied, época/voto, votantes e filas. Host acompanha armazenamento por par. Estado candidato não substitui confirmado.

Fluxo: calcular → registrar → distribuir → armazenar/ACK imediato → quorum → confirmar → aplicar uma vez e apresentar. Confirmar N exige prefixo completo. Registro atual confirma seu prefixo. Há no máximo um ciclo provisório; atraso pausa, sem pular células ou compensar com rajada.

Após três intervalos sem comandos, enviar atividade; tráfego válido conta, inclusive nas pausas. Timeout monotônico é suspeita, não remoção.

Época E escolhe ranking[(E-1) % tamanho], pulando removidos. Um voto/época; candidato precisa de quorum e histórico ao menos tão atualizado por (época do último registro, posição). Igualdade permite. Época nova não reescreve log antigo.

O eleito reconcilia: completar ausentes; ignorar iguais; substituir só sufixo provisório; verificar e abortar conflito confirmado. Confirma EPOCH_START e sincroniza snapshot ancorado no histórico antes da contagem. Queda não desfaz ciclo confirmado anunciado parcialmente. Cálculo só na memória do host perdido não é recuperável. Sem progresso no prazo, encerramento controlado, sem simultaneidade garantida entre partições.

## 6. Votantes, saída e encerramento

Moto eliminada pode assistir/votar; host eliminado pode coordenar. Reconfiguração:
CONFIG_JOINT → duas maiorias → transição → CONFIG_FINAL → duas maiorias → nova lista.
Uma alteração por vez; desde armazenamento da conjunta, usar regra conservadora. Versões identificam listas; timeout não desfaz confirmado.

Saída aguarda PLAYER_LEFT, reconfiguração e LEAVE_APPROVED. Host pausa, atualiza sucessor e transfere sem reassumir sozinho. Falha no meio segue recuperação.

Resultado terminal CYCLE/PLAYER_LEFT é global; aplicativo deriva situação individual. Eliminados anteriores não empatam com finalistas. Todos ainda integrantes confirmam entrega antes de SESSION_CLOSE. Timeout não é ACK; tratar falha. Controles posteriores não mudam placar. Resultado desconhecido deve ser recuperado ou informado indisponível.

Usuário escolhe lobby ou saída. Lobby ausente permite tentar novamente, sem reabrir partida. Manter registros disponíveis durante fechamento.

## 7. Estados e leitura

    DESCONECTADO → CONECTANDO_LOBBY → NO_LOBBY → NA_SALA
    → PREPARANDO → CONTAGEM → JANELA_ENTRADA → EM_PARTIDA
    → ENCERRANDO → RESULTADO

Falha/transferência: SINCRONIZANDO → recuperação e retomada. Rede continua nas pausas. Liderança, moto, voto e controle da sala são dimensões independentes.

Próximo: [plano de implementação](implementacao.md). Consultar [protocolo](protocolo.md) para campos, cálculos, parâmetros e transições, e [glossário](glossario.md) para termos. Esses detalhes ficam em um único lugar para evitar repetição.
