# Documentação do Tron P2P

A documentação descreve um jogo em rede para três ou quatro processos. O lobby prepara a sala; os jogadores mantêm conexões diretas; um host calcula os movimentos e replica registros para confirmação e recuperação.

Cada página apresenta o contexto necessário ao tema. Os links permitem aprofundar ou localizar o contrato técnico, sem substituir as explicações da própria página.

| Documento | Conteúdo |
|---|---|
| [Arquitetura](arquitetura.md) | Componentes, partida, comandos, confirmação e tratamento de falhas |
| [Protocolo](protocolo.md) | Formatos JSON, campos, validações e algoritmos |
| [Decisões](decisoes.md) | Problemas, alternativas, escolhas e consequências |
| [Glossário](glossario.md) | Termos com definições e exemplos |
| [Implementação](implementacao.md) | Organização do código, plano de 11 dias, testes e apresentação |

## Regras principais

O teclado deve abrir apenas nos últimos 500 ms da contagem de três segundos. Cada jogador pode manter dois comandos pendentes, e um comando vence ao atingir três ciclos de idade.

Um registro confirmado não pode ser alterado e deve ser aplicado uma única vez. Cada processo pode conceder um voto por época. A maioria depende da configuração de votantes, não da quantidade de sockets disponíveis.

A implementação deve preservar essas regras e demonstrar seus limites. Com dois votantes, a perda de um impede formar maioria e exige encerramento controlado. A documentação não comprova que o código já foi validado.

## Atualização dos documentos

Mudanças de comportamento devem atualizar arquitetura, decisões, protocolo e testes. Campos incompatíveis exigem revisão da versão. Os valores iniciais podem ser ajustados por medições, mantendo a mesma configuração em todos os processos da partida.
