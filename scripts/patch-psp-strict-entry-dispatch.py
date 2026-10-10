#!/usr/bin/env python3
"""Guard PSPRecomp generated-unit dispatch with exact registered entry lookup.

The upstream optimized runtime selects a generated 16KiB unit based on a
guest PC's bucket, even when that particular PC was not registered as an
entry. The generated C++ dispatcher then halts with "invalid internal
function entry" instead of letting the caller discover a missing entry.

This local bring-up patch disables that unsafe assumption for three
unit-selection paths. It intentionally trades some performance for
deterministic, diagnosable, exact entry-PC dispatch. Existing import / HLE
overrides still use their exact registered handlers.

No game data, guest binary, or generated content is changed.
"""
from pathlib import Path
import sys

GUARD = "// PES6_STRICT_AOT_ENTRY_GUARD"

def patch(checkout: Path) -> None:
    source_path = checkout / "src" / "runtime.cpp"
    source = source_path.read_text(encoding="utf-8")
    if GUARD in source:
        print("PSPRecomp strict generated-unit entry guard already applied")
        return

    replacement_pairs = [
        (
            '''Runtime::RecompiledFunction Runtime::lookup_generated_unit(std::uint32_t address) const noexcept {
    if (!generated_unit_layout_valid_ || generated_unit_span_ == 0u) return nullptr;''',
            '''Runtime::RecompiledFunction Runtime::lookup_generated_unit(std::uint32_t address) const noexcept {
    // PES6_STRICT_AOT_ENTRY_GUARD: do not call a unit without a valid PC entry.
    if (lookup_function(address) == nullptr) return nullptr;
    if (!generated_unit_layout_valid_ || generated_unit_span_ == 0u) return nullptr;''',
        ),
        (
            '''    if (function == nullptr) {
        const std::uint32_t delta = memory_.canonical(ctx.pc) - direct_base_;
        if ((delta & 3u) != 0u) return false;''',
            '''    // PES6_STRICT_AOT_ENTRY_GUARD: a unit can cover a 16 KiB window
    // without having a generated label at the particular target PC.
    if (function != nullptr && lookup_function(ctx.pc) == nullptr) {
        function = nullptr;
        entry_function = nullptr;
    }
    if (function == nullptr) {
        const std::uint32_t delta = memory_.canonical(ctx.pc) - direct_base_;
        if ((delta & 3u) != 0u) return false;''',
        ),
        (
            '''bool Runtime::invoke_chained_unit(AllegrexContext &ctx, std::uint32_t unit_index,
                                  GuestMemory::AotFastView *shared_aot_mem) {
#if !defined(PSPRECOMP_AOT_PRODUCTION_FASTPATHS)''',
            '''bool Runtime::invoke_chained_unit(AllegrexContext &ctx, std::uint32_t unit_index,
                                  GuestMemory::AotFastView *shared_aot_mem) {
    // PES6_STRICT_AOT_ENTRY_GUARD: reject unit-bucket false positives.
    if (lookup_function(ctx.pc) == nullptr) return false;
#if !defined(PSPRECOMP_AOT_PRODUCTION_FASTPATHS)''',
        ),
    ]
    for old, _ in replacement_pairs:
        if source.count(old) != 1:
            raise ValueError("PSPRecomp runtime structure changed; exact anchor missing, refusing patch")
    for old, new in replacement_pairs:
        source = source.replace(old, new, 1)
    source_path.write_text(source, encoding="utf-8")
    print("PSPRecomp strict generated-unit entry guard applied to 3 runtime paths")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("Usage: patch-psp-strict-entry-dispatch.py <local PSPRecomp checkout>")
        patch(Path(sys.argv[1]))
    except (OSError, ValueError) as exc:
        print(f"RUNTIME PATCH ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
