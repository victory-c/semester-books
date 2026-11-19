"""Score the rule-based extractor against hand-labelled real syllabi (tests/samples/real/EXPECTED.json)."""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from tbfind import extract, isbn as I

D = os.path.join(ROOT, "tests", "samples", "real")
norm = lambda t: " ".join(re.findall(r"[a-z0-9]+", (t or "").lower()))

def same(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    wa, wb = set(a.split()) - {"the", "a", "of", "and"}, set(b.split()) - {"the", "a", "of", "and"}
    return a in b or b in a or len(wa & wb) / max(1, min(len(wa), len(wb))) >= 0.6

def main():
    tot = dict(exp=0, found=0, extra=0, ed_ok=0, ed_n=0, isbn_ok=0, isbn_n=0, flag_ok=0, flag_n=0)
    for e in json.load(open(os.path.join(D, "EXPECTED.json"))):
        text = open(os.path.join(D, e["file"])).read().split("\n", 2)[-1]
        r = extract.extract(text, e["file"])
        got = r["books"]
        used, miss = set(), []
        for b in e["books"]:
            j = next((k for k, g in enumerate(got) if k not in used and
                      (same(b["title"], g["title"]) or (b.get("isbn") and I.to13(b["isbn"]) in g["isbns"]))), None)
            tot["exp"] += 1
            if j is None:
                miss.append(b["title"]); continue
            used.add(j); tot["found"] += 1
            g = got[j]
            if b.get("edition"):
                tot["ed_n"] += 1; tot["ed_ok"] += g["edition"] == b["edition"]
            if b.get("isbn"):
                tot["isbn_n"] += 1; tot["isbn_ok"] += I.to13(b["isbn"]) in g["isbns"]
        extra = [g["title"] for k, g in enumerate(got) if k not in used]
        tot["extra"] += len(extra)
        fl = r["flags"]
        exp_code = any(b.get("access_code") for b in e["books"])
        checks = {"no_textbook": (fl["no_textbook"], e["no_textbook"]),
                  "inclusive": (fl["inclusive_access"], e["inclusive_access"]),
                  "reader": (fl["course_reader"], e["course_reader"]),
                  "code": (bool(fl["courseware"]) or any(g["access_code"] for g in got), exp_code)}
        bad = [k for k, (a, b) in checks.items() if a != b]
        tot["flag_n"] += len(checks); tot["flag_ok"] += len(checks) - len(bad)
        print(f"{e['file']:32} books {len(e['books'])-len(miss)}/{len(e['books'])}  extra {len(extra)}"
              + (f"  MISS {miss}" if miss else "") + (f"  EXTRA {extra}" if extra else "") + (f"  FLAGS {bad}" if bad else ""))
    pct = lambda a, b: f"{a}/{b} ({100*a//max(b,1)}%)"
    print(f"\nbooks found {pct(tot['found'], tot['exp'])}, extra {tot['extra']}, edition {pct(tot['ed_ok'], tot['ed_n'])}, "
          f"isbn {pct(tot['isbn_ok'], tot['isbn_n'])}, flags {pct(tot['flag_ok'], tot['flag_n'])}")


if __name__ == "__main__":
    main()
