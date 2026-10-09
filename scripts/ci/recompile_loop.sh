#!/usr/bin/env bash
# Bounded automatic build -> Chromium smoke -> recompile on missing AOT.
# Never upload ISO/ELF/WASM. Diagnostics contain only text and PC addresses.
set -euo pipefail
cd /project
mkdir -p ci-reports
logfile="ci-reports/rounds.log"
: > "$logfile"
MAX_ROUNDS="$(printenv PES6_CI_MAX_ROUNDS || echo 5)"
[[ "$MAX_ROUNDS" =~ ^[1-9]$ ]] || { echo "MAX_ROUNDS must be 1..9" >&2; exit 2; }
seeds="$(printenv PES6_EXTRA_SEEDS || echo 0x0897FD08,0x08986598,0x089864DC,0x089864D0)"
export JOBS="$(printenv PES6_BUILD_JOBS || echo 2)"
export PES6_RECOVER_REGION="$(printenv PES6_RECOVER_REGION || echo 0x08986480:0x08986620)"
preview_pid=""

cleanup() {
  if [[ -n "$preview_pid" ]]; then
    kill "$preview_pid" 2>/dev/null || true
    wait "$preview_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

for ((round=1; round<=MAX_ROUNDS; round++)); do
  echo "=== PES6 automatic recompilation round $round / $MAX_ROUNDS ==="
  printf 'ROUND %s seeds=%s\n' "$round" "$seeds" >> "$logfile"
  export PES6_EXTRA_SEEDS="$seeds"
  bash scripts/port-unraid-inner.sh
  python3 scripts/prepare-psp-preview.py /project/.recomp-work/psp-web-recomp

  # Loopback is secure context; serve.py also supplies COOP/COEP.
  bash /project/.recomp-work/psp-web-recomp/scripts/serve.sh pes6 8613 >ci-reports/preview-server.log 2>&1 &
  preview_pid="$!"
  ready=0
  for ((t=0;t<80;t++)); do
    if curl -fsSI "http://127.0.0.1:8613/index.html" >/dev/null; then ready=1; break; fi
    if ! kill -0 "$preview_pid" 2>/dev/null; then break; fi
    sleep 2
  done
  if ((ready==0)); then
    echo "Preview did not start. See ci-reports/preview-server.log" >&2
    exit 4
  fi

  report="ci-reports/smoke-$round.json"
  python3 scripts/ci/smoke_browser.py --seconds 45 --output "$report"
  status="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$report")"
  pc="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("missing_pc") or "")' "$report")"
  printf 'RESULT round=%s status=%s pc=%s\n' "$round" "$status" "$pc" | tee -a "$logfile"

  cleanup
  preview_pid=""

  case "$status" in
    running_unverified)
      printf '\nResult: web guest did not halt during smoke. Menu/playability still needs visual validation.\n' | tee -a "$logfile"
      exit 0
      ;;
    missing_aot)
      if [[ ! "$pc" =~ ^0x[0-9A-Fa-f]{8}$ ]]; then
        echo "Invalid missing PC in browser report" >&2
        exit 6
      fi
      norm_pc="$(printf '%s' "$pc" | tr '[:lower:]' '[:upper:]')"
      norm_seeds="$(printf '%s' "$seeds" | tr '[:lower:]' '[:upper:]')"
      if [[ ",$norm_seeds," == *",$norm_pc,"* ]]; then
        echo "AOT PC already seeded: $pc. Investigate codegen/dispatch instead of repeating." | tee -a "$logfile" >&2
        exit 7
      fi
      if ((round==MAX_ROUNDS)); then
        echo "Automatic retry budget exhausted at $pc" >&2
        exit 8
      fi
      next="$seeds,$pc"
      python3 scripts/validate-aot-seeds.py \
        /project/.recomp-work/psp-web-recomp/games/pes6/root/EBOOT.BIN "$next"
      seeds="$next"
      echo "New validated AOT entry: $pc; scheduling next local build" | tee -a "$logfile"
      ;;
    guest_halted|infrastructure_error)
      echo "Non-AOT failure cannot be repaired automatically. Inspect smoke JSON." | tee -a "$logfile" >&2
      exit 9
      ;;
    *)
      echo "Unexpected smoke status: $status" >&2
      exit 10
      ;;
  esac
done
