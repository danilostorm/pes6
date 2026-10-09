#!/usr/bin/env python3
"""Opt-in PSPRecomp analyzer seeds for locally owned game builds.

Patch the *local* PSPRecomp checkout, never the upstream GitHub repository.
The environment variable PSPRECOMP_EXTRA_SEEDS is deliberately unset for other
games. Entries are validated against ELF executable segments in the analyzer.

Usage: python3 scripts/patch-psp-extra-seeds.py /project/.recomp-work/psp-web-recomp/PSPRecomp
"""
from pathlib import Path
import sys


def patch(source_file: Path) -> None:
    original = source_file.read_text(encoding="utf-8")
    marker = 'const char *extra = std::getenv("PSPRECOMP_EXTRA_SEEDS")'
    if marker in original:
        print("PSPRecomp extra-seed patch: already applied")
        return

    anchor = '''    return seeds;
}

FunctionAnalysis analyze_function('''
    replacement = '''    // PES6 bring-up and other optional ports can supply *specific* targets
    // omitted by static CFG discovery. Disabled when no environment is set.
    // A seed is allowed only inside an executable ELF segment; no bytes are
    // modified and no arbitrary zero/NOP instruction is synthesized.
    if (const char *extra = std::getenv("PSPRECOMP_EXTRA_SEEDS")) {
        std::istringstream values(extra);
        std::string token;
        std::size_t requested = 0u;
        while (std::getline(values, token, ',')) {
            if (++requested > 32u) {
                std::cerr << "[analysis] refusing more than 32 extra entry seeds\\\\n";
                break;
            }
            char *end = nullptr;
            const unsigned long value = std::strtoul(token.c_str(), &end, 0);
            if (end == token.c_str() || *end != '\\\\0' ||
                value > std::numeric_limits<std::uint32_t>::max()) {
                std::cerr << "[analysis] invalid extra entry: " << token << "\\\\n";
                continue;
            }
            const auto pc = static_cast<std::uint32_t>(value);
            if (!is_executable_address(ranges, pc)) {
                std::cerr << "[analysis] non-executable extra entry: 0x"
                          << std::hex << pc << std::dec << "\\\\n";
                continue;
            }
            const bool inserted = seeds.try_emplace(pc, "manual_extra_seed").second;
            std::cerr << "[analysis] extra seed 0x" << std::hex << pc << std::dec
                      << (inserted ? " added" : " already discovered") << "\\\\n";
        }
    }
    return seeds;
}

FunctionAnalysis analyze_function('''

    if original.count(anchor) != 1:
        raise RuntimeError("PSPRecomp analyzer anchor changed. No patch applied.")

    patched = original.replace(anchor, replacement, 1)
    patched = patched.replace(
        "#include <algorithm>\n",
        "#include <algorithm>\n#include <cstdlib>\n#include <iostream>\n#include <sstream>\n",
        1,
    )
    # Use actual C++ escape sequences, not literal newline characters inside
    # string literals. The generated C++ must remain a valid translation unit.
    patched = patched.replace(r"\\n", r"\n").replace(r"\\0", r"\0")
    source_file.write_text(patched, encoding="utf-8")
    print("PSPRecomp extra-seed patch: applied")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("Usage: patch-psp-extra-seeds.py <PSPRecomp checkout>")
        source_file = Path(sys.argv[1]) / "src" / "program_analysis.cpp"
        if not source_file.is_file():
            raise RuntimeError(f"Cannot find local PSPRecomp analyzer: {source_file}")
        patch(source_file)
    except (RuntimeError, OSError) as exc:
        print(f"PATCH ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
