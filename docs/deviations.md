# Deviations from the preregistration

The preregistration is `docs/preregistration.md`, frozen at commit 1831475. It states that any later change is dated and reported as a deviation. Each deviation below is dated and reported in the manuscript.

## Deviation 1, Nov 10, 2026: human labels restarted from claim 1

The author discarded the first 65 labels, saved Nov 9 and 10, 2026, and restarted labeling from claim 1.

Reason, in the author's words: "I restarted the review of all 330 claims because I had mistaken an internal cache lookup for the endpoint that handled a request and relied on session history the rubric did not allow, and I wanted to check whether either mistake affected other labels."

The discarded labels are archived (sha256 c73ff019c8b97d2e3082b091923ea1eb4be51a0ce2d1103b5adf4e95ddd1abcc) and are used in no analysis.

How the labels were entered: the author drafted each label and its reason in private working notes, which were not kept, and entered them into the labeling page afterwards. The saved time of each label is therefore its entry time, not its labeling time. All 330 labels (300 sampled claims and 30 check claims) were entered by Nov 11, 2026, 07:59 UTC.

The reliability check is unchanged: a blind re-code of 60 claims two weeks after the labels were completed, on Nov 24, 2026, with one rubric revision and a full relabel if unweighted kappa falls below 0.6.

What the rater read: the rater read each run's records himself, in software that only displays them, and for trace spans he read the session file, which holds the full rows of the trace table the agent read. The labeling page showed trace spans as a service name with no content, so the re-code page of Nov 24, 2026 shows each span from the same rows. One rater, the author, labeled all claims; his blind re-code is the registered reliability check, and no second rater took part.

## Deviation 2, Nov 12, 2026: the check claims and the verifier's check set

The check claims mixed into the labeling queue came from two templates of `src/evtrace/gold.py` only: 18 claims of T5 ("A and B both showed the fault", built as partly supported) and 12 of T6 ("A served OP", built as supported). T1 and T2 need metric samples, and no main run exposed one: the agents read 15 metric tables in 12 runs, and the registered reader kept them as command output lines because it knows no `kpi_name` column (`docs/defect_counts.json`). T3, T4, T7 and T8 read as synthetic and were left out of the page. The check could therefore not show a labeler who avoids "contradicted" or "unsupported".

The author's label matched the built label on 22 of 30 check claims. All 8 disagreements fall on the two templates. `scripts/check_claim_defects.py` tests every check claim against the run's corrected record with rules written before it was first run:

- T6: the 3 claims labeled contradicted are each linked to the caller's side of a call (a span of another service in the same trace has the linked span as its parent and the same operation name); the 1 claim labeled partly supported is linked to an internal step (its parent span belongs to the same service). None of the 8 agreements on T6 has either property.
- T5: in all 18 claims the linked item of the first service carries no fault signal, so the built label rests on a premise its own item does not show. For 2 of the 4 disagreements the record shows the second service with items and no fault signal; for the other 2 it shows a fault signal for the second service, and the paper reports those as disagreements between the rater and the check claim.
- The parser defect of deviation 5 explains none of the 8.

The author's 30 labels stand; nothing is relabeled. The paper reports 22 of 30 as it came out and does not read it as a test the labeler passed; label reliability rests on the blind re-code. The registered `gold.py` stays byte for byte. A new `src/evtrace/gold_v2.py` keeps only templates whose label follows from the recorded fields of the item they are built from, or from the construction alone (T5 dropped, T6 replaced by span duration and error-flag templates with supported and contradicted labels). The verifier is scored on the rebuilt check set (`data/check_sets/check_set_v2.jsonl`), with the old set's score beside it.

## Deviation 3, Nov 12, 2026: the link-blind baseline reads at most 50 items per claim

As registered, the link-blind baseline reads a claim with all telemetry exposed in its run, pooled. A run's record reaches about 1.6 MB, past what one judge call can read. The pool is capped at 50 items per claim, chosen by a written rule fixed before any test label is scored and holding no label: items of a service the claim names first, then the number of words the claim and the item share, then the later exposure step (`src/evtrace/recover.py`, `pool`).

## Deviation 4, Nov 12, 2026: one replay of the failed Condition B summary calls

The summary call allowed 2,048 output tokens and its stop reason was not stored. The requests were not stored either, so each request of the 115 failed Condition B runs was rebuilt from the session file and the agent's code (`scripts/replay_b.py`); all 115 rebuilt runs sum to the input tokens the API billed, with the same number of calls (`data/replay/count.jsonl`). The summary call of each run was then sent once more with the same model and messages and an output limit of 8,192 tokens, fixed before any replay (`data/replay`, `docs/replay_report.json`). Every reply ended on its own. Most replies began with a thinking block, which counts toward the output limit while the agent kept only the text; 96 of 104 Claude Haiku 5.5 replies and 4 of 11 Claude Sonnet 5.5 replies used more than 2,048 output tokens, and 99 of 104 and 11 of 11 summaries parsed. The registered figures stay the results; the replay is exploratory, and no replayed claim is labeled or enters the sample.

## Deviation 5, Nov 12, 2026: research question 2 is scored on corrected exposure records

AIOpsLab's trace table has nine whitespace-aligned columns. The registered `src/evtrace/exposure.py` splits a row from the left, so an operation name that holds a space shifts the later cells: the record keeps the operation cut to its first word, a wrong or missing start time and duration, the error flag read from the wrong cell and a merged response. Over the 488 scored runs, 66,871 of 224,303 span items (29.8 percent) in 74 runs are affected, and 2,442 of the 5,914 spans the table marks as errors are recorded as no error (`docs/defect_counts.json`). Ids, trace ids, span ids and services are right in every item.

The registered `exposure.py` and every stored `record.json` stay byte for byte. A corrected reading, `src/evtrace/exposure_v2.py`, reads a row from both ends and keeps the parent span. `scripts/rebuild_corrected.py` rebuilds a corrected record for every run from its stored `session.json`, with the same item ids in the same order, checks that the registered parser gives the stored evidence back, and writes the hashes of both records to `data/corrected/manifest.jsonl`. Research question 2 is scored on the corrected records; the same scoring on the registered records is reported beside it. This deviation was declared before any test label was scored.

The human labels were not affected: for trace spans the rater read each run's session file, which holds the full rows of the trace table.

## Deviation 6, Nov 12, 2026: the Stage 3 judge's output limit

The registered judge (`ModelJudge` in `src/evtrace/verify.py`) asks for a one-word verdict with an output limit of 16 tokens. Claude Opus 5.5 begins its reply with a thinking block, which counts toward that limit. In the first judge run of the frozen verifier (commit 4748d14, Actions run 43319198927, kept in `data/rq2/judge_run1`), 1,079 of 1,129 judge replies stopped at the limit with no text, so the verifier read them as "unrelated". No test label had been read. The judge is run again with an output limit of 4,096 tokens (`scripts/rq2_run.py --judge-max-tokens`); the judge prompt, the model, the stages and the link recovery are unchanged, and the registered code is not edited. The first run is reported beside the second. This was declared before any test label was scored.
