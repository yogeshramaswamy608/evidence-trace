# Research question 2: the verifier against the author's labels

Generated Nov 12, 2026. Frozen verifier: commit 7aaf658 (link recovery frozen at 4748d14, judge output limit raised by deviation 6). Judge: Claude Opus 5.5, Actions run 43323262773; every request and response is in `data/rq2/judge/*_log.jsonl.gz`. The first judge run (Actions run 43319198927, registered 16-token limit) is kept in `data/rq2/judge_run1`.

The 200 test labels were read once, by `scripts/rq2_score.py`, after the verifier was frozen. Figures: `docs/rq2_test.json` (test), `docs/rq2_dev.json` (development), `docs/rq2_checks.json` (check sets, labels known by construction; `docs/rq2_checks_run1.json` for the first run). The human label file stays out of this repository until the blind re-code of Nov 24, 2026.

The link-blind baseline (deviation 3; play 3b) ran once on Nov 16, 2026: `scripts/rq2_baseline.py` at commit a479830, which leaves the frozen verifier unchanged, Actions run 43847729074, the same judge, prompt and output limit, 600 calls, 0 errors, every reply ending on its own with text; 15.13 USD at list prices (`data/rq2/baseline`). The 200 test labels were read by `scripts/rq2_score.py` for it, on the laptop, with no label printed. Figures: `docs/rq2_baseline_test.json`, `docs/rq2_baseline_dev.json`. Paired on the same 199 test claims (`scripts/rq2_paired.py`; `docs/rq2_paired_test_corrected.json`, `docs/rq2_paired_test_registered.json`), corrected records: baseline minus verifier, precision +7.3 points (3.9 to 11.7) and F1 +0.11 (0.06 to 0.17), both intervals excluding 0; recall +13.0 points (0.0 to 27.8); exact McNemar 54 to 17, p = 0.00001. On the registered records the verifier left 60 claims unlabeled at its budget, so that pairing is reported, not read.

Positive class: unsupported or contradicted. Not checkable claims are excluded. Intervals: cluster bootstrap over runs, seed 20261105.

| Verifier | Group | Claims | Positives | Unlabeled | Precision | Recall | F1 | Macro F1 | Kappa |
|---|---|---|---|---|---|---|---|---|---|
| Full verifier, corrected records (primary) | A_recovered_links | 173 | 21 | 0 | 13.9% (8.3 to 20.4) | 76.2% (57.1 to 93.8) | 0.24 | 0.24 | 0.09 |
| Full verifier, corrected records (primary) | B_agent_links | 26 | 2 | 0 | 7.7% (0.0 to 27.3) | 50.0% (0.0 to 100.0) | 0.13 | 0.11 | 0.00 |
| Full verifier, corrected records (primary) | all | 199 | 23 | 0 | 13.3% (7.8 to 19.1) | 73.9% (55.0 to 90.9) | 0.23 | 0.23 | 0.09 |
| Full verifier, corrected records (primary) | exploratory_without_self_reports | 186 | 13 | 0 | 6.0% (2.5 to 10.7) | 53.8% (26.7 to 81.8) | 0.11 | 0.19 | 0.06 |
| Full verifier, registered records (judge run stopped at its budget before 85 claims; unlabeled claims count as misses) | A_recovered_links | 173 | 21 | 54 | 14.7% (7.5 to 22.9) | 52.4% (30.4 to 73.7) | 0.23 | 0.24 | 0.08 |
| Full verifier, registered records (judge run stopped at its budget before 85 claims; unlabeled claims count as misses) | B_agent_links | 26 | 2 | 6 | 11.1% (0.0 to 37.5) | 50.0% (0.0 to 100.0) | 0.18 | 0.14 | 0.08 |
| Full verifier, registered records (judge run stopped at its budget before 85 claims; unlabeled claims count as misses) | all | 199 | 23 | 60 | 14.3% (7.3 to 21.8) | 52.2% (30.8 to 73.7) | 0.22 | 0.24 | 0.09 |
| Full verifier, registered records (judge run stopped at its budget before 85 claims; unlabeled claims count as misses) | exploratory_without_self_reports | 186 | 13 | 56 | 7.9% (2.6 to 14.3) | 46.2% (20.0 to 75.0) | 0.13 | 0.21 | 0.07 |
| No-judge baseline (Stages 1 and 2), corrected records | A_recovered_links | 173 | 21 | 0 | 0.0% (0.0 to 0.0) | 0.0% (0.0 to 0.0) | 0.00 | 0.22 | -0.02 |
| No-judge baseline (Stages 1 and 2), corrected records | B_agent_links | 26 | 2 | 0 | 16.7% (0.0 to 66.7) | 50.0% (0.0 to 100.0) | 0.25 | 0.20 | 0.04 |
| No-judge baseline (Stages 1 and 2), corrected records | all | 199 | 23 | 0 | 16.7% (0.0 to 66.7) | 4.3% (0.0 to 14.3) | 0.07 | 0.25 | 0.04 |
| No-judge baseline (Stages 1 and 2), corrected records | exploratory_without_self_reports | 186 | 13 | 0 | 25.0% (0.0 to 100.0) | 7.7% (0.0 to 25.0) | 0.12 | 0.25 | 0.03 |
| Link-blind baseline (Stage 3 judge on a capped pool of 50, no links), corrected records | A_recovered_links | 173 | 21 | 0 | 21.3% (14.0 to 29.6) | 90.5% (76.5 to 100.0) | 0.35 | 0.42 | 0.24 |
| Link-blind baseline (Stage 3 judge on a capped pool of 50, no links), corrected records | B_agent_links | 26 | 2 | 0 | 12.5% (0.0 to 40.0) | 50.0% (0.0 to 100.0) | 0.20 | 0.33 | 0.33 |
| Link-blind baseline (Stage 3 judge on a capped pool of 50, no links), corrected records | all | 199 | 23 | 0 | 20.6% (13.3 to 28.4) | 87.0% (71.4 to 100.0) | 0.33 | 0.43 | 0.26 |
| Link-blind baseline (Stage 3 judge on a capped pool of 50, no links), corrected records | exploratory_without_self_reports | 186 | 13 | 0 | 11.5% (5.7 to 18.3) | 76.9% (50.0 to 100.0) | 0.20 | 0.37 | 0.20 |
| Link-blind baseline (Stage 3 judge on a capped pool of 50, no links), registered records | A_recovered_links | 173 | 21 | 0 | 18.0% (10.9 to 25.7) | 76.2% (57.1 to 93.8) | 0.29 | 0.41 | 0.22 |
| Link-blind baseline (Stage 3 judge on a capped pool of 50, no links), registered records | B_agent_links | 26 | 2 | 0 | 11.1% (0.0 to 33.3) | 50.0% (0.0 to 100.0) | 0.18 | 0.32 | 0.29 |
| Link-blind baseline (Stage 3 judge on a capped pool of 50, no links), registered records | all | 199 | 23 | 0 | 17.3% (10.7 to 24.4) | 73.9% (55.0 to 90.9) | 0.28 | 0.41 | 0.23 |
| Link-blind baseline (Stage 3 judge on a capped pool of 50, no links), registered records | exploratory_without_self_reports | 186 | 13 | 0 | 9.1% (3.6 to 15.4) | 61.5% (33.3 to 88.9) | 0.16 | 0.37 | 0.18 |
