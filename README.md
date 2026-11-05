# evidence-trace

Bind every root-cause claim of an AI incident agent to the telemetry it actually saw, and check it.

This is the code for paper 3, "Evidence-Traceable AI Incident Response: Binding Every Agent Claim to Telemetry" (Yogesh Ramaswamy). It runs agents on AIOpsLab problems (Chen et al. 2025, commit 576c3f0), records every telemetry item each agent was shown, and labels each claim of the agent's root-cause summary as supported, partly supported, unsupported or contradicted.

## Parts

| Part | File | What it does |
| --- | --- | --- |
| Provenance format | `src/evtrace/data/provenance.schema.json` | JSON Schema of a record: evidence items, claims, links |
| Exposure log | `src/evtrace/exposure.py`, `session.py` | Rebuilds, from an AIOpsLab session file, every span, log line, metric sample and command line shown to the agent, with the steps that showed it |
| Stage 1 | `src/evtrace/rules.py` | Schema and rules R1 to R4 |
| Stages 2 and 3 | `src/evtrace/verify.py` | Consistency checks (service, time window, value) and a judge model with a frozen prompt (`data/judge_prompt.txt`) |
| Condition B links | `src/evtrace/locate.py` | Resolves the agent's locators (`span:`, `log:`, `metric:`, `cmd:`) to evidence items |
| Gold labels by construction | `src/evtrace/gold.py` | Claims with known labels built from the exposure log, eight templates |
| Agents | `src/evtrace/agent.py` | The ReAct agent of AIOpsLab with one model behind it, and a probe agent that needs no model |
| Statistics | `src/evtrace/stats.py` | Cohen's kappa, exact McNemar, Holm, precision and recall, cluster bootstrap |
| Runs | `scripts/run_aiopslab.py`, `.github/workflows/pilot.yml` | AIOpsLab in a kind cluster on the GitHub runner; one folder per run |

## Use

```
pip install -e '.[test]'
pytest -q
evtrace selftest tests/fixtures/session_synthetic.json
evtrace verify record.json
evtrace verify record.json --model MODEL   # Stage 3 judge; reads LLM_API_KEY
```

The pilot workflow (Actions, "pilot", Run workflow) runs the probe agent with no key, or a model agent with the repository secret `LLM_API_KEY`, and stops at the budget given.

The test fixture is synthetic: it has the shape of an AIOpsLab session file and uses the sample identifiers of the W3C Trace Context specification. It holds no data from any real run.

## License

Apache 2.0.
