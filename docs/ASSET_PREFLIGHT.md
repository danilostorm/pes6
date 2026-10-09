# Diagnóstico dos arquivos de PES 6 (PSP)

## Verificação de 9 de outubro de 2026

Na pasta disponibilizada no Google Drive foram encontrados uma imagem ISO de 1.248.329.728 bytes, um arquivo 7z de 629.135.917 bytes e uma pasta PSP_GAME extraída. Nenhum desses arquivos foi inserido no GitHub.

O PARAM.SFO confirma: TITLE = Pro Evolution Soccer 6; DISC_ID = ULES00476; DISC_VERSION = 1.03; PSP_SYSTEM_VER = 2.81.

O EBOOT.BIN tem 1.915.264 bytes e assinatura hexadecimal 7e505350 (~PSP): é um executável PSP criptografado, não um ELF pronto para recompilar. O BOOT.BIN tem 1.914.920 bytes e inicia com 00000000, portanto não foi identificado como um ELF utilizável.

Na pasta USRDIR há arquivos AFS de áudio e dados e módulos PRX de rede ad-hoc. A existência dos arquivos não demonstra que o jogo já inicie no navegador nem que o modo online funcione.

## Verificador local incluído

Executar com Node.js 20+ sobre uma pasta que contenha PSP_GAME:

    node scripts/inspect-psp.mjs --dir /caminho/PES6

Ou usando arquivos separados:

    node scripts/inspect-psp.mjs --eboot /caminho/EBOOT.BIN --boot /caminho/BOOT.BIN --param /caminho/PARAM.SFO

Ele emite um JSON com a identidade do título e o estado do executável. Não decripta, recompila, copia ou publica dados do jogo. ready_for_recompiler = false enquanto o EBOOT original estiver no formato ~PSP.

## Próximo experimento

1. Preparar uma VM Linux com git, CMake, Ninja, Python 3, C++20 e a toolchain do projeto PSP Web Recomp.
2. Sobre arquivos obtidos legitimamente, produzir localmente um ELF com uma ferramenta compatível com EBOOT de PSP.
3. Executar os scripts de portabilidade em uma ISO ou pasta extraída e capturar a primeira falha real do jogo.
4. Corrigir gradualmente APIs de PSP, GPU, áudio, arquivos e input até obter o primeiro boot.
5. Só depois conectar o motor ao launcher, integrar saves e implementar netplay ad-hoc.

Referência técnica: https://github.com/snuri00/psp-web-recomp

Importante: não distribuir ISO, AFS, EBOOT nem WASM gerado do jogo em um repositório público ou site sem os direitos necessários.
