#!/usr/bin/env bash
# Executado DENTRO do container Ubuntu; deixa todos os artefatos em .recomp-work.
set -euo pipefail

PROJECT=/project
WORK="$PROJECT/.recomp-work"
ISO="$PROJECT/pes6.iso"
UPSTREAM="$WORK/psp-web-recomp"
GAME="$UPSTREAM/games/pes6"
DISC="$GAME/root/disc"
ELF="$GAME/root/EBOOT.BIN"
MANUAL_ELF="$WORK/PES6.elf"
DECRYPTER="$WORK/pspdecrypt/pspdecrypt"
JOBS="${JOBS:-4}"

signature() {
  [[ -f "$1" ]] || return 1
  head -c 4 "$1" | od -An -tx1 | tr -d ' \n'
}
fail() { echo "ERRO: $*" >&2; exit 1; }

[[ -f "$ISO" ]] || fail "Arquivo nao encontrado: $ISO"
mkdir -p "$WORK"

echo "== [1/5] Obtendo PSP Web Recomp (somente codigo aberto)"
if [[ ! -d "$UPSTREAM/.git" ]]; then
  # Versoes anteriores criavam /games/pes6/root antes do git clone.
  # Retirar SOMENTE essas pastas se estiverem completamente vazias.
  # Nao executar rm -rf: pode haver dados do usuario neste caminho.
  if [[ -d "$GAME/root" ]]; then
    rmdir "$GAME/root" "$GAME" "$UPSTREAM/games" "$UPSTREAM" 2>/dev/null || true
  fi
  [[ ! -e "$UPSTREAM" ]] ||
    fail "A pasta $UPSTREAM ja existe e nao e um clone Git. Verifique seu conteudo antes de mover ou remover; nenhum arquivo foi apagado."
  git clone https://github.com/snuri00/psp-web-recomp.git "$UPSTREAM"
fi

echo "== [1.1/5] Aplicando HLE de Modulos do PES6 (patch local, idempotente)"
python3 "$PROJECT/scripts/patch-psp-modulemgr.py" "$UPSTREAM"
mkdir -p "$GAME/root"

echo "== [2/5] Extraindo ISO local do PES6 (arquivo original inalterado)"
if [[ ! -f "$DISC/PSP_GAME/SYSDIR/EBOOT.BIN" ]]; then
  python3 -I "$UPSTREAM/scripts/extract_iso.py" "$ISO" "$DISC"
fi
ENCRYPTED="$DISC/PSP_GAME/SYSDIR/EBOOT.BIN"
[[ -f "$ENCRYPTED" ]] || fail "EBOOT.BIN nao foi encontrado dentro da ISO."
echo "Formato original: $(signature "$ENCRYPTED")"

echo "== [3/5] Preparando executavel ELF"
if [[ -f "$MANUAL_ELF" ]]; then
  [[ "$(signature "$MANUAL_ELF")" == "7f454c46" ]] ||
    fail "O arquivo $MANUAL_ELF existe, mas nao comeca com assinatura ELF."
  cp "$MANUAL_ELF" "$ELF"
  echo "Usando ELF previamente extraido com PPSSPP."
elif [[ "$(signature "$ELF" || true)" == "7f454c46" ]]; then
  echo "ELF ja existente e reconhecido, reutilizando."
else
  if [[ ! -x "$DECRYPTER" ]]; then
    echo "Compilando pspdecrypt (GPLv3) somente neste diretorio local"
    if [[ ! -d "$WORK/pspdecrypt/.git" ]]; then
      git clone https://github.com/John-K/pspdecrypt.git "$WORK/pspdecrypt"
    fi
    make -C "$WORK/pspdecrypt" -j "$JOBS"
  fi
  rm -f "$ELF"
  if ! "$DECRYPTER" -o "$ELF" "$ENCRYPTED"; then
    rm -f "$ELF"
    echo "A ferramenta local nao conseguiu descriptografar este executavel." >&2
  fi
fi

if [[ "$(signature "$ELF" || true)" != "7f454c46" ]]; then
  rm -f "$ELF"
  cat >&2 <<'NOTICE'
NAO FOI POSSIVEL GERAR O ELF DESCRIPTOGRAFADO.

Alternativa: abra sua copia do jogo no PPSSPP, ative
Settings > Tools > Developer Tools > Dump decrypted EBOOT.BIN on game boot.
Depois localize o arquivo gerado no diretorio PSP/SYSTEM/DUMP do PPSSPP.
Copie o executavel descriptografado para:
  /mnt/user/appdata/pes6/.recomp-work/PES6.elf
Rode novamente: bash scripts/port-unraid.sh build
NOTICE
  exit 3
fi
echo "ELF valido: $(stat -c '%s bytes' "$ELF")"

echo "== [4/5] Configurando PSPRecomp / Emscripten"
"$UPSTREAM/scripts/setup.sh"

echo "== [4.1/5] Corrigindo descoberta de entrada AOT (PSPRecomp local)"
python3 "$PROJECT/scripts/patch-psp-extra-seeds.py" "$UPSTREAM/PSPRecomp"
# Rebuild the native psp_recomp binary so the next generate.sh actually
# consumes the changed analyzer (incremental Ninja on subsequent runs).
"$UPSTREAM/scripts/build_tools.sh"

echo "== [5/5] Recompilando PES6 para o navegador"
export JOBS
export PSPRECOMP_EXTRA_SEEDS="${PES6_EXTRA_SEEDS:-0x0897FD08}"
echo "== Force analysis seeds: $PSPRECOMP_EXTRA_SEEDS"
"$UPSTREAM/scripts/port.sh" pes6 "$ISO"

echo
echo "Build web gerado em: $UPSTREAM/build/web-pes6/profiles/web"
echo "Teste local: bash scripts/port-unraid.sh serve"
echo "NAO publique o ELF, o WASM gerado ou arquivos comerciais no GitHub."
