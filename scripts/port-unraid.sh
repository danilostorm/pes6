#!/usr/bin/env bash
# Compilacao local do PES6 PSP no Unraid, sem publicar arquivos comerciais.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${PES6_BUILDER_IMAGE:-storpes6-builder:local}"
MODE="${1:-build}"
PREVIEW_PORT="${PES6_PREVIEW_PORT:-8613}"
CONTAINER="pes6-recomp-preview"

fail() { echo "ERRO: $*" >&2; exit 1; }
command -v docker >/dev/null || fail "Docker nao encontrado."
[[ -d "$ROOT" ]] || fail "Projeto nao encontrado."

export BUILDX_CONFIG="${BUILDX_CONFIG:-$ROOT/.buildx}"
mkdir -p "$BUILDX_CONFIG" "$ROOT/.recomp-work"

build_image() {
  if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "== Montando ambiente Ubuntu isolado ($IMAGE)"
    docker build -f "$ROOT/tools/recomp/Dockerfile" -t "$IMAGE" "$ROOT/tools/recomp"
  fi
}
case "$MODE" in
  build)
    [[ -f "$ROOT/pes6.iso" ]] || fail "ISO ausente: $ROOT/pes6.iso"
    echo "== ISO: $(stat -c '%s bytes' "$ROOT/pes6.iso")"
    build_image
    docker run --rm --init \
      --name pes6-recomp-build \
      --mount "type=bind,source=$ROOT,target=/project" \
      -e "JOBS=${PES6_BUILD_JOBS:-4}" \
      -e "PES6_EXTRA_SEEDS=${PES6_EXTRA_SEEDS:-0x0897FD08,0x08986598}" \
      "$IMAGE" bash /project/scripts/port-unraid-inner.sh
    ;;
  diagnose)
    build_image
    docker run --rm --init \
      --mount "type=bind,source=$ROOT,target=/project,readonly" \
      "$IMAGE" python3 /project/scripts/diagnose-aot-entry.py \
      --root /project --address "${PES6_DIAG_PC:-0x08986598}"
    ;;
  serve)
    [[ -f "$ROOT/.recomp-work/psp-web-recomp/build/web-pes6/profiles/web/index.html" ]] ||
      fail "Build nao encontrado. Execute primeiro: bash scripts/port-unraid.sh build"
    build_image
    if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
      fail "O preview ja existe. Pare com: bash scripts/port-unraid.sh stop"
    fi
    trace_flags=()
    if [[ "${PES6_TRACE_HLE:-0}" == "1" ]]; then
      trace_flags+=(-e PSPWEB_TRACE_HLE=1)
    fi
    docker run -d --name "$CONTAINER" \
      -p "${PES6_PREVIEW_BIND:-0.0.0.0}:$PREVIEW_PORT:8613" \
      -e PSPRECOMP_TRACE_ON_ERROR=1 \
      "${trace_flags[@]}" \
      --mount "type=bind,source=$ROOT,target=/project" \
      "$IMAGE" bash -lc 'cd /project/.recomp-work/psp-web-recomp && \
        sed -i '\''s/("127.0.0.1", port)/("0.0.0.0", port)/'\'' scripts/serve.py && \
        exec scripts/serve.sh pes6 8613'
    echo "== Preview iniciado: http://IP_DO_UNRAID:$PREVIEW_PORT"
    ;;
  stop)
    docker rm -f "$CONTAINER" 2>/dev/null || true
    ;;
  *)
    fail "Uso: bash scripts/port-unraid.sh [build|diagnose|serve|stop]"
    ;;
esac
