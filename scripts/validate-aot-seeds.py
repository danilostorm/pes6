#!/usr/bin/env python3
"""Fail closed on invalid explicit PSPRecomp CFG seeds.

Reads a *local* decrypted ELF and the supplied PC list. Neither the ISO nor the
ELF is changed, and no game bytes are sent to GitHub.
"""
import argparse
from pathlib import Path
import struct
import sys


def check(elf_path: Path, addresses: str):
    raw = elf_path.read_bytes()
    if len(raw) < 52 or raw[:6] != b"\x7fELF\x01\x01":
        raise ValueError("Expected a decrypted little-endian ELF32")
    elf_type = struct.unpack_from("<H", raw, 16)[0]
    if elf_type not in (2, 0xFFA0):
        raise ValueError(f"Unexpected PSP ELF type: 0x{elf_type:X}")
    ph_offset = struct.unpack_from("<I", raw, 28)[0]
    ph_size, ph_count = struct.unpack_from("<HH", raw, 42)
    if ph_size < 32 or ph_count > 128:
        raise ValueError("Invalid ELF program header dimensions")
    sections = []
    for index in range(ph_count):
        pos = ph_offset + index * ph_size
        if pos + 32 > len(raw):
            raise ValueError("Truncated ELF program header")
        typ, off, vaddr, _, filesz, _, flags, _ = struct.unpack_from("<8I", raw, pos)
        if typ != 1 or not (flags & 1):
            continue
        addr = vaddr + 0x08804000 if elf_type == 0xFFA0 else vaddr
        sections.append((addr, addr + filesz, off))
    tokens = [v.strip() for v in addresses.split(",") if v.strip()]
    if not tokens or len(tokens) > 128:
        raise ValueError("Expected 1..128 comma-separated code addresses")
    seen = set()
    for token in tokens:
        pc = int(token, 0)
        if pc in seen:
            raise ValueError(f"Duplicate entry seed: {token}")
        seen.add(pc)
        if pc % 4:
            raise ValueError(f"Unaligned code address: 0x{pc:08X}")
        region = next((r for r in sections if r[0] <= pc and pc + 4 <= r[1]), None)
        if region is None:
            raise ValueError(f"Not inside file-backed executable PSP region: 0x{pc:08X}")
        offset = region[2] + pc - region[0]
        if offset + 4 > len(raw):
            raise ValueError(f"ELF truncated at: 0x{pc:08X}")
        word = struct.unpack_from("<I", raw, offset)[0]
        if word == 0:
            raise ValueError(f"NOP/zero instruction at 0x{pc:08X}; manual analysis required")
        print(f"[preflight] 0x{pc:08X}: MIPS word 0x{word:08X}; file-backed RX/aligned")
    print("[preflight] All requested AOT entry seeds passed conservative structural checks.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("elf", type=Path)
    parser.add_argument("addresses")
    options = parser.parse_args()
    try:
        check(options.elf, options.addresses)
    except (OSError, ValueError, OverflowError, struct.error) as exc:
        print(f"EXTRA SEED PRE-FLIGHT FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
