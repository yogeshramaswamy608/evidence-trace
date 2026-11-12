# Research question 2: the verifier against the author's labels

Generated Nov 12, 2026. Frozen verifier: commit 7aaf658 (link recovery frozen at 4748d14, judge output limit raised by deviation 6). Judge: Claude Opus 5.5, Actions run 43323262773; every request and response is in `data/rq2/judge/*_log.jsonl.gz`. The first judge run (Actions run 43319198927, registered 16-token limit) is kept in `data/rq2/judge_run1`.

The 200 test labels were read once, by `scripts/rq2_score.py`, after the verifier was frozen. Figures: `docs/rq2_test.json` (test), `docs/rq2_dev.json` (development), `docs/rq2_checks.json` (check sets, labels known by construction; `docs/rq2_checks_run1.json` for the first run). The human label file stays out of this repository until the blind re-code of Nov 24, 2026.

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
