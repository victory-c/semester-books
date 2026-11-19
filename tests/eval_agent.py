"""Score an agent-written books.json (tests/samples/agent_real_books.json) against EXPECTED.json."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_real import same, D, I   # noqa: reuse matcher (importing runs the rule eval quietly below)

agent = {c["course"]: c for c in json.load(open(os.path.join(D, "..", "agent_real_books.json")))["courses"]}
tot = dict(exp=0, found=0, extra=0, ed_ok=0, ed_n=0, isbn_ok=0, isbn_n=0, code_ok=0, code_n=0)
for e in json.load(open(os.path.join(D, "EXPECTED.json"))):
    got = agent.get(e["file"][:-4], {"books": []})["books"]
    used, miss = set(), []
    for b in e["books"]:
        j = next((k for k, g in enumerate(got) if k not in used and
                  (same(b["title"], g.get("title")) or (b.get("isbn") and I.to13(b["isbn"]) == I.to13(g.get("isbn") or "")))), None)
        tot["exp"] += 1
        if j is None:
            miss.append(b["title"]); continue
        used.add(j); tot["found"] += 1; g = got[j]
        if b.get("edition"):
            tot["ed_n"] += 1; tot["ed_ok"] += g.get("edition") == b["edition"]
        if b.get("isbn"):
            tot["isbn_n"] += 1; tot["isbn_ok"] += I.to13(b["isbn"]) == I.to13(g.get("isbn") or "")
        tot["code_n"] += 1; tot["code_ok"] += bool(g.get("access_code")) == bool(b.get("access_code"))
    extra = [g.get("title") for k, g in enumerate(got) if k not in used and g.get("kind", "book") == "book"]
    tot["extra"] += len(extra)
    print(f"{e['file']:32} books {len(e['books'])-len(miss)}/{len(e['books'])}" + (f"  MISS {miss}" if miss else "")
          + (f"  EXTRA {extra}" if extra else ""))
pct = lambda a, b: f"{a}/{b} ({100*a//max(b,1)}%)"
print(f"\nbooks found {pct(tot['found'], tot['exp'])}, extra {tot['extra']}, edition {pct(tot['ed_ok'], tot['ed_n'])}, "
      f"isbn {pct(tot['isbn_ok'], tot['isbn_n'])}, access code {pct(tot['code_ok'], tot['code_n'])}")
