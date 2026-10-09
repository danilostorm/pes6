#!/usr/bin/env python3
"""Diagnose a PSPRecomp missing AOT dispatch PC without modifying game binaries.

Reads the locally decrypted ELF and generated C++ source. Prints only metadata,
address ranges, instruction words and registry info; does not upload assets.
"""
import argparse
import json
from pathlib import Path
import re
import struct
import sys

LOAD_BASE = 0x08804000


def elf_segments(data):
    if data[:4] != b"\x7fELF" or data[4:6] != b"\x01\x01":
        raise ValueError("Expected little-endian ELF32 (decrypted PSP executable)")
    kind = struct.unpack_from("<H", data, 16)[0]
    phoff = struct.unpack_from("<I", data, 28)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 42)
    if phentsize < 32 or phnum > 128:
        raise ValueError("Invalid program headers")
    segments = []
    for i in range(phnum):
        off = phoff + i * phentsize
        if off + 32 > len(data):
            raise ValueError("Truncated program headers")
        typ, pos, vaddr, _, size, memsz, flags, _ = struct.unpack_from("<8I", data, off)
        if typ != 1:
            continue
        base = (LOAD_BASE + vaddr) if kind == 0xFFA0 else vaddr
        segments.append((base, base + size, base + memsz, pos, flags))
    return kind, segments


def source_name(root, addr, segments):
    parent = root / ".recomp-work/psp-web-recomp"
    directory = parent / "PSPRecomp/profiles/web/generated/pes6"
    if not directory.is_dir():
        directory = parent / "profile/generated/pes6"
    report_file = directory / "auto_codegen_report.json"
    try:
        span = int(json.loads(report_file.read_text())["unit_span_bytes"])
    except (OSError, KeyError, ValueError, TypeError):
        span = 0x4000
    rx_bases = sorted(begin for begin, _, _, _, flags in segments if flags & 1)
    if not rx_bases or addr < rx_bases[0] or span <= 0:
        return directory, None, span
    bucket = (addr - rx_bases[0]) // span
    return directory, directory / f"generated_unit_{bucket:04d}.cpp", span


def inspect(root, addr):
    elf = root / ".recomp-work/psp-web-recomp/games/pes6/root/EBOOT.BIN"
    if not elf.is_file():
        raise FileNotFoundError(f"Decrypted local ELF not found: {elf}")
    data = elf.read_bytes()
    kind, segments = elf_segments(data)
    print(f"ELF: {elf} ({len(data)} bytes, type=0x{kind:04X})")
    print(f"Missing dispatch: 0x{addr:08X}")
    for begin, end, mem_end, _, flags in segments:
        print(f"  PT_LOAD 0x{begin:08X}-0x{end:08X} (memory end 0x{mem_end:08X}), flags={flags:03b}")
    matches = [(b, e, fileoff, flags) for b, e, _, fileoff, flags in segments if b <= addr < e]
    if not matches:
        print("RESULT: target is outside ALL file-backed ELF PT_LOAD segments.")
        print("Do NOT add a forced function seed; investigate a corrupted/indirect target.")
        return
    begin, end, fileoff, flags = matches[0]
    if not flags & 1 or addr % 4:
        print("RESULT: target is not in an aligned executable segment. Do NOT force a seed.")
        return
    print("RESULT: target is aligned and lies in a file-backed executable segment.")
    print("Nearby little-endian Allegrex/MIPS words:")
    for pc in range(max(begin, addr-48), min(end, addr+52), 4):
        offset = fileoff + pc - begin
        if offset + 4 > len(data):
            continue
        word = struct.unpack_from("<I", data, offset)[0]
        description = ""
        if word == 0:
            description = "nop (0)"
        elif word == 0x03E00008:
            description = "jr ra"
        elif word & 0xFFFF0000 == 0x27BD0000:
            description = f"addiu sp, sp, {struct.unpack('<h', struct.pack('<H',word&65535))[0]}"
        elif (word >> 26) in (2, 3):
            target = ((pc+4) & 0xF0000000) | ((word & 0x3FFFFFF) << 2)
            description = f"{'jal' if word>>26==3 else 'j'} 0x{target:08X}"
        print(f"  {'>>' if pc==addr else '  '} 0x{pc:08X}: 0x{word:08X}  {description}")
    if fileoff + addr-begin + 4 <= len(data):
        instruction = struct.unpack_from("<I", data, fileoff+addr-begin)[0]
        if instruction == 0:
            print("WARNING: target instruction is NOP; examine surrounding code before adding a seed.")

    directory, cpp, span = source_name(root, addr, segments)
    print(f"Generated source: {directory} (unit span 0x{span:X})")
    if cpp is None or not cpp.is_file():
        print(f"Bucket C++ source not found: {cpp}. The compiler may have skipped this region.")
        return
    print(f"Target bucket: {cpp.name} ({cpp.stat().st_size} bytes)")
    source = cpp.read_text(errors="replace")
    pc_text = f"{addr:08X}"
    label = f"L_{pc_text}"
    registration = f"runtime.register_function(0x{pc_text}u"
    print(f"Instruction label {label}: {'YES' if label in source else 'NO'}")
    print(f"Exact dispatcher registration: {'YES' if registration in source else 'NO'}")
    entries = [
        int(x, 16) for x in re.findall(
            r"runtime\.register_function\(0x([0-9A-Fa-f]{8})u", source)
    ]
    if entries:
        nearest = sorted(entries, key=lambda value: abs(value-addr))[:8]
        print("Nearest registered entry PCs: " + ", ".join(f"0x{x:08X}" for x in nearest))
    print("Classification:")
    if label in source and registration not in source:
        print("  Code was emitted but PC was not registered as an entry: CFG/indirect dispatch gap.")
    elif not label in source:
        print("  PC was not emitted as a code label: missing analysis/CFG coverage is possible.")
    else:
        print("  PC IS registered in source; check build freshness/registry and runtime mapping.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--address", type=lambda s: int(s, 0), default=0x0897FD08)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    try:
        inspect(args.root.resolve(), args.address)
    except (OSError, ValueError, struct.error) as exc:
        print(f"Diagnosis failed: {exc}", file=sys.stderr)
        sys.exit(1)
