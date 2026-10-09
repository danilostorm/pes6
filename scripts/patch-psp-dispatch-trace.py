#!/usr/bin/env python3
"""Print last guest dispatch PCs when PSPRecomp halts on a missing AOT entry.

Patches the local PSPRecomp checkout only; keeps normal fast path unchanged.
The extra output is opt-in (?trace=1 sets PSPRECOMP_TRACE_ON_ERROR).
"""
from pathlib import Path
import sys

OLD = '''        const FunctionEntry *function_entry = lookup_entry(before);
        if (function == nullptr) {
            stop("No recompiled function registered at " + hex32(before));
            break;
        }
        g_runtime_dispatch_pc = before;'''

NEW = '''        const FunctionEntry *function_entry = lookup_entry(before);
        if (function == nullptr) {
            if (trace_on_error) {
                std::cerr << "[missing-aot] pc=" << hex32(before)
                          << " ra=" << hex32(cpu_.gpr[31])
                          << " sp=" << hex32(cpu_.gpr[29]);
                if (memory_.contains(before, 4u))
                    std::cerr << " word=" << hex32(memory_.load32(before));
                std::cerr << "\\n";
                const std::size_t count = std::min(recent_count, std::size_t{24});
                const std::size_t first =
                    (recent_next + recent_dispatches.size() - count) % recent_dispatches.size();
                for (std::size_t n = 0; n < count; ++n) {
                    const auto &history = recent_dispatches[(first + n) % recent_dispatches.size()];
                    std::cerr << "[missing-aot-previous] uid=" << history.thread_uid
                              << " name=" << history.thread_name.data()
                              << " pc=" << hex32(history.pc)
                              << " ra=" << hex32(history.ra)
                              << " sp=" << hex32(history.sp)
                              << " a0=" << hex32(history.a0)
                              << " a1=" << hex32(history.a1) << "\\n";
                }
            }
            stop("No recompiled function registered at " + hex32(before));
            break;
        }
        g_runtime_dispatch_pc = before;'''


def patch(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if "[missing-aot-previous]" in source:
        print("PSPRecomp missing-AOT trace patch already applied")
        return
    if source.count(OLD) != 1:
        raise RuntimeError("Runtime diagnostic dispatch anchor has changed; refusing to modify it")
    # Keep C++ newline escaping intact.
    replacement = NEW.replace(r"\\n", r"\n")
    path.write_text(source.replace(OLD, replacement, 1), encoding="utf-8")
    print("PSPRecomp missing-AOT trace patch applied (enable with browser ?trace=1)")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("Usage: patch-psp-dispatch-trace.py <PSPRecomp checkout>")
        file = Path(sys.argv[1]) / "src" / "runtime.cpp"
        if not file.is_file():
            raise RuntimeError(f"Local PSPRecomp runtime not found: {file}")
        patch(file)
    except (OSError, RuntimeError) as exc:
        print(f"PATCH ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
