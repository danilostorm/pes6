# PES 6 PSP: primeiro erro de inicializacao (ULES00476)

## Estado observado

Depois de configurar HTTPS com reverse proxy, a pagina carregou o ELF recompilado
no navegador, inicializou WebGL e exibiu:

```text
[pspweb] module we10psp loaded at 0x8804000-0x9c0c000, 229 imports, 0 relocations, 87746 registered entries
[hle] unimplemented ModuleMgrForUser::0xD8B73127(0x089943DC, ...) -> 0
[kernel] halted: Unsupported Allegrex instruction 0x00000000 at 0x0897FD08: invalid internal function entry
```

O NID `0xD8B73127` corresponde a `sceKernelGetModuleIdByAddress`,
que retorna um UID do modulo que ocupa um endereco. A camada HLE original
retornava `0` genericamente para imports nao implementados. A correção local
em `scripts/patch-psp-modulemgr.py` registra a função e identifica um modulo
dentro do intervalo reservado pelo kernel para o executavel principal.

**A causa direta do erro em 0x0897FD08 ainda nao foi confirmada.** A funcao HLE
faltante e um defeito verificado, mas pode haver tambem endereco de entrada
nao descoberto pelo recompilador, instrucao sobreposta ou codigo carregado
dinamicamente.

## Recompilar e testar novamente

```bash
cd /mnt/user/appdata/pes6
git pull --ff-only
bash scripts/port-unraid.sh stop
bash scripts/port-unraid.sh build
bash scripts/port-unraid.sh serve
```

A recompilacao reutiliza a ISO extraida e o ambiente de build; apenas
dependencias alteradas precisam ser compiladas novamente.

Visite o dominio HTTPS onde o preview esta publicado, acrescentando:
`?trace=1&threads=0`

Exemplo: `https://pes6.hoststorm.cloud/?trace=1&threads=0`.
`trace=1` ativa `PSPWEB_TRACE_HLE` e `PSPRECOMP_TRACE_ON_ERROR`
**dentro do WebAssembly no navegador**, nao no processo HTTP. Observe
os registros no painel da propria pagina ou no Console (F12).

**Coletar:** a primeira linha de erro, as ultimas chamadas HLE antes do erro,
ultimo PC de salto no trace e o endereco do erro. Se persistir `invalid
internal function entry`, avaliar a analise de alvos indiretos em PSPRecomp
em vez de substituir um instrucao desconhecida por NOP.

A pagina do launcher na porta 8788 e a pagina de preview 8613 sao independentes.
Nenhuma compilacao do jogo deve ser versionada neste GitHub publico.

## Fontes

- [PSPSDK Module Manager](https://pspdev.github.io/pspsdk/group__ModuleMgr.html)
- [PSP Web Recomp debugging](https://github.com/snuri00/psp-web-recomp/blob/main/docs/internals.md)

## Segunda execucao: falta de entrada AOT (09/10/2026)

A HLE `sceKernelGetModuleIdByAddress(0x089943DC)` agora retorna `0x101`,
em vez do fallback zero, e o programa progride ate as chamadas de interrupcao.

A falha atual e:

```text
[kernel] halted: No recompiled function registered at 0x0897FD08
```

Este erro indica um PC sem registro no AOT, **nao** prova que os bytes
correspondam a uma funcao valida nem que haja erro no navegador.

Foi adicionado um diagnostico de leitura apenas dos arquivos locais, que
faz a correspondencia entre ELF, intervalos executaveis, palavras Allegrex,
rotulo de codigo e `runtime.register_function` no arquivo C++ gerado:

```bash
cd /mnt/user/appdata/pes6
git pull --ff-only
bash scripts/port-unraid.sh diagnose
```

Para investigar outro endereco sem recompilar:

```bash
PES6_DIAG_PC=0x0897FD08 bash scripts/port-unraid.sh diagnose
```

O comando utiliza o contêiner compilador existente, com o repositorio
montado como **somente leitura**. Nao modifica a ISO, o ELF nem o build.

Se a instrucao estiver fora de um segmento RX, verificar o salto/pilha;
se estiver dentro e o rotulo aparecer sem registro, corrigir o conjunto
de entradas de dispatch; se nao tiver rotulo, corrigir a descoberta
de fluxo (alvos indiretos, seeds) do PSPRecomp.

## Terceira etapa: falta de cobertura de codigo em 0x0897FD08

Diagnostico do servidor AEROCOOL:

```text
ELF 1914920 bytes, type=0x0002
PT_LOAD 0x08804000-0x089D6070, flags=111
0x0897FD08: 0x8FA20224 (instrucao MIPS nao nula)
generated_unit_0094.cpp: sem rotulo L_0897FD08 e sem registro
```

A analise estatica atual **nao cobre esse trecho**. O endereco esta no
segmento executavel da imagem ELF e sucede um salto incondicional com
delay slot; um destino indireto/jump table e uma explicacao possivel,
mas ainda nao foi demonstrada.

A rotina `scripts/patch-psp-extra-seeds.py` modifica apenas o checkout
local do PSPRecomp, permitindo entradas explicitas e validadas na analise.
O script `port-unraid-inner.sh` recompila as ferramentas do analisador
apos esse patch. O build padrao do PES6 passa `0x0897FD08` via
`PSPRECOMP_EXTRA_SEEDS`. Este teste nao ignora instrucoes invalidas
nem altera ELF, ISO ou textura do jogo.

```bash
cd /mnt/user/appdata/pes6
git pull --ff-only
bash scripts/port-unraid.sh stop
bash scripts/port-unraid.sh build
bash scripts/port-unraid.sh diagnose
bash scripts/port-unraid.sh serve
```

A saida deve conter `[analysis] extra seed 0x897fd08 added` ou
`already discovered`. Depois do build, o diagnostico deve mostrar
`Instruction label L_0897FD08: YES`; se nao mostrar, capturar a
saida e **nao assumir** que esta corrigido. Mesmo que o codigo seja
registrado, pode surgir uma proxima falha de inicializacao.

Para testar outro PC posteriormente, sem novo commit de codigo:
`PES6_EXTRA_SEEDS=0x0897FD08,0xENDERECO bash scripts/port-unraid.sh build`.
Usar somente enderecos confirmados pelo diagnostico dentro do segmento
executavel; cada endereco adicional deve ser revisado individualmente.

## Quarta etapa: entrada AOT faltante em 0x08986598

A recompilacao que adicionou 0x0897FD08 agora passou pela inicializacao
principal, imprimiu o banner de PES 6 PSP e iniciou os servicos de video:

```text
[guest] - PES6 for PSP No.0001 - (Sep 29 2006 20:03:03)
[hle] sceGeListEnQueue(...) -> 1
[hle] sceGeDrawSync(...) -> 0
[hle] sceDisplaySetMode(... 480, 272 ...) -> 0
[kernel] halted: No recompiled function registered at 0x08986598
```

O PC 0x08986598 esta dentro da faixa RX do ELF, conhecida do diagnostico
anterior (0x08804000..0x089D6070). Seus bytes ainda **nao foram analisados**
no AEROCOOL; a compilacao agora valida se cada PC solicitado e alinhado,
file-backed, RX e possui instrucao nao nula antes de prosseguir.

O script de build inclui por padrao as duas entradas observadas:
`PES6_EXTRA_SEEDS=0x0897FD08,0x08986598`. Se qualquer validacao falhar,
**o build para sem publicar novo motor**, preservando o executavel antigo.

```bash
cd /mnt/user/appdata/pes6
git pull --ff-only
bash scripts/port-unraid.sh stop
bash scripts/port-unraid.sh diagnose   # agora analisa 0x08986598 por padrao
bash scripts/port-unraid.sh build
bash scripts/port-unraid.sh diagnose
bash scripts/port-unraid.sh serve
```

Com `?trace=1&threads=0` o PSPRecomp tambem registra
`[missing-aot]` e os ultimos 24 `[missing-aot-previous]` ao parar por
uma funcao nao registrada; a instrumentacao so roda com diagnostico.
O objetivo e identificar a origem de futuros saltos, nao apenas
repetir seeds cegamente. O console do navegador pode ser utilizado para
obter esse registro.

Se o navegador ainda apontar o endereco antigo apos recompilar, forcar
atualizacao completa da pagina, verificar cache do proxy e conferir a
saida do novo build. Um numero de FPS na pagina nao significa que o jogo
esta funcional enquanto aparece `Stopped`.

## Quinta etapa: terceiro destino AOT ausente (0x089864DC)

Depois de incluir as entradas `0x0897FD08` e `0x08986598`,
o jogo chegou novamente a inicializacao de video, mas parou em:

```text
[missing-aot] pc=0x089864DC ra=0x089850B8 sp=0x09FBF950 word=0x50C0001B
[kernel] halted: No recompiled function registered at 0x089864DC
```

A instrucao `0x50C0001B` e uma ramificacao condicional MIPS
`beql a2,zero,+27`, cujo alvo tomado fica em `0x0898654C`.
Este dado e um indício de código válido, mas **não estabelece qual
salto anterior gerou o PC 0x089864DC**: o histórico de 24 despachos
do lado de fora da unidade C++ não inclui necessariamente saltos
encadeados internamente.

Os valores padrao dos scripts agora sao:

```text
PES6_EXTRA_SEEDS=0x0897FD08,0x08986598,0x089864DC
PES6_DIAG_PC=0x089864DC
```

O script `validate-aot-seeds.py` verifica no ELF local que cada PC
esta alinhado, dentro do segmento executavel file-backed e tem uma
instrucao diferente de zero **antes** do codegen. Se falhar, nao
force o seed. Se passar, o novo teste de navegador sera necessario
para descobrir se ha outras lacunas CFG ou problemas de HLE.

```bash
cd /mnt/user/appdata/pes6
git pull --ff-only
bash scripts/port-unraid.sh diagnose
bash scripts/port-unraid.sh stop
bash scripts/port-unraid.sh build
bash scripts/port-unraid.sh diagnose
bash scripts/port-unraid.sh serve
```

Quando houver novos enderecos de entrada, pode-se passa-los sem
editar novamente o repositorio:

```bash
PES6_DIAG_PC=0xENDERECO bash scripts/port-unraid.sh diagnose
PES6_EXTRA_SEEDS=0x0897FD08,0x08986598,0x089864DC,0xENDERECO bash scripts/port-unraid.sh build
```

Mas primeiro validar os enderecos no ELF e revisar o trace.
Se muitos PCs diferentes continuarem faltando, deve-se investigar
uma correcao sistematica do analisador (alvos indiretos/tabelas de salto),
em vez de adicionar centenas de entradas manualmente.

## Sexta etapa: preview HTTPS servindo compilacao anterior

O arquivo de terminal de 09/10 confirmou build bem-sucedido com os 3 seeds:

```text
[analysis] extra seed 0x897fd08 added
[analysis] extra seed 0x8986598 added
[analysis] extra seed 0x89864dc added
[6/6] Linking CXX executable profiles/web/index.html
Instruction label L_089864DC: YES
Exact dispatcher registration: YES
```

Entretanto, o console do navegador trouxe `87775 registered entries`
e falha em `0x08986598`, que pertencem a uma das compilacoes anteriores.
Antes de adicionar outros seeds, verificar o caminho Nginx e caches.

O modo `bash scripts/port-unraid.sh serve` agora publica
`build-info.json` dentro do preview, contendo a hash SHA-256 do index.wasm
atual, e aplica `Cache-Control: no-store` no servidor original,
preservando requisições HTTP Range e os headers de isolamento.

```bash
cd /mnt/user/appdata/pes6
git pull --ff-only
bash scripts/port-unraid.sh stop
bash scripts/port-unraid.sh serve
curl -fsS "http://127.0.0.1:8613/build-info.json"
curl -fsS "https://pes6.hoststorm.cloud/build-info.json?check=$(date +%s)"
curl -sSI http://127.0.0.1:8613/index.wasm | grep -Ei 'Cache-Control|Last-Modified|Content-Length'
curl -skSI https://pes6.hoststorm.cloud/index.wasm | grep -Ei 'Cache-Control|Age|X-Cache|Last-Modified|Content-Length'
```

Se os hashes/URLs divergirem, corrigir a configuracao do proxy
(host de destino e opcao de cache de assets) antes de recompilar o jogo.
Se as hashes forem iguais e o erro permanecer somente no navegador,
fazer teste em janela anonima ou Chrome F12 -> Network -> Disable cache,
recarregar (Ctrl+Shift+R) e inspecionar os arquivos JS/WASM efetivamente
baixados. O JSON de build nao inclui conteudo comercial, apenas hashes,
tamanhos e nomes dos artefatos.

**Nao confundir:** o arquivo `build-info.json` vem do servidor;
comparar o hash no JSON nao e prova de que a pagina anteriormente aberta
tenha carregado o mesmo WASM. E apenas um primeiro teste de origem.

## Setima etapa: 0x089864D0, recuperar candidatos estruturais ao redor

Os arquivos no preview HTTP e dominio HTTPS tem o mesmo SHA-256 do
WebAssembly `5ce7a3129021b876...`, confirmando o caminho do proxy.
No novo teste, apos tres entradas adicionais, ocorreu:

```text
[missing-aot] pc=0x089864D0 ra=0x089850B8 sp=0x09FBF950 word=0x8D030008
[kernel] halted: No recompiled function registered at 0x089864D0
```

O endereco 0x089864D0 esta exatamente apos o `jr ra` em 0x089864C8
e seu delay slot em 0x089864CC. Analogamente, 0x089864DC vem logo
depois de um `j` em 0x089864D4 e seu delay slot em 0x089864D8.
Sao entradas plausiveis para codigo acessado indiretamente (ainda
nao demonstrado que foram originadas por saltos validos).

O experimento `scripts/recover-psp-blocks.py` detecta possiveis
entradas apos `J`/`JR`, **apenas** na regiao
`0x08986480:0x08986620`, no ELF descriptografado local.
O limite e 16 entradas recuperadas, 32 no total. Rejeita candidatos
desalinhados, zerados ou fora do segmento executavel; o build
continua submetendo toda a lista a `validate-aot-seeds.py`.
Isso **nao e** uma correcao universal para o PSPRecomp: pode haver
falsos positivos, desempenho pior ou nova incompatibilidade.
Nenhum binario comercial entra no GitHub.

```bash
cd /mnt/user/appdata/pes6
git pull --ff-only
bash scripts/port-unraid.sh stop
bash scripts/port-unraid.sh diagnose
bash scripts/port-unraid.sh build
bash scripts/port-unraid.sh diagnose
bash scripts/port-unraid.sh serve
```

A compilacao mostrara `[recover]`, `[preflight]`, `[analysis]` e
`Automatic global codegen completed`. Depois do build, verificar
`Instruction label L_089864D0: YES` e
`Exact dispatcher registration: YES` no `diagnose`.

Para desativar os candidatos automaticos e usar apenas os quatro
enderecos observados nos testes, sem editar o codigo:

```bash
PES6_RECOVER_REGION=off bash scripts/port-unraid.sh build
```

Se a geracao falhar com `RECOVERY FAILED`, nao aumentar o limite
automaticamente; estreitar a regiao ou investigar o CFG e a tabela
de saltos do PES6. Para testes subsequentes, comparar as versoes
do preview via `/build-info.json`, nao acrescentar varios PC sem
verificacao.
