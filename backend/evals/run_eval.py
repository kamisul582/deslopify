"""Eval suite: accuracy / precision / recall, repeatability, prompt-injection
resistance, citation verification rate, cost and latency.

Usage (needs ANTHROPIC_API_KEY, spends real money - see COST note in README):
    python -m evals.run_eval --model claude-haiku-4-5-20251001 --repeats 3
    python -m evals.run_eval --min-accuracy 0.8 --max-injection-success 0.0   # CI gate
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.llm import LLMClient, LLMError
from app.pipeline import run_pipeline
from app.prompts import active_versions

from .metrics import agenda_metrics, classification_metrics, injection_metrics, percentile, repeatability

HERE = Path(__file__).parent
RESULTS = HERE / "results"


def load_dataset() -> list[dict]:
    return [json.loads(line) for line in (HERE / "dataset.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


async def run_once(item, llm, settings, model, sem):
    async with sem:
        t0 = time.perf_counter()
        try:
            r = await run_pipeline(item["text"], llm, settings, model)
        except LLMError as e:
            return {"id": item["id"], "label": item["label"], "error": e.code}
        return {
            "id": item["id"],
            "label": item["label"],
            "kind": item["kind"],
            "verdict": r.verdict,
            "ai_probability": r.ai_probability,
            "injection_detected": r.injection_detected,
            "agenda_status": r.agenda_status,
            "latency_s": time.perf_counter() - t0,
            "cost_usd": r.usage.cost_usd,
            "input_tokens": r.usage.input_tokens,
            "output_tokens": r.usage.output_tokens,
        }


async def evaluate(model: str, repeats: int, concurrency: int = 4) -> dict:
    settings = Settings.from_env()
    settings.model = model
    llm = LLMClient(settings)
    sem = asyncio.Semaphore(concurrency)
    data = load_dataset()
    tasks = [run_once(it, llm, settings, model, sem) for it in data for _ in range(repeats)]
    results = await asyncio.gather(*tasks)
    errors = [r for r in results if "error" in r]
    ok = [r for r in results if "error" not in r]

    by_item: dict[str, list[dict]] = {}
    for r in ok:
        by_item.setdefault(r["id"], []).append(r)
    clean_first = [runs[0] for runs in by_item.values() if runs[0]["kind"] == "clean"]
    inj_all = [r for r in ok if r["kind"] == "injection"]
    lat = [r["latency_s"] for r in ok]
    n_items = len(data)

    return {
        "meta": {
            "model": model,
            "prompt_versions": active_versions(),
            "repeats": repeats,
            "dataset_items": n_items,
            "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "errors": len(errors),
        },
        "classification": classification_metrics(clean_first),
        "classification_all_runs": classification_metrics([r for r in ok if r["kind"] == "clean"]),
        "repeatability": repeatability({k: v for k, v in by_item.items() if v[0]["kind"] == "clean"}) if repeats > 1 else None,
        "injection": injection_metrics(inj_all),
        "agenda": agenda_metrics([r for r in ok if r["kind"] == "clean"]),
        "cost": {
            "total_usd": round(sum(r["cost_usd"] for r in ok), 4),
            "per_request_usd": round(sum(r["cost_usd"] for r in ok) / max(len(ok), 1), 5),
        },
        "latency_s": {"mean": round(sum(lat) / max(len(lat), 1), 2), "p95": round(percentile(lat, 0.95), 2)},
        "raw": results,
    }


def to_markdown(res: dict) -> str:
    m, c, rep, inj, ag = res["meta"], res["classification"], res["repeatability"], res["injection"], res["agenda"]
    lines = [
        "| Model | Prompts | Acc (decided) | Precision | Recall | Abstain | Inj. success | Flip rate | $/req | p95 s |",
        "|---|---|---|---|---|---|---|---|---|---|",
        f"| `{m['model']}` | detect {m['prompt_versions']['detect']} / agenda {m['prompt_versions']['agenda']} | "
        f"{c['accuracy_decided']} | {c['precision']} | {c['recall']} | {c['abstain_rate']} | "
        f"{inj['attack_success_rate']} | {rep['verdict_flip_rate'] if rep else 'n/a'} | "
        f"{res['cost']['per_request_usd']} | {res['latency_s']['p95']} |",
    ]
    return "\n".join(lines) + f"\n\nAgenda citation check (AI verdicts): {ag}\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=Settings.model)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--min-accuracy", type=float)
    ap.add_argument("--max-injection-success", type=float)
    ap.add_argument("--max-flip-rate", type=float)
    a = ap.parse_args()

    res = asyncio.run(evaluate(a.model, a.repeats))
    RESULTS.mkdir(exist_ok=True)
    v = res["meta"]["prompt_versions"]
    out = RESULTS / f"{a.model}__detect-{v['detect']}__agenda-{v['agenda']}.json"
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    md = to_markdown(res)
    out.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)
    print(f"saved {out}")

    failed = []
    if res["meta"]["errors"]:
        failed.append(f"{res['meta']['errors']} API errors")
    acc = res["classification"]["accuracy_decided"]
    if a.min_accuracy is not None and (acc is None or acc < a.min_accuracy):
        failed.append(f"accuracy {acc} < {a.min_accuracy}")
    asr = res["injection"]["attack_success_rate"]
    if a.max_injection_success is not None and (asr is None or asr > a.max_injection_success):
        failed.append(f"injection success {asr} > {a.max_injection_success}")
    flip = (res["repeatability"] or {}).get("verdict_flip_rate")
    if a.max_flip_rate is not None and flip is not None and flip > a.max_flip_rate:
        failed.append(f"flip rate {flip} > {a.max_flip_rate}")
    if failed:
        print("EVAL GATE FAILED:", "; ".join(failed), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
