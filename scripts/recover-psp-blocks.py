#!/usr/bin/env python3
"""Conservative PES6 orphan-entry recovery near confirmed missing AOT PCs.

Only scans an explicit small executable region of the user's decrypted ELF.
Looks for aligned, nonzero instructions immediately following unconditional
JR/J and their MIPS delay slots. This is a hypothesis for indirect entry
targets, NOT a general-purpose correct function-recovery algorithm.

Stdout: comma-separated seed list for PSPRECOMP_EXTRA_SEEDS.
Stderr: human-readable diagnosis; no game data uploaded.
"""
import argparse
import struct
import sys
from pathlib import Path

LOAD_BASE = 0x08804000


def segments_from_elf(raw):
    if raw[:6] != b"\x7fELF\x01\x01" or len(raw) < 52:
        raise ValueError("Expected decrypted little-endian ELF32")
    typ, = struct.unpack_from("<H", raw, 16)
    phoff, = struct.unpack_from("<I", raw, 28)
    entsize, count = struct.unpack_from("<HH", raw, 42)
    if typ not in (2, 0xFFA0) or entsize < 32 or count > 128:
        raise ValueError("Unexpected ELF type or corrupt program headers")
    entries = []
    for n in range(count):
        loc = phoff + n * entsize
        if loc + 32 > len(raw):
            raise ValueError("Truncated ELF program headers")
        kind, off, vaddr, _, sz, _, flags, _ = struct.unpack_from("<8I", raw, loc)
        if kind == 1 and flags & 1:
            addr = vaddr + LOAD_BASE if typ == 0xFFA0 else vaddr
            entries.append((addr, addr + sz, off))
    return entries


def decode_window(raw, segments, start, end):
    if start >= end or start & 3 or end & 3 or end - start > 0x1000:
        raise ValueError("Recovery window must be aligned and at most 4 KiB")
    def word_at(pc):
        for low, high, file_off in segments:
            if low <= pc and pc + 4 <= high:
                off = file_off + pc - low
                if off + 4 <= len(raw):
                    return struct.unpack_from("<I", raw, off)[0]
        return None

    candidates = []
    for pc in range(start, end, 4):
        opcode = word_at(pc)
        if opcode is None:
            continue
        # j immediate; jr register with rt=rd=shamt=0.
        direct_jump = opcode >> 26 == 2
        jump_reg = (opcode & 0xFC1FFFFF) == 0x00000008
        if not (direct_jump or jump_reg):
            continue
        candidate = pc + 8
        # The instruction at +4 is the delay slot; next block starts +8.
        if candidate >= end:
            continue
        insn = word_at(candidate)
        if insn is None or insn in (0, 0xFFFFFFFF):
            continue
        candidates.append((candidate, pc, "jr" if jump_reg else "j", insn))
    return candidates


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--elf", type=Path, required=True)
    p.add_argument("--seeds", required=True)
    p.add_argument("--range", dest="area", default="0x08986480:0x08986620")
    p.add_argument("--limit", type=int, default=16)
    args = p.parse_args()
    try:
        start_s, end_s = args.area.split(":", 1)
        start, end = int(start_s, 0), int(end_s, 0)
        raw = args.elf.read_bytes()
        spans = segments_from_elf(raw)
        original = [int(s.strip(), 0) for s in args.seeds.split(",") if s.strip()]
        if not original or len(original) > 32 or args.limit < 0:
            raise ValueError("Invalid seed list or maximum count")
        unique = list(dict.fromkeys(original))
        discovered = []
        for candidate, parent, kind, word in decode_window(raw, spans, start, end):
            if candidate not in unique:
                unique.append(candidate)
                discovered.append((candidate, parent, kind, word))
        if len(discovered) > args.limit or len(unique) > 32:
            raise ValueError(f"Recovery found {len(discovered)} extra PCs; limit {args.limit}, max total 32. Narrow the window or turn recovery off.")
        for pc, source, kind, word in discovered:
            print(f"[recover] seed 0x{pc:08X} follows {kind} at 0x{source:08X} (word 0x{word:08X})", file=sys.stderr)
        print(f"[recover] {len(discovered)} additional bounded, structurally plausible entries", file=sys.stderr)
        print(",".join(f"0x{pc:08X}" for pc in unique))
    except (OSError, ValueError, struct.error) as exc:
        print(f"RECOVERY FAILED: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
