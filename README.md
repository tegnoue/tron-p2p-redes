# Tron P2P — projeto de Redes

Projeto acadêmico de um jogo Tron com lobby, malha de sockets TCP e protocolo de aplicação específico.

O contrato de implementação e o material de estudo estão em **[docs/README.md](docs/README.md)**.

- [Arquitetura](docs/arquitetura.md)
- [Protocolo de mensagens e algoritmos](docs/protocolo.md)
- [Decisões e alternativas](docs/decisoes.md)
- [Glossário](docs/glossario.md)
- [Implementação, testes e apresentação](docs/implementacao.md)

A documentação descreve o comportamento a construir. Ela não afirma que os módulos e garantias já estejam implementados ou testados.

A regra de preparação é de três segundos no total: teclado bloqueado nos primeiros 2,5 segundos e liberado somente nos últimos 500 ms.

## Ambiente

Usar Python com Poetry. A interface pode utilizar bibliotecas auxiliares de terminal, mas rede e protocolo devem usar diretamente a API de sockets.

Consulte o guia de implementação para configuração, comandos de execução esperados, ordem de construção e demonstrações. Ao concluir cada módulo, atualize as instruções de execução para refletir os comandos realmente disponíveis.
