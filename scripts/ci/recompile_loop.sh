#!/usr/bin/env bash
# Bounded automatic build -> Chromium smoke -> recompile on missing AOT.
# Never upload ISO/ELF/WASM. Diagnostics contain only text and PC addresses.
set -euo pipefail
cd /project
mkdir -p ci-reports
logfile="ci-reports/rounds.log"
: > "$logfile"
# More than five short attempts: work for up to two hours or 80 boots.
# A hard wall-clock budget keeps Actions costs bounded even if a tool hangs.
MAX_ROUNDS="${PES6_CI_MAX_ROUNDS:-80}"
MAX_MINUTES="${PES6_CI_MAX_MINUTES:-120}"
MAX_SEEDS=128
[[ "$MAX_ROUNDS" =~ ^[1-9][0-9]?$|^100$ ]] && (( MAX_ROUNDS <= 100 )) ||
  { echo "PES6_CI_MAX_ROUNDS must be 1..100" >&2; exit 2; }
[[ "$MAX_MINUTES" =~ ^[1-9][0-9]?$|^1[0-7][0-9]$|^180$ ]] ||
  { echo "PES6_CI_MAX_MINUTES must be 1..180" >&2; exit 2; }
started_at="$(date +%s)"

# Carry verified AOT PCs forward across GitHub workflow executions using only
# a small text cache; the runner never caches ISO, ELF, game data, or WebAssembly.
mkdir -p .ci-state
seed_file=".ci-state/known-seeds.txt"
seeds="${PES6_EXTRA_SEEDS:-0x0897FD08,0x08986598,0x089864DC,0x089864D0,0x08984284,0x08984DEC,0x088C4330,0x088BE928,0x088BE534,0x088C160C,0x0880D7AC,0x0880D7CC}"
declare -A known=()
distinct=()
add_unique_seed() {
  local pc="$1"
  [[ "$pc" =~ ^0[xX][0-9A-Fa-f]{8}$ ]] || { echo "Invalid cached seed: $pc" >&2; return 2; }
  pc="0x${pc:2}"
  pc="${pc^^}"
  if [[ -z "${known[$pc]+yes}" ]]; then
    known[$pc]=1
    distinct+=("$pc")
  fi
}
IFS=, read -ra base_list <<< "$seeds"
for pc in "${base_list[@]}"; do add_unique_seed "$pc"; done
if [[ -s "$seed_file" ]]; then
  IFS=, read -ra saved_list < "$seed_file"
  for pc in "${saved_list[@]}"; do add_unique_seed "$pc"; done
  echo "== Restored ${#saved_list[@]} saved AOT addresses from diagnostic cache."
fi
(( ${#distinct[@]} <= MAX_SEEDS )) || { echo "Too many cached AOT seeds" >&2; exit 2; }
seeds="$(IFS=,; echo "${distinct[*]}")"
printf '%s\n' "$seeds" > "$seed_file"
export JOBS="${PES6_BUILD_JOBS:-2}"
export PES6_RECOVER_REGION="${PES6_RECOVER_REGION:-0x08986480:0x08986620}"
export PES6_CI_MODE=1
preview_pid=""

cleanup() {
  if [[ -n "$preview_pid" ]]; then
    kill "$preview_pid" 2>/dev/null || true
    wait "$preview_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

for ((round=1; round<=MAX_ROUNDS; round++)); do
  elapsed="$(( $(date +%s) - started_at ))"
  if (( elapsed >= MAX_MINUTES * 60 )); then
    echo "Elapsed time budget of $MAX_MINUTES minutes exhausted after $((round - 1)) rounds." | tee -a "$logfile" >&2
    exit 11
  fi
  echo "=== PES6 automatic recompilation round $round / $MAX_ROUNDS; elapsed $((elapsed / 60))m / ${MAX_MINUTES}m ==="
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
      # If the address is already in the generated AOT set, more seeding
      # cannot fix a runtime dispatch/codegen mismatch. Stop and diagnose.
      if [[ -s .ci-state/last-build-seeds.txt ]]; then
        compiled="$(tr '[:lower:]' '[:upper:]' < .ci-state/last-build-seeds.txt)"
        if [[ ",$compiled," == *",$norm_pc,"* ]]; then
          echo "Missing PC $pc was ALREADY requested in compiled AOT entries; investigate codegen/runtime. Aborting futile retries." | tee -a "$logfile" >&2
          exit 12
        fi
      fi
      if ((round == MAX_ROUNDS)); then
        echo "Automatic retry budget exhausted at $pc" | tee -a "$logfile" >&2
        exit 8
      fi
      if (( ${#distinct[@]} >= MAX_SEEDS )); then
        echo "Max $MAX_SEEDS validated PCs reached. Investigate systematic CFG discovery instead of relaxing further." | tee -a "$logfile" >&2
        exit 13
      fi
      next="$seeds,$pc"
      python3 scripts/validate-aot-seeds.py \
        /project/.recomp-work/psp-web-recomp/games/pes6/root/EBOOT.BIN "$next"
      add_unique_seed "$pc"
      seeds="$next"
      # Persist only address strings. The cache/save step runs even if this
      # workflow fails later; the next push resumes after these PCs.
      printf '%s\n' "$seeds" > "$seed_file"
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
