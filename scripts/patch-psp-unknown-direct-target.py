#!/usr/bin/env python3
"""Safely patch local PSPRecomp AOT codegen: missing direct-entry fallback.

The direct-unit-chain fast path calls a compiled native unit with DirectEntryId
zero when a compile-time target is NOT in the global entry table. In that case
the original code does NOT store the target into ctx.pc before invocation;
the guest unit may observe the previous PC and halt as "invalid internal
function entry" (even when its target is valid).

When no known direct entry id exists, route via the runtime exact per-PC
dispatcher instead. It can either invoke an exact registered entry or return
false so the outer dispatcher reports the actual missing AOT PC. Existing
known direct entries retain their fast path. Local checkout only.
"""
from pathlib import Path
import sys


OLD = '''    return "rt.invoke_chained_direct<&" + generated_unit_cpp_name(unit) + ", " +
        std::to_string(unit) + "u>(ctx, &aot_mem)";
}'''

NEW = '''    // Unknown direct entry: the specialized unit call would not set ctx.pc
    // to target because it has no DirectEntryId. That can dispatch the stale
    // caller PC into an unrelated generated unit. Use exact PC lookup, which
    // preserves the real target and correctly reports absent AOT coverage.
    return "(ctx.pc = " + psprecomp::hex32(target) +
        "u, rt.invoke_chained_call(ctx, &aot_mem))";
}'''


def patch(checkout: Path):
    source_file = checkout / "tools" / "codegen_main.cpp"
    source = source_file.read_text(encoding="utf-8")
    if source.count(NEW) == 1:
        print("PSPRecomp codegen unknown-target handoff: already patched")
        return
    if source.count(OLD) != 1:
        raise ValueError("PSPRecomp codegen direct-chain anchor changed; refusing to patch")
    source_file.write_text(source.replace(OLD, NEW, 1), encoding="utf-8")
    print("PSPRecomp codegen unknown-target handoff: patched local checkout")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("Usage: patch-psp-unknown-direct-target.py <PSPRecomp checkout>")
        patch(Path(sys.argv[1]))
    except (OSError, ValueError) as exc:
        print(f"CODEGEN PATCH ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
