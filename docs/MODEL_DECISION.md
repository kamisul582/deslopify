# Model decision: Haiku vs Sonnet

**Decision (provisional): keep `claude-haiku-4-5-20251001` as the default model.**

Measured on 2026-10-04 with `python -m evals.run_eval --repeats 3` (prompts detect v1 / agenda v1):

| Model | Prompts | Acc (decided) | Precision | Recall | Abstain | Inj. success | Flip rate | $/req | p95 s |
|---|---|---|---|---|---|---|---|---|---|
| `claude-haiku-4-5-20251001` | detect v1 / agenda v1 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | $0.0032 | 9.5 |
| `claude-sonnet-5-5` | detect v1 / agenda v1 | 1.0 | 1.0 | 1.0 | 0.042 | 0.0 | 0.042 | $0.0096 | 12.1 |
| `claude-haiku-4-5-20251001` | detect v1 / agenda **v2** | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | $0.0030 | 7.6 |

Run on 2026-10-04, 24 clean items x 3 repeats + 18 injection runs per model. Agenda citations that passed verification on AI verdicts: Haiku 80% verified / 20% partial (some claims dropped), Sonnet 94% / 6%. Haiku had 1 of 90 requests fail with unparseable model JSON after the retry (1.1%). Raw results: `backend/evals/results/`.

## Why Haiku

- On this set both models are perfect on accuracy, precision, recall and injection resistance (0% attack success, every injection flagged), so accuracy does **not** separate them.
- Haiku costs about 3x less per request ($0.0032 vs $0.0096) and has lower p95 latency (9.5 s vs 12.1 s). With a per-IP limit of 5/day and a daily budget cap, that is the difference between roughly 3x more free analyses for the same money.
- Verdict stability: Haiku had no verdict flips across repeats; Sonnet flipped one item (4%) and abstained on one clean item (4%). Neither is significant at this sample size.

## What Sonnet did better

- Agenda grounding: 94% of agendas had every quote verified vs 80% for Haiku. The verification step drops unsupported claims, so this costs completeness, not correctness.
- Haiku failed to produce parseable JSON on 1 of 90 requests after one repair retry (1.1%); Sonnet had none. The user sees a clean error and is not charged a quota unit.

## When to revisit

Switch the agenda step (not detection) to Sonnet if real traffic shows many partially-verified agendas, or if a larger real-world dataset separates the models on false-positive rate. Both are one env var (`MODEL`) away.

**Caveat:** the seed dataset is small and synthetic (see `backend/evals/build_dataset.py`). Differences of a few points between models on 24 items are noise, and a perfect score is a sign the set is easy. Grow it with real, independently labelled texts before treating any gap as real.

## Update: agenda prompt v2 (Haiku)

The agenda prompt was reworked (v2): shorter output (TL;DR, a guessed author prompt, at most 3 tactics, one context line instead of a table). Re-run on Haiku with the same dataset: unchanged classification (detection prompt untouched), 0 injection successes, 0 flips, cost per request $0.0030 (v1: $0.0032), p95 7.6 s (v1: 9.5 s), 86% of agendas fully verified (v1: 80%). A "repair turn" in the LLM wrapper (the model is shown its own invalid JSON and the error) removed the unparseable-output failures seen on one text (`ai-03`); Sonnet was not re-run on v2. The decision (Haiku by default) stands. The guessed author prompt cannot be verified against the text, so the UI labels it as a guess.
