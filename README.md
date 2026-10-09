# STOR PES6 Web

Launcher web e serviço de salas/chat, feitos para rodar no seu próprio servidor e integrar **futuramente** uma versão de PSP de PES 6 recompilada para WebAssembly.

> ⚠️ **Estado atual:** a interface, os controles (barramento de entrada), o serviço de salas, presença, chat, a importação local de arquivos e a instalação Docker estão implementados. **PES 6 NÃO está incluído e ainda NÃO é jogável neste repositório.** A recompilação e a integração do executável original são tarefas separadas.

## Executar

Node.js 20+ (não exige `npm install`):

```bash
npm start
# http://localhost:8787
```

Docker/Unraid:

```bash
git clone https://github.com/danilostorm/pes6.git
cd pes6
docker compose up -d --build
# http://IP_DO_UNRAID:8787
```

Para atualizar: `git pull --ff-only && docker compose up -d --build`.

Na produção, publique atrás de HTTPS (reverse proxy) preservando COOP/COEP e use um hostname separado dos demais sites que precisem de conteúdo cross-origin.

## Compilacao e testes automaticos no GitHub Actions

O projeto inclui o workflow [PES6 WebAssembly Auto Build + Browser Smoke](https://github.com/danilostorm/pes6/actions/workflows/pes6-wasm-ci.yml), que compila e executa o PES6 PSP em um Chromium temporario do GitHub, validando automaticamente ate cinco rodadas de entradas AOT faltantes. Para rodar, configure uma unica vez o segredo `PES6_DRIVE_FILE_ID` com o ID da ISO no Google Drive. Nenhum arquivo comercial e versionado ou disponibilizado como artefato.

Veja [o guia de configuracao e limites do teste automatizado](docs/GITHUB_ACTIONS_TESTING.md). Um smoke test sem travamentos **nao garante** jogabilidade ou menus funcionais.

## Recompilacao experimental do PES 6 (ISO local no Unraid)

O servidor web **nao executa PES 6 apenas porque a ISO esta presente**. Para preparar uma compilacao local, sem adicionar arquivos comerciais ao GitHub:

```bash
cd /mnt/user/appdata/pes6
git pull --ff-only
bash scripts/port-unraid.sh build
# se concluir, iniciar um preview separado:
bash scripts/port-unraid.sh serve
# http://IP_DO_UNRAID:8613
```

O script usa um ambiente Ubuntu isolado e tenta descriptografar o executavel antes de iniciar o PSPRecomp/Emscripten. Nao ha garantia de que o jogo compile ou inicialize sem ajustes especificos de HLE/GPU/arquivo. Consulte [guia completo para Unraid](docs/UNRAID_PORT.md).

## O que foi construído

- **Página responsiva PT-BR** com painel de jogo, status real do motor e modos touch
- **Entrada unificada** para teclado, Gamepad API e toque, com tratamento de `pointerdown`/`pointerup` e liberação de teclas para evitar botões travados
- **Gráficos**: perfis econômico/equilibrado/alto e opções de resolução/FPS que o runtime futuro pode consumir
- **API** para criação/entrada/saída de salas, presença e chat em tempo real via Server-Sent Events (SSE); sem contas e sem persistência de salas
- **Armazenamento de arquivos locais** com IndexedDB: importação/download (não equivale a instalar os arquivos no PSP)
- **Servidor HTTP sem dependências externas** com cabeçalhos de isolamento e suporte a `Range`
- **Docker Compose** sem exigir GPU no servidor (o objetivo é renderizar no cliente)

## Limitações claras

- Não usa nem redistribui código privado, scripts, compilados ou arquivos comerciais do site de referência.
- O HTML de referência não é o motor do jogo. O backend de sala não transforma o jogo em multiplayer até portar a rede ad-hoc do PSP.
- Versão atual do lobby usa memória do processo; reinício apaga salas/chat e não é escalável horizontalmente sem backend compartilhado.
- O membro é autenticado por token efêmero em URL SSE. Para acesso público em escala, adicionar contas, rate limiting, proteção contra abuso, armazenamento persistente e revisão de segurança.
- A camada de presença desconecta membros inativos; se a aba suspender em dispositivos móveis, será necessário reconectar à sala.
- O controle touch só envia ações ao jogo após a instalação de um runtime real, conforme [guia de integração](docs/BUILD_ENGINE.md).

## Arquitetura

```text
public/index.html + style.css  → shell e painéis
public/app.js                  → configurações, controle, salas e IndexedDB
public/engine-adapter.js       → contrato de integração com WASM
public/runtime/                → reservado para build local licenciado
server.mjs                     → arquivos estáticos + Range + REST + SSE
```

## Referências e direitos

- [PSP Web Recomp](https://github.com/snuri00/psp-web-recomp): ferramenta de recompilação sob MIT; nenhum código do upstream foi incorporado aqui.
- [OptiJuegos PES6](https://pes6.optijuegos.net/): referência de funcionalidades, sem copiar os arquivos do jogo, assets, scripts ou servidor.
- O jogo PES 6, seus nomes, escudos, áudio, uniformes e arquivos associados pertencem aos titulares respectivos. Este projeto não é afiliado à Konami.

## Testes

```bash
npm run check
npm test
```

Mais detalhes em [docs/BUILD_ENGINE.md](docs/BUILD_ENGINE.md).

## Arquivos PES6 verificados em 09/10/2026

A análise do material fornecido confirmou a edição PSP europeia **ULES00476**, versão **1.03**. O `EBOOT.BIN` ainda está **criptografado** (`~PSP`), portanto o motor jogável segue pendente. O repositório inclui agora um [diagnóstico detalhado e orientações](docs/ASSET_PREFLIGHT.md) e um **verificador local**:

```bash
node scripts/inspect-psp.mjs --dir "/caminho/para/PES6"
```

O verificador não decripta, distribui nem recompila os arquivos do jogo.

