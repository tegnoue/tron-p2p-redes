# Guia da documentação

Este diretório é o ponto de partida para implementar, testar e apresentar o Tron P2P.

| Documento | Pergunta que responde |
|---|---|
| [Arquitetura](arquitetura.md) | Como o sistema está organizado e por que funciona assim? |
| [Glossário](glossario.md) | O que significam os termos e contadores? |
| [Protocolo](protocolo.md) | O que enviar, validar, armazenar e fazer em cada situação? |
| [Implementação e apresentação](implementacao.md) | Em que ordem construir e como demonstrar os requisitos? |
| [Decisões](decisoes.md) | Quais alternativas foram discutidas e o que foi escolhido? |

## Ordem sugerida

1. Ler arquitetura e as cinco palavras iniciais do glossário.
2. Implementar transporte, lobby e motor isoladamente.
3. Seguir os estados e mensagens do protocolo.
4. Acrescentar confirmação, eleição e reconfiguração, testando cada etapa.
5. Preparar a demonstração com os cenários de implementação.

Não tentar programar eleição antes de conseguir explicar comando, ciclo, registro, posição e época.

## Situação dos documentos

A versão 1 fornece um contrato inicial completo de mensagens e algoritmos para a implementação. Os valores padrão e detalhes de estrutura de código são escolhas técnicas iniciais.

A documentação não significa que o aplicativo ou seus testes já existam. Não há afirmação de que a implementação tenha provado todas as propriedades distribuídas.

O histórico de decisões preserva as escolhas feitas na discussão. Os outros arquivos descrevem diretamente o funcionamento esperado.

## Regras que precisam ficar visíveis para toda a equipe

- Contagem de três segundos; teclado abre só nos últimos 500 ms.
- Até dois comandos pendentes; expiração ao atingir três ciclos.
- Registros confirmados são imutáveis.
- Um voto por época.
- Votantes não são apenas motos vivas.
- Não reduzir quorum com base em quem responde.
- Host antigo não pode reassumir sozinho.
- Sem quorum suficiente, parar com diagnóstico em vez de criar resultado.
- A continuidade irrestrita após desconexões sucessivas não é garantida; veja o limite na arquitetura.

## Como alterar o contrato

Uma correção deve atualizar os documentos, os tipos compartilhados e os testes afetados no mesmo trabalho. Se alterar um campo incompatível com os participantes existentes, aumentar a versão.

Antes de implementar uma solução local para uma dúvida, verificar se ela muda um estado, uma mensagem, uma maioria ou a interpretação de um registro. Se mudar, precisa ser compartilhada com a equipe.

As referências externas úteis são as documentações de socket, selectors, queue, threading, json, hashlib, time e unittest da biblioteca padrão do Python. Bibliotecas que automatizem o multiplayer, RPC ou a sincronização não substituem o protocolo deste trabalho.
