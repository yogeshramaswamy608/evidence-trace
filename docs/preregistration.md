# Preregistration, paper 3: provenance of root-cause claims by LLM agents

Frozen at the git tag prereg-v1. Nothing below changes after the main runs start; any later change is dated and reported as a deviation.

## Fixed inputs

1. Benchmark: AIOpsLab commit 576c3f080c7ae2459a972afd4a2f8d5f01828430 (Oct 19, 2026).
2. Study set: the 41 active localization and analysis problems at that commit (28 localization, 13 analysis), listed in docs/study_problems.txt. Eight localization entries are commented out of the registry there and are not run.
3. Exclusion: a problem whose application fails to deploy in the probe check is excluded and listed with its reason.
4. Agents: claude-sonnet-5-5 and claude-haiku-5-5, AIOpsLab ReAct client, same tools and step limit, no temperature sent.
5. Design: 2 models x 41 problems x 3 repetitions (seeds 0, 1, 2) x 2 conditions (A free form, B evidence links required), at most 492 runs.
6. Judge for Stage 3: a model different from both agents (enforced in code), prompt src/evtrace/data/judge_prompt.txt, every request and response logged.
7. Sampling: src/evtrace/sample.py, seed 20261105, 300 claims, strata model x condition x task type, at most 5 per run, split 100 development and 200 test.
8. Gold claims: src/evtrace/gold.py, seed 20261105, mixed unmarked into the labeling queue.
9. Rubric: docs/labeling_rubric.md, version 1.
10. Statistics: src/evtrace/stats.py, bootstrap seed 20261105.

## Analysis

1. RQ1: unsupported, partly supported and contradicted rates with cluster bootstrap 95 percent intervals over runs.
2. RQ2: verifier precision, recall and F1 on the 200 test claims, positive class unsupported or contradicted; four-class confusion matrix, macro F1 and kappa.
3. RQ3: per model, exact McNemar test on 41 per-problem majority outcomes (correct when at least 2 of 3 runs are correct), Holm across the two models; secondary mixed-effects logistic regression with a random intercept for problem.
4. Reliability: blind re-code of 60 claims two weeks after first labels; unweighted kappa below 0.6 triggers one rubric revision and a full relabel.

## Budget

Main runs stop at 200 US dollars of model spend; problems not reached are listed.

## File hashes at the tag

See docs/prereg_hashes.txt.
