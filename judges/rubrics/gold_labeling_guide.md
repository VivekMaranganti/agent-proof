version: 1

# Gold Labeling Guide

This guide is for a human reviewer producing a gold set: a small collection
of hand-assigned `pass` / `fail` / `uncertain` labels used to check whether
an LLM judge agrees with a careful human doing the same job. Store the
result with `judges.gold.save_gold_labels` — see `judges/gold.py` for the
`GoldLabel` schema (task id, label, rationale, labeler, timestamp).

## One gold set per judge dimension

A gold set calibrates exactly one judge. Don't mix criteria in a single
file: a policy-correctness gold set and a response-quality gold set are
different files, because they ask a reviewer to evaluate different things
for the same transcript. Name the file after the dimension it calibrates,
e.g. `policy_judge_seed.json`.

## What you're given

For each task, you'll see the same evidence the judge sees: the task's
input, the ordered tool calls the agent made, and (if produced) the
agent's final written reply. Apply the same rubric the judge is using —
`judges/rubrics/policy_judge.md` or `judges/rubrics/response_quality_judge.md`
— read it before labeling, not just this guide.

## How to label

1. Read the task input and the tool-call sequence in order.
2. Apply the relevant judge's rubric as if you were that judge.
3. Assign `pass`, `fail`, or `uncertain` using the same definitions the
   rubric gives the model — don't invent your own bar.
4. Write a one- or two-sentence rationale. This is what future reviewers
   (human or model) use to understand *why* you labeled it that way, so be
   concrete: cite the specific action or omission that drove your decision.
5. Record your name (or a stable identifier) as `labeler` and the current
   time as `labeled_at`.

## Disagreement with a judge is expected, not a bug

If a judge's verdict disagrees with your gold label, that's exactly what
`judges.gold.compare_verdicts_to_gold` is for surfacing. Don't relabel a
gold entry just because a judge disagreed with it — only relabel if, on
review, you believe your original label was wrong.

## Keep the set small and deliberate

A gold set doesn't need to cover the whole benchmark suite. A handful of
tasks per dimension, chosen to include clear passes, clear fails, and at
least one genuinely ambiguous case, is more useful for calibration than a
large set labeled quickly.
