# Testar a recompilacao PES6 diretamente no GitHub Actions

**Objetivo:** compilar o PES6 PSP original para WebAssembly em runner Ubuntu
temporario do GitHub e executar um smoke test real com Chromium/Playwright.
Nao sera mais preciso executar `bash scripts/port-unraid.sh build` no AEROCOOL
a cada atualizacao de codigo.

## Configuracao unica necessaria

No [repositorio PES6](https://github.com/danilostorm/pes6), acesse:

1. **Settings → Secrets and variables → Actions → New repository secret**
2. **Name:** `PES6_DRIVE_FILE_ID`
3. **Secret:** somente o ID do arquivo ISO no seu Google Drive,
   *nao* a URL da pasta e *nao* credenciais Google. Veja na sua conta
   o ID do arquivo `Pro_Evolution_Soccer_6_PROPER_EUR_MULTI5_PSP-LIGHTFORCE.iso`.
4. Salve o segredo.

Atualmente esta ISO esta compartilhada no Drive como `anyone / reader`.
Para usar o download sem OAuth, o arquivo precisa continuar acessivel
por link. Se voce restringir o Drive, o job falhara na transferencia;
nesse caso sera necessario configurar uma conta de servico e acesso
privado com credenciais seguras.

A ISO **nao e enviada a este repositorio nem anexada ao GitHub Actions**.
Ela e baixada na maquina temporaria de build e descartada com o runner.
Lembre-se de observar suas permissoes de uso dos arquivos do jogo;
**nao** publique builds contendo codigo ou assets comerciais.

## Rodar uma vez

Abra [Actions](https://github.com/danilostorm/pes6/actions/workflows/pes6-wasm-ci.yml),
selecione **PES6 WebAssembly Auto Build + Browser Smoke**,
clique **Run workflow** e use `main`.

Apos a configuracao do secret, pushes em `main` que alterem os scripts
de build/testes ou o workflow tambem iniciam um novo teste automaticamente.
Nao use Pull Requests publicos para executar o teste com ISO.

## O que o teste faz

- Baixa ISO de 1.248.329.728 bytes diretamente do seu Drive ao runner
  GitHub, sem publicar o arquivo.
- Descriptografa `EBOOT.BIN` localmente com ferramentas abertas e recompila
  o PSPRecomp + WebAssembly usando a mesma cadeia do Unraid.
- Publica o resultado **apenas em 127.0.0.1** dentro do runner.
- Abre o navegador Chromium isolado com Playwright, executa a pagina com
  `?trace=1&threads=0` e coleta o estado do guest.
- Se encontrar `No recompiled function registered at 0x...`, valida o
  endereco no ELF (alinhamento, segmento executavel, instrucao nao nula).
  Se for novo e valido, acrescenta-o a lista da rodada seguinte.
- Para apos ate cinco rodadas ou no primeiro erro que nao pode ser
  corrigido por uma seed (por exemplo HLE, memoria, WebGL, crash JS).
- Faz upload **somente de JSON de diagnósticos e logs resumidos**, nunca
  ISO, EBOOT, WebAssembly ou imagens do jogo.

Limites: GitHub Actions tem limites de disco, CPU, memoria, cota,
transferencia e tempo; o Drive pode limitar downloads. Tambem pode haver
falha especifica de Chromium headless / SwiftShader (WebGL).

**Resultado `running_unverified` nao significa que o PES6 chegou ao menu,
que os controles funcionam ou que esta jogavel**: indica somente que nao
parou durante a janela automatizada. Validacao visual e jogabilidade
precisam de testes adicionais.

## Onde conferir as falhas

Em GitHub → Actions → PES6 WebAssembly Auto Build + Browser Smoke,
abra a execucao recente. A secao `Summary` lista as rodadas e
enderecos encontrados. O artefato `pes6-boot-diagnostics` contem apenas
`smoke-*.json` e `rounds.log`.

Se o teste mostrar `configured=false` significa que falta o segredo
`PES6_DRIVE_FILE_ID`. Esse passo nao pode ser preenchido pela conexao
do Drive ao ChatGPT: contas e permissoes do GitHub Actions sao separadas.
