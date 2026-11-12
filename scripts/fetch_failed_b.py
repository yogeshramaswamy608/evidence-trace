"""Copy the run folders of the failed Condition B runs out of this repository's Actions artifacts (P4).
Usage (in Actions, GH_TOKEN set): python scripts/fetch_failed_b.py OUT_DIR
A failed run is a reached Condition B run whose summary did not parse (data/runs/run_outcomes.jsonl, b_parsed false)."""
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile


def main(out: str) -> int:
    rows = [json.loads(l) for l in open("data/runs/run_outcomes.jsonl")]
    failed = [r for r in rows if r["condition"] == "B" and r["reached"] and not r.get("b_parsed")]
    repo = os.environ["GITHUB_REPOSITORY"]
    for aid in sorted({r["artifact"] for r in failed}):
        raw = subprocess.run(["gh", "api", f"repos/{repo}/actions/artifacts/{aid}/zip"], check=True, capture_output=True).stdout
        z = zipfile.ZipFile(io.BytesIO(raw))
        for r in failed:
            if r["artifact"] != aid:
                continue
            for name in ("session.json", "summary.txt", "usage.json", "meta.json"):
                dest = os.path.join(out, r["run_id"], name)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(f"{r['run_id']}/{name}") as src, open(dest, "wb") as fh:
                    shutil.copyfileobj(src, fh)
    print(len(failed), "failed runs copied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
