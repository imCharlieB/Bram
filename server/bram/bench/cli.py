"""bram-bench: measure one model."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from ..models.base import ModelError, ModelProvider
from ..models.ollama import OllamaProvider
from .cases import CASES, Case


async def run(provider: ModelProvider, cases: list[Case], repeat: int = 3) -> list[dict]:
    results = []
    for case in cases:
        for attempt in range(repeat):
            row = {"case": case.name, "group": case.group, "attempt": attempt + 1}
            start = time.perf_counter()
            try:
                reply = await provider.chat(case.messages, case.tools, case.schema)
            except ModelError as err:
                row |= {"passed": False, "error": str(err)}
            else:
                row |= {"passed": case.check(reply) and not reply.truncated,
                        "text": reply.text[:300], "truncated": reply.truncated,
                        "tool_calls": [[c.name, c.arguments] for c in reply.tool_calls],
                        "prompt_tokens": reply.prompt_tokens, "output_tokens": reply.output_tokens,
                        "prompt_seconds": reply.prompt_seconds,
                        "output_seconds": reply.output_seconds}
            row["seconds"] = round(time.perf_counter() - start, 2)
            results.append(row)
    return results


def summarize(results: list[dict]) -> dict:
    groups: dict[str, list[int]] = {}
    for row in results:
        score = groups.setdefault(row["group"], [0, 0])
        score[0] += row["passed"]
        score[1] += 1

    def rate(tokens: str, seconds: str) -> float | None:
        rows = [r for r in results if r.get(tokens) and r.get(seconds)]
        total = sum(r[seconds] for r in rows)
        return round(sum(r[tokens] for r in rows) / total, 1) if total else None

    times = sorted(r["seconds"] for r in results)
    return {"groups": {k: f"{p}/{n}" for k, (p, n) in groups.items()},
            "median_seconds": times[len(times) // 2] if times else None,
            "slowest_seconds": times[-1] if times else None,
            "prompt_tokens_per_second": rate("prompt_tokens", "prompt_seconds"),
            "output_tokens_per_second": rate("output_tokens", "output_seconds")}


async def _main(args: argparse.Namespace) -> int:
    think = {"on": True, "off": False, "default": None}[args.think]
    provider = OllamaProvider(args.url, args.model or "", context=args.context,
                              timeout=args.timeout, think=think,
                              keep_alive=-1 if args.keep_loaded else "30m")
    try:
        if not args.model:
            print("Installed models:", *await provider.installed(), sep="\n  ")
            return 0
        identity = await provider.identity()
        details = await provider.details()
        info = {"identity": identity, "ollama": await provider.version(),
                "capabilities": details.get("capabilities"), "details": details.get("details"),
                "context": args.context, "think": args.think}
        print(json.dumps(info, indent=2))
        results = await run(provider, CASES, args.repeat)
        info["loaded"] = [{k: m.get(k) for k in ("name", "size", "size_vram", "context_length")}
                          for m in await provider.loaded()]
    except ModelError as err:
        print(f"Benchmark failed: {err}", file=sys.stderr)
        return 2
    finally:
        await provider.close()
    for row in results:
        if not row["passed"]:
            print("FAIL", row["case"], row.get("error") or row["tool_calls"] or repr(row["text"]))
    summary = summarize(results)
    print(json.dumps({"summary": summary, "loaded": info["loaded"]}, indent=2))
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"info": info, "summary": summary, "results": results},  # noqa: ASYNC240
                                   indent=2), encoding="utf-8")
    return 0 if all(r["passed"] for r in results) else 1


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True)
    p.add_argument("--model", help="omit to list installed models")
    p.add_argument("--context", type=int, default=8192)
    p.add_argument("--timeout", type=float, default=180)
    p.add_argument("--repeat", type=int, default=3)
    p.add_argument("--think", choices=["on", "off", "default"], default="default")
    p.add_argument("--keep-loaded", action="store_true",
                   help="never unload; use with a matching --context on a shared server")
    p.add_argument("--out")
    sys.exit(asyncio.run(_main(p.parse_args())))


if __name__ == "__main__":
    main()
