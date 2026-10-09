#!/usr/bin/env python3
"""Headless smoke of the *locally built* PES6 WASM; never exports game binaries.

This is a boot/crash check, not a claim of end-to-end gameplay compatibility.
Writes only bounded diagnostic messages and an optional report JSON.
"""
import argparse
import asyncio
import json
from pathlib import Path
import re
import time
from playwright.async_api import async_playwright

PC_RE = re.compile(r"No recompiled function registered at (0x[0-9A-Fa-f]{8})")
ERROR_RE = re.compile(r"\[(?:kernel|pspweb)\] (?:halted|guest stopped)")
SENSITIVE_URL = re.compile(r"https?://\S+")


async def run(url, seconds):
    result = {
        "status": "infrastructure_error", "reason": "",
        "missing_pc": None, "guest_started": False, "frames_observed": None,
        "console_tail": [], "page_errors": [], "elapsed_seconds": None,
    }
    started = time.monotonic()
    messages = []
    errors = []
    try:
        async with async_playwright() as ap:
            browser = await ap.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", "--disable-dev-shm-usage", "--enable-webgl",
                    "--use-gl=angle", "--use-angle=swiftshader",
                    "--enable-unsafe-swiftshader", "--disable-gpu-sandbox",
                    "--disable-background-timer-throttling",
                ],
            )
            context = await browser.new_context(viewport={"width": 1280, "height": 900})
            page = await context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)[:300]))
            # Only WebAssembly guest logs, not external file responses or binary bytes.
            page.on("console", lambda msg: messages.append(msg.text[:400]) if
                    any(tag in msg.text for tag in ("[kernel]", "[pspweb]", "[missing-aot]", "[guest]")) else None)
            await page.goto(url + "/?trace=1&threads=0", wait_until="domcontentloaded", timeout=120000)
            deadline = time.monotonic() + seconds
            log = ""
            status = ""
            while time.monotonic() < deadline:
                await asyncio.sleep(1)
                try:
                    state = await page.evaluate("""() => ({
                        log: document.querySelector('#log')?.textContent || '',
                        status: document.querySelector('#status')?.textContent || '',
                        isolated: window.crossOriginIsolated,
                        secure: window.isSecureContext
                    })""")
                except Exception as exc:
                    result["reason"] = "Browser execution unavailable: " + str(exc)[:250]
                    break
                log, status = state["log"], state["status"]
                result["guest_started"] = "[pspweb] module " in log
                if not state["isolated"] or not state["secure"]:
                    result["reason"] = "Browser not in secure, cross-origin-isolated context"
                    break
                if "Stopped:" in status or "[kernel] halted:" in log:
                    break
            result["console_tail"] = [
                SENSITIVE_URL.sub("[URL]", line)[:300]
                for line in log.splitlines()[-55:]
                if any(token in line for token in ("[hle]", "[pspweb]", "[guest]", "[kernel]", "[missing-aot]", "[webfs]"))
            ]
            result["page_errors"] = errors[-6:]
            found = PC_RE.search(log)
            if found:
                result["status"] = "missing_aot"
                result["missing_pc"] = found.group(1).upper().replace("0X", "0x")
                result["reason"] = f"Missing compiled guest entry: {result['missing_pc']}"
            elif "Stopped:" in status or ERROR_RE.search(log):
                result["status"] = "guest_halted"
                result["reason"] = status[:300] or "Guest halted"
            elif result["reason"]:
                result["status"] = "infrastructure_error"
            elif result["guest_started"] and status.strip().lower() == "running":
                result["status"] = "running_unverified"
                result["reason"] = "Guest did not stop during smoke window; rendering/menu playability NOT verified"
            else:
                result["status"] = "infrastructure_error"
                result["reason"] = f"Guest did not reach Running in {seconds}s; UI status: {status[:120]}"
            await context.close()
            await browser.close()
    except Exception as exc:
        result["status"] = "infrastructure_error"
        result["reason"] = type(exc).__name__ + ": " + str(exc)[:450]
    result["elapsed_seconds"] = round(time.monotonic() - started, 1)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8613")
    parser.add_argument("--seconds", type=int, default=40)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.seconds < 10 or args.seconds > 180:
        parser.error("Smoke window must be 10-180 seconds")
    result = asyncio.run(run(args.url.rstrip("/"), args.seconds))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "console_tail"}, indent=2))


if __name__ == "__main__":
    main()
