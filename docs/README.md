# Por onde começar

| Preciso… | Leia |
|---|---|
| Entender o sistema | [Arquitetura](arquitetura.md) |
| Saber o que construir e testar nos 11 dias | [Implementação](implementacao.md) |
| Consultar campos, mensagens e algoritmos | [Protocolo](protocolo.md) |
| Entender um termo | [Glossário](glossario.md) |
| Saber o que foi escolhido e por quê | [Decisões](decisoes.md) |

Leia arquitetura e implementação primeiro. Use o protocolo durante a programação; não é necessário ler novamente toda a especificação a cada etapa.

## Regras que todos precisam lembrar

- Contagem de 3 s; entrada apenas nos últimos 500 ms.
- Dois comandos pendentes; expiração ao atingir três ciclos.
- Registro confirmado é imutável e aplicado uma vez.
- Um voto por época; ranking não substitui maioria.
- Moto viva e processo votante são coisas diferentes.
- Sem quorum, não reduzir a lista localmente nem inventar resultado.

## Alterações

Mudar campo, estado, maioria ou interpretação de registro exige atualizar documentação, tipos compartilhados e testes juntos. Alterações incompatíveis aumentam a versão do protocolo. Valores iniciais são ajustáveis por testes; comportamentos novos precisam constar no registro de decisões.

Os documentos são um contrato de implementação, não evidência de que o código já funciona. Consulte a biblioteca padrão do Python: socket, selectors, queue, threading, json, hashlib, time e unittest.
