#!/usr/bin/env python3
"""tbfind: from syllabi (or an agent-written book list) to "which books, which edition, where".

Examples
  python3 tbfind.py "MATH 1A=samples/math1a.txt" samples/bio1a.html --school berkeley
  python3 tbfind.py --books samples/agent_books.json --json out/result.json
  python3 tbfind.py --isbn 9780134093413
  python3 tbfind.py --sample          # bundled example, no network, no saved state

Exit codes (for the Skill):
  0  results printed (some courses may still need input; see totals.need_input)
  2  bad input: a file is missing or the book list is not valid JSON / wrong shape
  3  no books and no "no textbook" answer for any course: ask the student for a bookstore screenshot
  1  unexpected error (message on stderr)
"""
import argparse
import json
import os
import re
import sys

from tbfind import extract, lookup, report


def fail(msg, code):
    print(msg, file=sys.stderr)
    sys.exit(code)


def load_syllabus(spec):
    course, _, path = spec.rpartition("=") if "=" in spec else (None, None, spec)
    if not os.path.exists(path):
        fail(f"file not found: {path}", 2)
    if path.lower().endswith(".pdf"):
        fail(f"{path}: PDF not supported here; pass the extracted text (the agent reads PDFs in Cubbie)", 2)
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    name = course or os.path.splitext(os.path.basename(path))[0].replace("_", " ").upper()
    return extract.extract(raw, course=name)


URL_RE = re.compile(r"(?:https?://|www\.)[^\s)\]]+", re.I)
# Shadow libraries / file-sharing sites: never repeated to the student, whatever the syllabus or agent wrote.
BLOCKED = re.compile(r"libgen|library\s*genesis|z-?lib|1lib|annas?-?archive|anna's archive|welib|pdfdrive|"
                     r"sci-?hub|b-ok\.|bookfi|ebook-?hunter|vk\.com", re.I)


# Text that should never reach the student from a book field: download offers and instructions aimed at Cubbie.
SUSPECT = re.compile(r"free\s*(?:pdf|download|e-?book)|\bdownload (?:it|the|here|link|from)\b|\btorrents?\b|"
                     r"tell the student|ignore (?:the|all|previous)|\binstructions? (?:for|to)\b|"
                     r"you (?:must|should) (?:send|tell|say)", re.I)


def _clean_text(v):
    """Drop links, and any part of the text (split at brackets, dashes, ; or |) that names a blocked site or reads
    like an instruction; keep the rest."""
    v = URL_RE.sub(" ", v)
    v = re.sub(r"[(\[]\s*(?:see|at|from|via|on)?\s*[)\]]", " ", v, flags=re.I)   # brackets left empty by a link
    parts = re.split(r"\s*(?:[()\[\];|]|\s[-–—]\s|\s[-–—]$)\s*", v)
    bad = [p for p in parts if BLOCKED.search(p) or SUSPECT.search(p)]
    if not bad:
        return " ".join(v.split()).strip(" -:,;") or None   # nothing to drop: keep the original punctuation
    keep = [p for p in parts if p.strip() and p not in bad]
    return " ".join(" ".join(keep).split()).strip(" -:,;") or None


def _clean_book(b, where):
    """Normalise one agent-written book: edition as a number, no links or blocked sites in text fields."""
    b = dict(b)
    ed = b.get("edition")
    if ed is not None and not isinstance(ed, int):
        n = lookup.edition_number(str(ed))
        if n is None:
            fail(f"{where}.edition must be a number like 5 (got {ed!r})", 2)
        b["edition"] = n
    for k in ("title", "author", "courseware", "publisher", "note", "raw"):
        if isinstance(b.get(k), str):
            b[k] = _clean_text(b[k])
    if b.get("url") and BLOCKED.search(str(b["url"])):
        b["url"] = None
    if not (b.get("title") or b.get("isbn") or b.get("kind") == "reader"):
        fail(f"{where} needs a title or an isbn", 2)
    return b


def load_books_json(path):
    """Book list the agent wrote: {"school": ..., "courses": [{"course", "books": [...]}, ...]}."""
    if not os.path.exists(path):
        fail(f"file not found: {path}", 2)
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        fail(f"{path} is not valid JSON: {e}", 2)
    if not isinstance(data, dict) or not isinstance(data.get("courses"), list):
        fail('book list must be {"courses": [{"course": "...", "books": [...]}]}', 2)
    courses = []
    for i, c in enumerate(data["courses"]):
        if not isinstance(c, dict) or not c.get("course"):
            fail(f"courses[{i}] needs a 'course' name", 2)
        books = []
        for j, b in enumerate(c.get("books") or []):
            if not isinstance(b, dict) or not (b.get("title") or b.get("isbn") or b.get("kind") == "reader"):
                fail(f"courses[{i}].books[{j}] needs a title or an isbn", 2)
            lib = b.get("library")
            if lib is not None and (not isinstance(lib, dict) or lib.get("status") not in report.LIBRARY_STATUSES):
                fail(f"courses[{i}].books[{j}].library.status must be one of {list(report.LIBRARY_STATUSES)}", 2)
            if b.get("kind") and b["kind"] not in report.KINDS:
                fail(f"courses[{i}].books[{j}].kind must be one of {list(report.KINDS)}", 2)
            if b.get("status") and b["status"] not in report.STATUS_ORDER:
                fail(f"courses[{i}].books[{j}].status must be one of {sorted(report.STATUS_ORDER)}", 2)
            b = _clean_book(b, f"courses[{i}].books[{j}]")
            books.append(dict(b, isbns=[b["isbn"]] if b.get("isbn") else []))
        flags = dict(c.get("flags") or {})
        for k in ("no_textbook", "inclusive_access", "see_bookstore", "course_reader", "syllabus_empty"):
            if k in c:
                flags[k] = bool(c[k])
        # The agent may also pass the syllabus text; rules double-check what it wrote.
        if c.get("syllabus_text"):
            rules = extract.extract(c["syllabus_text"], c["course"])
            for k, v in rules["flags"].items():
                flags.setdefault(k, v)
            if not books:
                books = rules["books"]
        courses.append({"course": c["course"], "books": books, "flags": flags})
    return courses, data.get("school")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("syllabi", nargs="*", help='syllabus text/HTML files, optionally "COURSE=path"')
    p.add_argument("--books", help="agent-written book list (JSON)")
    p.add_argument("--isbn", action="append", help="look up one ISBN (repeatable)")
    p.add_argument("--school", help="berkeley or asu for library links; others get WorldCat")
    p.add_argument("--json", help="also write the full result to this file")
    p.add_argument("--no-lookup", action="store_true", help="skip Open Library/OpenStax (extraction only)")
    p.add_argument("--offline", action="store_true", help="use only the local cache")
    p.add_argument("--sample", action="store_true", help="run on the bundled sample syllabus, no network")
    p.add_argument("--library-todo", action="store_true",
                   help="print the catalog searches for Cubbie to open in its browser, one JSON line each, and stop")
    p.add_argument("--full-text", help="write the full list (for a PDF) to this file and print a one-screen summary")
    a = p.parse_args(argv)

    if a.sample:
        here = os.path.dirname(os.path.abspath(__file__))
        a.syllabi = ["MATH 1A=" + os.path.join(here, "..", "assets", "sample_syllabus.txt")]
        a.no_lookup, a.school = True, a.school or "berkeley"
    if a.offline:
        lookup.OFFLINE = True
    school = a.school
    courses = []
    if a.books:
        got, sch = load_books_json(a.books)
        courses += got
        school = school or sch
    for spec in a.syllabi:
        courses.append(load_syllabus(spec))
    if a.isbn:
        courses.append({"course": "Lookup", "books": [{"isbns": [i], "status": "unspecified"} for i in a.isbn],
                        "flags": {}})
    if not courses:
        p.print_help()
        return 2

    for c in courses:
        c["books"] = [_clean_book(b, c["course"] or "book") for b in c["books"]]
    result = report.build(courses, school=school, do_lookup=not a.no_lookup)
    if result.get("lookup_failed"):
        print(f"tbfind: stopped online lookups for this run ({result['lookup_failed']})", file=sys.stderr)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    if a.library_todo:
        todo = report.library_todo(result)
        for row in todo:
            print(json.dumps(row, ensure_ascii=False))
        if not todo:
            print("nothing to check" if school else "no catalog link for this school; skip the library step")
        return 0
    if a.full_text:
        with open(a.full_text, "w") as f:
            f.write(report.to_text(result))
        print(report.to_summary(result))
    else:
        print(report.to_text(result))
    if all(c["state"] == "not_found" for c in result["courses"]):
        return 3
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:   # never leave the agent with a bare traceback
        print(f"tbfind failed: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
