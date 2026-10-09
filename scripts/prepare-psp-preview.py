#!/usr/bin/env python3
"""Prepare a PES6 PSP recomp preview for reliable post-build verification.

Never modifies the ISO, ELF, generated WASM or bundled game data. Only writes
a small public build-info.json next to the web build, and applies HTTP no-store
headers to the *local* upstream preview server script.
"""
import hashlib
import json
from pathlib import Path
import sys


def sha256_file(path: Path) -> str:
    hash_ = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hash_.update(block)
    return hash_.hexdigest()


def prepare(checkout: Path) -> None:
    output = checkout / "build/web-pes6/profiles/web"
    serve = checkout / "scripts/serve.py"
    wasm = output / "index.wasm"
    if not wasm.is_file() or not serve.is_file():
        raise RuntimeError("Web build/preview source missing; run the build first.")

    files = {}
    for name in ("index.html", "index.js", "index.wasm", "index.data"):
        path = output / name
        if path.is_file():
            files[name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    digest = files["index.wasm"]["sha256"]
    doc = {"name": "STOR PES6 PSP Web Recomp", "build_id": digest[:16], "files": files}
    info = output / "build-info.json"
    temp = output / "build-info.json.tmp"
    temp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(info)

    source = serve.read_text(encoding="utf-8")
    old = '        self.send_header("Cache-Control", "no-cache")'
    updated = (
        '        self.send_header("Cache-Control", "no-store, no-cache, max-age=0, must-revalidate")\n'
        '        self.send_header("Pragma", "no-cache")\n'
        '        self.send_header("Expires", "0")'
    )
    if updated not in source:
        if source.count(old) != 1:
            raise RuntimeError("Upstream serve.py changed; refusing to patch cache headers.")
        serve.write_text(source.replace(old, updated), encoding="utf-8")
        print("[preview] local HTTP no-store headers enabled")
    else:
        print("[preview] HTTP no-store headers already enabled")
    print(f"[preview] build_id={doc['build_id']} index.wasm_sha256={digest}")
    print("[preview] compare /build-info.json on 127.0.0.1:8613 and HTTPS domain")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("Usage: prepare-psp-preview.py <local psp-web-recomp checkout>")
        prepare(Path(sys.argv[1]))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"PREVIEW PREPARATION ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
