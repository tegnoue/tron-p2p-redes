# Game Tron Redes

Projeto de Redes de Computadores do curso de Engenharia de Software da UnB. O objetivo é a especificação e implementação de um protocolo de aplicação customizado para um jogo Tron multijogador em tempo real. 

A solução utiliza uma arquitetura híbrida construída inteiramente com *sockets* TCP puros em Python. Um servidor centralizado atua como Lobby para descoberta de jogadores, enquanto as partidas ocorrem numa malha Peer-to-Peer (P2P) com um par autoritário. O sistema garante consistência de estado e tolerância a falhas através da migração determinística de host em caso de desconexão.

## Estrutura do Projeto
O código-fonte está isolado no diretório `src/` para separar a lógica de rede das regras do jogo:
* `src/core/`: Domínio partilhado, configuração e serialização do protocolo.
* `src/lobby/`: Servidor central de descoberta e registo.
* `src/game/`: Motor do jogo Tron (matriz, regras e colisões isoladas da rede).
* `src/node/`: Nó do jogador, interface de terminal e máquina de estados P2P.
* `docs/`: Especificação técnica da arquitetura e do protocolo (RFC).

## Configuração do Ambiente
Este projeto utiliza o [Poetry](https://python-poetry.org/) para gestão de dependências e isolamento do ambiente virtual.

1. Clone o repositório:
   ```bash
   git clone [https://github.com/SEU_USUARIO/game-tron-redes.git](https://github.com/SEU_USUARIO/game-tron-redes.git)
   cd game-tron-redes
   ```
2. Instale as dependências (inclui `rich` para a interface e `python-dotenv`):
   ```bash
   poetry install
   ```
3. Configure as variáveis de ambiente:
   ```bash
   cp .env.example .env
   ```

## Execução
Abra terminais separados para o servidor e para os clientes. Utilize o ambiente do Poetry para executar os módulos.

**Para iniciar o Lobby:**
```bash
poetry run python -m src.lobby
```

**Para iniciar um Jogador (Nó):**
```bash
poetry run python -m src.node
```