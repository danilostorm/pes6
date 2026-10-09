#!/usr/bin/env python3
"""Pure-Python unit tests for the PES6 local ELF block-recovery helpers."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recovery = load_script("recovery", "recover-psp-blocks.py")
validator = load_script("validator", "validate-aot-seeds.py")


def elf_fixture():
    raw = bytearray(256)
    raw[:6] = b"\x7fELF\x01\x01"
    struct.pack_into("<H", raw, 16, 2)
    struct.pack_into("<I", raw, 28, 52)
    struct.pack_into("<HH", raw, 42, 32, 1)
    struct.pack_into("<8I", raw, 52, 1, 128, 0x08804000, 0, 64, 64, 5, 4)
    struct.pack_into("<I", raw, 128, 0x08000008)  # j with delay slot
    struct.pack_into("<I", raw, 128 + 8, 0x8D030008)  # code after delay slot
    struct.pack_into("<I", raw, 128 + 16, 0x03E00008)  # jr ra
    struct.pack_into("<I", raw, 128 + 24, 0x8D020020)  # another code entry
    return bytes(raw)


class RecoveryUnitTests(unittest.TestCase):
    def test_recovers_post_jump_entries(self):
        elf = elf_fixture()
        segments = recovery.segments_from_elf(elf)
        candidates = recovery.decode_window(elf, segments, 0x08804000, 0x08804040)
        addrs = [pc for pc, _, _, _ in candidates]
        self.assertIn(0x08804008, addrs)
        self.assertIn(0x08804018, addrs)

    def test_seed_validator_checks_elf_and_alignment(self):
        with tempfile.TemporaryDirectory() as folder:
            elf_file = Path(folder) / "fake.elf"
            elf_file.write_bytes(elf_fixture())
            validator.check(elf_file, "0x08804008,0x08804018")
            with self.assertRaises(ValueError):
                validator.check(elf_file, "0x08804009")
            with self.assertRaises(ValueError):
                validator.check(elf_file, "0x0880400C")
            with self.assertRaises(ValueError):
                validator.check(elf_file, "0x08805000")


if __name__ == "__main__":
    unittest.main()
