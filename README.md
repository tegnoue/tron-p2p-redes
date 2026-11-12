# Tron P2P — projeto de Redes

O sistema deve executar um jogo Tron entre três ou quatro processos, com um lobby para descoberta e conexões TCP diretas entre os jogadores. Um host calcula os movimentos e compartilha registros para confirmação, eleição e recuperação.

A documentação está organizada em [docs/README.md](docs/README.md). Arquitetura, protocolo, decisões, glossário e implementação apresentam o contexto necessário a cada assunto.

A contagem deve durar três segundos, com entrada liberada somente nos últimos 500 ms. Os comandos de execução e as garantias descritas devem ser verificados nos testes do aplicativo.
