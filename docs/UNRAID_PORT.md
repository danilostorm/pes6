# Recompilar PES 6 PSP no Unraid (prova de conceito)

**Status:** fluxo de build criado e scripts inspecionados; **nao ha confirmacao de que PES 6 compile ou seja jogavel** no framework. O motor do launcher continua independente do resultado. Execute somente com copia do jogo que voce tenha direito de utilizar.

## Pre-requisitos

- ISO local em `/mnt/user/appdata/pes6/pes6.iso`.
- Unraid com Docker, internet para clonar ferramentas abertas e espaco livre suficiente para ISO extraida, toolchain e codigo gerado (recomenda-se reservar varios GB; idealmente 10 GB livres).
- Armazenamento saudavel. Se `dmesg` indicar erros de I/O, investigue e proteja seus backups antes de operacoes pesadas.
- Sem necessidade de instalar apt, Emscripten, CMake ou Git no proprio Unraid: o ambiente de compilacao usa um container Ubuntu.

## Compilar

```bash
cd /mnt/user/appdata/pes6
git pull --ff-only
bash scripts/port-unraid.sh build
```

O comando:
1. constroi uma imagem de ferramenta Ubuntu, de maneira isolada;
2. busca o [PSP Web Recomp](https://github.com/snuri00/psp-web-recomp);
3. extrai a ISO **localmente**, sem alterar a imagem original;
4. busca e compila [pspdecrypt](https://github.com/John-K/pspdecrypt) em `.recomp-work` para tentar obter um ELF;
5. verifica se os primeiros quatro bytes sao `7F 45 4C 46`, instala as ferramentas oficiais do projeto e inicia o port;
6. deixa os arquivos gerados exclusivamente em `.recomp-work/psp-web-recomp`.

O `pspdecrypt` nao e copiado para o repositório, e usa sua licenca GPLv3 de forma independente. O executavel traduzido e o WASM gerado contêm codigo do jogo e **nao devem ser publicados em um repositório publico**.

## Se a descriptografia automatica nao funcionar

No [PPSSPP](https://www.ppsspp.org/), use:
- **Settings > Tools > Developer Tools > Dump decrypted EBOOT.BIN on game boot**.
- Inicie a ISO com a opcao ativada e procure o dump no diretorio `PSP/SYSTEM/DUMP` da pasta de dados do PPSSPP (o nome do arquivo pode usar o ID do jogo).
- Transfira o binario descriptografado para o Unraid, salvando como `/mnt/user/appdata/pes6/.recomp-work/PES6.elf`.
- Rode novamente `bash scripts/port-unraid.sh build`.

O script valida a assinatura ELF antes da compilacao. Nao copie o `EBOOT.BIN` criptografado original com outro nome: isso nao funciona.

## Testar o build isoladamente

Somente se a compilacao completar:

```bash
bash scripts/port-unraid.sh serve
# abra http://IP_DO_UNRAID:8613
docker logs -f pes6-recomp-preview
```

Para mudar a porta de teste, defina `PES6_PREVIEW_PORT=8614` antes de `bash scripts/port-unraid.sh serve`. Para parar: `bash scripts/port-unraid.sh stop`.

**O preview e separado do launcher STOR PES6** (que continua na porta 8788 no seu Unraid). Primeiro precisamos verificar se PES 6 inicia, renderiza e recebe controles; so depois vale conectar a compilacao ao `public/engine-adapter.js`.

O port pode parar por chamadas HLE nao implementadas, suporte do renderer ou outros detalhes do motor diferente dos jogos ja testados no framework. Um build bem-sucedido nao equivale a um jogo funcional.

## Diagnostico

Se houver erros na compilacao, copie as ultimas linhas do terminal, especialmente mensagens `[hle] unimplemented`, falhas de extracao, assinatura ELF ou erros do Emscripten. Para repeticoes, o script reutiliza os repositorios, o arquivo ELF e os artefatos da ISO quando presentes. Variavel `PES6_BUILD_JOBS=2` reduz paralelismo em maquina com pouca memoria.

### Direitos

Nenhuma ISO, EBOOT, ELF, audio, textura, arquivo AFS ou WASM traduzido e carregado para o GitHub. O codigo do launcher e das rotinas de build e publico; dados comerciais permanecem no servidor do usuario.
