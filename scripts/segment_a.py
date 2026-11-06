"""Propose atomic claims for Condition A free-text summaries (manuscript Section 5.5).

Input: JSON lines {run_id, problem_id, text}. Output: JSON lines {run_id, problem_id, claims:[{claim_id,text,type}]}
and a log of every request and response. The author corrects the proposals by hand.
"""
import argparse, json, os, time, urllib.error, urllib.request
from pathlib import Path

PROMPT = (Path(__file__).resolve().parents[1] / "src/evtrace/data/segment_prompt.txt").read_text()


def call(model: str, text: str, key: str) -> str:
    body = {"model": model, "max_tokens": 4096, "messages": [{"role": "user", "content": PROMPT + text}]}
    for attempt in range(4):
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), method="POST",
                                     headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return "".join(b.get("text", "") for b in json.load(r)["content"])
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 529) and attempt < 3:
                time.sleep(10 * (attempt + 1)); continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:300]}")


def parse(reply: str) -> list[dict]:
    s = reply[reply.find("["): reply.rfind("]") + 1]
    out = json.loads(s)
    return [{"claim_id": f"a{i+1}", "text": c["text"].strip(), "type": c["type"]} for i, c in enumerate(out) if c.get("text", "").strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out"); ap.add_argument("log"); ap.add_argument("--model", default="claude-opus-5-5")
    a = ap.parse_args()
    key = os.environ["LLM_API_KEY"]
    with open(a.inp) as f, open(a.out, "w") as o, open(a.log, "w") as lg:
        for line in f:
            r = json.loads(line)
            reply = call(a.model, r["text"], key)
            lg.write(json.dumps({"run_id": r["run_id"], "model": a.model, "request": PROMPT + r["text"], "response": reply}) + "\n")
            try:
                claims = parse(reply); err = ""
            except Exception as e:  # recorded, the author segments this run by hand
                claims, err = [], f"parse: {e}"
            o.write(json.dumps({"run_id": r["run_id"], "problem_id": r["problem_id"], "claims": claims, "error": err}) + "\n")


if __name__ == "__main__":
    main()
