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
