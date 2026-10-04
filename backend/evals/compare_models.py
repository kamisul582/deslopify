"""Run the eval for several models and print one comparison table.

    python -m evals.compare_models claude-haiku-4-5-20251001 claude-sonnet-5-5 --repeats 3

Paste the table into docs/MODEL_DECISION.md together with the written decision.
"""

import argparse
import asyncio

from .run_eval import evaluate, to_markdown


async def main_async(models, repeats):
    out = []
    for m in models:
        out.append(to_markdown(await evaluate(m, repeats)).split("\n\n")[0].splitlines())
    print(out[0][0])
    print(out[0][1])
    for rows in out:
        print(rows[2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    ap.add_argument("--repeats", type=int, default=3)
    a = ap.parse_args()
    asyncio.run(main_async(a.models, a.repeats))


if __name__ == "__main__":
    main()
