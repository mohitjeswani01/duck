"""Benchmarks the same realistic Duck request against candidate Gemini
models, to inform which should be GEMINI_MODEL (primary) vs
GEMINI_FALLBACK_MODEL. Sends one real Duck-shaped request — the actual
system prompt, the full 7-tool schema, one sample bug description, no
conversation history — 3 times to each model, at the same LOW thinking level
the investigating phase actually uses in production, and reports average and
slowest latency, any errors, and whether the first tool call chosen looks
like a sensible start for the bug described (vs. guessing, or not
investigating at all).

9 Gemini calls total (3 models x 3 runs) — well under a 20-call budget.

Usage (from backend/, venv active):
    python scripts/benchmark_models.py
"""
import asyncio
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.genai import types  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services.gemini_key_pool import get_gemini_key_pool  # noqa: E402
from app.services.system_prompt import build_system_prompt  # noqa: E402
from app.services.tool_declarations import ALL_TOOLS  # noqa: E402

MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash"]
RUNS_PER_MODEL = 3

SAMPLE_BUG = (
    "I log in and then like fifteen seconds later I'm back at the login screen. "
    "It's supposed to keep me logged in for an hour, I didn't even get to look at anything."
)

_RELEVANT_KEYWORDS = ("auth", "session", "token", "login", "expir")


def _is_sensible_first_call(name: str, args: dict) -> bool:
    if name == "list_files":
        return True
    if name in ("read_file", "search_code"):
        haystack = " ".join(str(v) for v in args.values()).lower()
        return any(kw in haystack for kw in _RELEVANT_KEYWORDS)
    return False


@dataclass
class RunResult:
    latency: float | None
    error: str | None
    first_call: str | None
    sensible: bool


@dataclass
class ModelReport:
    model: str
    runs: list = field(default_factory=list)

    @property
    def successes(self) -> list:
        return [r for r in self.runs if r.error is None]

    @property
    def avg_latency(self) -> float | None:
        lat = [r.latency for r in self.successes if r.latency is not None]
        return statistics.mean(lat) if lat else None

    @property
    def slowest(self) -> float | None:
        lat = [r.latency for r in self.successes if r.latency is not None]
        return max(lat) if lat else None

    @property
    def sensible_count(self) -> int:
        return sum(1 for r in self.successes if r.sensible)


async def run_once(pool, model: str, system_instruction: str, settings) -> RunResult:
    contents = [types.Content(role="user", parts=[types.Part.from_text(text=SAMPLE_BUG)])]
    config = types.GenerateContentConfig(
        tools=[ALL_TOOLS],
        system_instruction=system_instruction,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel[settings.gemini_thinking_level]),
    )

    async def op(client):
        return await client.aio.models.generate_content(model=model, contents=contents, config=config)

    start = time.monotonic()
    try:
        response = await asyncio.wait_for(pool.execute(op, model=model), timeout=settings.gemini_call_timeout_seconds + 60)
        latency = time.monotonic() - start
    except Exception as exc:  # noqa: BLE001 — benchmark: record every failure mode, don't crash the run
        return RunResult(latency=None, error=f"{type(exc).__name__}: {exc}", first_call=None, sensible=False)

    calls = response.function_calls or []
    if not calls:
        text = (response.text or "")[:80]
        return RunResult(latency=latency, error=None, first_call=f"(no tool call — text: {text!r})", sensible=False)

    first = calls[0]
    sensible = _is_sensible_first_call(first.name, first.args or {})
    return RunResult(latency=latency, error=None, first_call=f"{first.name}({first.args})", sensible=sensible)


async def main() -> None:
    settings = get_settings()
    pool = get_gemini_key_pool()
    system_instruction = build_system_prompt("mohitjeswani01", "taskboard")

    reports: list[ModelReport] = []
    for model in MODELS:
        report = ModelReport(model=model)
        print(f"\n=== {model} ===")
        for i in range(RUNS_PER_MODEL):
            result = await run_once(pool, model, system_instruction, settings)
            report.runs.append(result)
            if result.error:
                print(f"  run {i + 1}: ERROR {result.error}")
            else:
                mark = "sensible" if result.sensible else "QUESTIONABLE"
                print(f"  run {i + 1}: {result.latency:.1f}s  first_call={result.first_call}  [{mark}]")
        reports.append(report)

    print("\n" + "=" * 72)
    print("BENCHMARK REPORT")
    print("=" * 72)
    for r in reports:
        avg = f"{r.avg_latency:.1f}s" if r.avg_latency is not None else "n/a"
        slow = f"{r.slowest:.1f}s" if r.slowest is not None else "n/a"
        print(f"\n[{r.model}]")
        print(f"  successes:         {len(r.successes)}/{len(r.runs)}")
        print(f"  avg latency:       {avg}")
        print(f"  slowest:           {slow}")
        print(f"  sensible 1st call: {r.sensible_count}/{len(r.successes)}")
        errors = [run.error for run in r.runs if run.error]
        if errors:
            print(f"  errors:            {errors}")


if __name__ == "__main__":
    asyncio.run(main())
