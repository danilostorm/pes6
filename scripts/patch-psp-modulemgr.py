#!/usr/bin/env python3
"""Apply a small, idempotent, source-verified PSP module-manager HLE fix.

Use only with the unmodified PSP Web Recomp upstream checkout. The patch never
changes the game ISO, ELF, assets, generated game code or public GitHub artifacts.
"""
from pathlib import Path
import sys


def replace_exact(src: str, old: str, new: str, where: Path) -> str:
    # A replacement can contain its original anchor. Test for the full
    # replacement first, otherwise consecutive builds duplicate declarations.
    if new in src:
        return src
    if old in src:
        if src.count(old) != 1:
            raise RuntimeError(f"Ambiguous anchor in {where}: {old[:90]!r}")
        return src.replace(old, new, 1)
    raise RuntimeError(
        f"Upstream version differs in {where}; patch NOT applied. "
        f"Expected anchor: {old[:100]!r}"
    )


def prepare(root: Path) -> None:
    header = root / "profile" / "host" / "kernel.hpp"
    source = root / "profile" / "host" / "kernel.cpp"
    if not header.is_file() or not source.is_file():
        raise RuntimeError(f"PSP Web Recomp sources missing inside: {root}")

    shell = root / "profile" / "web" / "shell.html"
    if not shell.is_file():
        raise RuntimeError(f"Browser shell not found: {shell}")
    h = header.read_text()
    c = source.read_text()
    web = shell.read_text()
    if "ENV.PSPRECOMP_TRACE_ON_ERROR = '1'" not in web:
        lines = [
            line for line in web.splitlines(keepends=True)
            if line.lstrip().startswith("preRun: [mountSaves]")
        ]
        if len(lines) != 1 or not lines[0].rstrip().endswith("),"):
            raise RuntimeError("Browser shell preRun changed; trace patch NOT applied")
        original = lines[0]
        replacement = original.rstrip("\\n")[:-1] + (
            ".concat(/[?&]trace=1(?:&|$)/.test(location.search) ? "
            "[function () { ENV.PSPWEB_TRACE_HLE = '1'; "
            "ENV.PSPRECOMP_TRACE_ON_ERROR = '1'; }] : []),\\n"
        )
        web = web.replace(original, replacement, 1)

    h = replace_exact(
        h,
        "    std::set<std::int32_t> modules_;\n",
        "    std::set<std::int32_t> modules_;\n"
        "    // UID -> (base, byte length) for loaded PSP guest modules.\n"
        "    std::map<std::int32_t, std::pair<std::uint32_t, std::uint32_t>> module_regions_;\n",
        header,
    )
    h = replace_exact(
        h,
        "    void sceKernelStartModule(Ctx &ctx);\n",
        "    void sceKernelStartModule(Ctx &ctx);\n"
        "    void sceKernelGetModuleIdByAddress(Ctx &ctx);\n",
        header,
    )

    c = replace_exact(
        c,
        '    hle(mm, 0x50F0C1ECu, "sceKernelStartModule", &Kernel::sceKernelStartModule);\n',
        '    hle(mm, 0x50F0C1ECu, "sceKernelStartModule", &Kernel::sceKernelStartModule);\n'
        '    hle(mm, 0xD8B73127u, "sceKernelGetModuleIdByAddress", &Kernel::sceKernelGetModuleIdByAddress);\n',
        source,
    )
    c = replace_exact(
        c,
        """void Kernel::reserve(std::uint32_t address, std::uint32_t size, std::string name) {
    blocks_[new_uid()] = MemoryBlock{std::move(name), address, align_up(size, 0x100u)};
}
""",
        """void Kernel::reserve(std::uint32_t address, std::uint32_t size, std::string name) {
    const std::uint32_t length = align_up(size, 0x100u);
    if (name.rfind("module:", 0) == 0) {
        // Distinct module UID, not a partition-memory block UID.
        const std::int32_t module_uid = new_uid();
        modules_.insert(module_uid);
        module_regions_[module_uid] = {address, length};
    }
    blocks_[new_uid()] = MemoryBlock{std::move(name), address, length};
}
""",
        source,
    )
    c = replace_exact(
        c,
        """void Kernel::sceKernelStartModule(Ctx &ctx) {
    if (ctx.gpr[7] != 0u) rt_.memory().store32(ctx.gpr[7], 0u);
    finish(ctx, ctx.gpr[4]);
}
""",
        """void Kernel::sceKernelStartModule(Ctx &ctx) {
    if (ctx.gpr[7] != 0u) rt_.memory().store32(ctx.gpr[7], 0u);
    finish(ctx, ctx.gpr[4]);
}

// ModuleMgrForUser NID D8B73127: find the UID of the guest module
// containing the supplied code/data address, or return a PSP UID error.
void Kernel::sceKernelGetModuleIdByAddress(Ctx &ctx) {
    const std::uint32_t address = ctx.gpr[4];
    for (const auto &[uid, region] : module_regions_) {
        if (address >= region.first && address - region.first < region.second) {
            finish(ctx, static_cast<std::uint32_t>(uid));
            return;
        }
    }
    finish(ctx, kErrorUnknownUid);
}
""",
        source,
    )

    # Both modifications must pass preflight before either file is written.
    if h != header.read_text():
        header.write_text(h)
    if c != source.read_text():
        source.write_text(c)
    if web != shell.read_text():
        shell.write_text(web)
    print("ModuleMgrForUser::sceKernelGetModuleIdByAddress: HLE installed (idempotent).")
    print("Browser guest tracing available with ?trace=1")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("Usage: python3 scripts/patch-psp-modulemgr.py /path/to/psp-web-recomp")
        prepare(Path(sys.argv[1]).resolve())
    except (OSError, RuntimeError) as exc:
        print(f"PATCH ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
