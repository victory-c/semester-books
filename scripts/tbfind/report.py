"""Build the per-course result and the short iMessage-style reply."""
from . import links, lookup
from .isbn import to13

STATUS_ORDER = {"required": 0, "unspecified": 1, "recommended": 2, "optional": 3}


CONFIDENT = ("isbn", "isbn-unverified", "title+edition")
KINDS = ("book", "courseware", "reader")


def _non_book(book, kind):
    """Courseware and course readers: nothing to look up, nothing to compare."""
    return {"kind": kind, "title": book.get("title") or ("Course reader" if kind == "reader" else book.get("courseware")),
            "author": None, "edition_asked": None, "edition_found": None,
            "isbn": to13(book.get("isbn") or "") if book.get("isbn") else None, "confidence": "skipped",
            "status": book.get("status") or "unspecified", "access_code": kind == "courseware" or bool(book.get("access_code")),
            "courseware": book.get("courseware") or (book.get("title") if kind == "courseware" else None),
            "free": None, "library": None, "catalog_search_url": None, "compare_url": None, "library_url": None, "older_editions": [], "older_edition_ok": False,
            "custom": False, "notes": [], "source_line": book.get("raw")}


def resolve_book(book, school, do_lookup=True, oer_hint=False):
    kind = book.get("kind") or "book"
    if kind != "book":
        return _non_book(book, kind)
    isbns = [i for i in (to13(x) for x in book.get("isbns") or [book.get("isbn")] if x) if i]
    book = dict(book, isbns=isbns)
    info = lookup.identify(book) if do_lookup else {"match": None, "confidence": "skipped", "authors": [],
                                                      "older_editions": [], "notes": [], "public_domain_url": None}
    match = info.get("match") or {}
    isbn = match.get("isbn13") or (isbns[0] if isbns else None)
    if info.get("confidence") not in CONFIDENT and not isbns:
        isbn = None   # only show an ISBN we are sure of
    title = book.get("title") or info.get("title")
    free = {"kind": "provided", "url": book.get("url")} if book.get("provided") else None
    if do_lookup and not free:
        line = " ".join(str(book.get(k) or "") for k in ("raw", "author", "title", "publisher", "note")).lower()
        hint = oer_hint or any(w in line for w in ("openstax", "free online", "open textbook", "oer"))
        stax = lookup.openstax_match(title or "", set(isbns), allow_title=hint)
        if stax:
            free = {"kind": "openstax", "title": stax["title"], "url": stax["url"]}
        elif info.get("public_domain_url"):
            free = {"kind": "public_domain", "url": info["public_domain_url"]}
    return {
        "kind": "book",
        # Filled in by Cubbie after it opens catalog_search_url in its browser (see SKILL.md).
        "library": book.get("library"),
        "catalog_search_url": None if free else links.catalog_search_url(school, isbn, title, book.get("author")),
        "title": title,
        "author": book.get("author") or (", ".join(info.get("authors") or []) or None),
        "edition_asked": book.get("edition"),
        "edition_found": match.get("edition"),
        "isbn": isbn,
        "confidence": info.get("confidence"),
        "status": book.get("status") or "unspecified",
        "access_code": bool(book.get("access_code")),
        "courseware": book.get("courseware"),
        "free": free,
        "compare_url": None if free else links.compare_link(
            isbn, " ".join(x for x in (title, _ed(book["edition"]) + "ition" if book.get("edition") else None) if x),
            book.get("author")),
        "library_url": links.library_link(school, isbn, title),
        "older_editions": info.get("older_editions") or [],
        "older_edition_ok": bool(book.get("older_edition_ok")),
        "custom": bool(book.get("custom")),
        "notes": info.get("notes") or [],
        "source_line": book.get("raw"),
    }


def build(courses, school=None, do_lookup=True):
    """courses: [{'course', 'books', 'flags'}] -> result dict."""
    out = {"school": school, "courses": [], "totals": {}}
    n_books = n_free = n_code = n_lib = 0
    for c in courses:
        hint = bool((c.get("flags") or {}).get("mentions_oer")) and len(c.get("books", [])) == 1
        books = [resolve_book(b, school, do_lookup, oer_hint=hint) for b in c.get("books", [])]
        books.sort(key=lambda b: STATUS_ORDER.get(b["status"], 1))
        flags = c.get("flags") or {}
        # Courseware named anywhere in the syllabus usually comes bundled with the main book.
        if flags.get("courseware") and books and not any(b["access_code"] for b in books) and books[0]["kind"] == "book":
            books[0]["access_code"] = True
            books[0]["courseware"] = flags["courseware"][0]
        if books:
            state = "found"
        elif flags.get("no_textbook"):
            state = "no_textbook"
        else:
            state = "not_found"
        n_books += sum(1 for b in books if b["kind"] == "book")
        n_free += sum(1 for b in books if b["free"])
        n_lib += sum(1 for b in books if (b.get("library") or {}).get("status") in ("ebook", "open_access"))
        n_code += sum(1 for b in books if b["access_code"])
        if not books and flags.get("courseware"):
            n_code += 1
        out["courses"].append({"course": c.get("course"), "state": state, "books": books, "flags": flags})
    out["totals"] = {"courses": len(courses), "books": n_books, "free": n_free, "access_code": n_code,
                     "library_ebook": n_lib,
                     "need_input": [c["course"] for c in out["courses"] if c["state"] == "not_found"]}
    return out


def _ed(n):
    if not n:
        return ""
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf} ed"


def to_text(result):
    """Plain text, no Markdown, links on their own line: how Cubbie would text it."""
    t = result["totals"]
    lines = []
    head = f"Found {t['books']} book{'s' if t['books'] != 1 else ''} across {t['courses']} course{'s' if t['courses'] != 1 else ''}."
    if t["access_code"]:
        head += f" {t['access_code']} need{'s' if t['access_code'] == 1 else ''} an access code."
    if t["free"]:
        head += f" {t['free']} {'is' if t['free'] == 1 else 'are'} free."
    if t.get("library_ebook"):
        head += f" {t['library_ebook']} you can read free through the library."
    lines += [head, ""]
    for c in result["courses"]:
        lines.append(c["course"] or "Course")
        f = c["flags"]
        if c["state"] == "no_textbook":
            lines.append("No textbook to buy. Readings look like they're on the course site.")
        elif c["state"] == "not_found":
            if f.get("courseware"):
                lines.append(f"No book listed, but it uses {', '.join(f['courseware'])}, which usually needs a paid access code.")
            if f.get("see_bookstore"):
                lines.append("The syllabus just points to the bookstore list. Send me a screenshot of it for this one?")
            else:
                lines.append("I couldn't find a book list in the syllabus. Send me a screenshot of the bookstore list for this one?")
        for b in c["books"]:
            tag = "" if b["status"] in ("required", "unspecified") else f" ({b['status']})"
            if b["kind"] == "courseware":
                lines.append(f"- {b['title']}{tag}: paid online access, bought separately (usually through the link in Canvas).")
                continue
            if b["kind"] == "reader":
                lines.append(f"- {b['title']}{tag}: usually sold only through the campus copy shop or bookstore.")
                continue
            bits = [b["title"] or "Untitled"]
            if b["author"]:
                bits.append(b["author"].split(",")[0])
            ed = _ed(b["edition_asked"] or b["edition_found"])
            if ed:
                bits.append(ed)
            lines.append("- " + ", ".join(bits) + tag)
            if b["isbn"]:
                lines.append(f"  ISBN {b['isbn']}")
            if b["free"]:
                what = {"openstax": "free on OpenStax", "public_domain": "public domain, free to read",
                        "provided": "provided free by the course"}[b["free"]["kind"]]
                if b["free"].get("url"):
                    lines.append(f"  It's {what}:")
                    lines.append(f"  {b['free']['url']}")
                else:
                    lines.append(f"  It's {what}, no need to buy it.")
                continue
            if b["access_code"]:
                tool = b["courseware"] or "the online homework"
                lines.append(f"  Needs an access code for {tool}. A used copy won't include one; buying the code alone from the publisher is often cheapest.")
            if b["custom"]:
                lines.append("  This is a custom edition, usually sold only at the campus bookstore.")
            want = b["edition_asked"] or b["edition_found"]
            if b["older_edition_ok"]:
                lines.append("  The syllabus says an older edition is fine, and those are usually much cheaper.")
            elif b["older_editions"] and not b["access_code"] and want and b["older_editions"][0] >= want - 2:
                lines.append(f"  An older edition ({_ed(b['older_editions'][0])}) is usually much cheaper. Worth asking the professor if it's OK.")
            lib = b.get("library") or {}
            login = links.SCHOOLS.get((result.get("school") or "").lower(), {}).get("login", "campus")
            msg = {
                "open_access": "Free online for anyone (open access):",
                "ebook": f"Free to read online through the library with your {login} login "
                         "(some library ebooks allow only a few readers at once):",
                "timed_loan": f"The library lends it online in short timed loans ({login} login). "
                              "Good for a chapter, not for the whole term:",
                "print": "The library has a print copy (loans can be short if it's on reserve):",
            }.get(lib.get("status"))
            if msg:
                lines.append("  " + msg)
                if lib.get("url"):
                    lines.append(f"  {lib['url']}")
            if b["compare_url"]:
                lines.append("  Compare prices:")
                lines.append(f"  {b['compare_url']}")
        unsure = [b for b in c["books"] if b["kind"] == "book" and not b["free"]
                  and b["confidence"] not in CONFIDENT and b["confidence"] != "skipped"]
        if unsure:
            which = "these" if len(unsure) > 1 else "this one"
            lines.append(f"I couldn't confirm the ISBN for {which}. Match the edition with the bookstore list before buying.")
        if f.get("course_reader") and not any(b["kind"] == "reader" for b in c["books"]):
            lines.append("This course has a course reader. That one is usually only sold through the campus copy shop or bookstore.")
        if f.get("inclusive_access"):
            lines.append("Heads up: the syllabus mentions inclusive/first-day access. You may be billed automatically, so check the opt-out deadline before buying elsewhere.")
        checked = any(b.get("library") for b in c["books"])
        if c["books"] and not checked and any(b["library_url"] and not b["free"] for b in c["books"]):
            first = next(b for b in c["books"] if b["library_url"] and not b["free"])
            lines.append("Library check, in case there's a copy or a reserve:")
            lines.append(first["library_url"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_summary(result):
    """A one-screen text for long lists; the full list goes in a document (to_text)."""
    t = result["totals"]
    buy, code, free, none, ask, optional = [], [], [], [], [], []
    for c in result["courses"]:
        name = c["course"] or "Course"
        if c["state"] == "no_textbook":
            none.append(name)
            continue
        if c["state"] == "not_found":
            ask.append(name)
            continue
        paid = [b for b in c["books"] if not b["free"] and b["status"] in ("required", "unspecified")]
        if not paid:
            if any(not b["free"] for b in c["books"]):
                optional.append(name)
            else:
                free.append(name)
            continue
        first = paid[0]
        label = first["title"] or "a book"
        if len(paid) > 1:
            label += f" + {len(paid) - 1} more"
        (code if any(b["access_code"] for b in paid) else buy).append(f"{name}: {label}")
    lines = [f"Your {t['courses']} courses: {t['books']} books to look at. Full list with links is in the PDF."]
    if code:
        lines.append("Need an access code (a used book won't have one):")
        lines += [f"- {x}" for x in code]
    if buy:
        lines.append("To buy:")
        lines += [f"- {x}" for x in buy]
    lib_books = [f"{c['course']}: {b['title']}" for c in result["courses"] for b in c["books"]
                 if (b.get("library") or {}).get("status") in ("ebook", "open_access")]
    if lib_books:
        lines.append("Free to read online through your library:")
        lines += [f"- {x}" for x in lib_books]
    if optional:
        lines.append("Only optional books: " + ", ".join(optional))
    if free:
        lines.append("Free: " + ", ".join(free))
    if none:
        lines.append("Nothing to buy: " + ", ".join(none))
    if any(c["flags"].get("inclusive_access") for c in result["courses"]):
        lines.append("Some of these bill you automatically (inclusive access). Check the opt-out deadline before buying elsewhere.")
    if ask:
        lines.append("No book list found for " + ", ".join(ask) + ". Send me a screenshot of the bookstore list?")
    return "\n".join(lines) + "\n"


LIBRARY_STATUSES = ("ebook", "open_access", "timed_loan", "print", "none")


def library_todo(result, limit=8):
    """Books worth checking in the school catalog: paid, not yet checked; required ones first."""
    rows = []
    for c in result["courses"]:
        for b in c["books"]:
            if b["kind"] == "book" and not b["free"] and not b.get("library") and b.get("catalog_search_url"):
                rows.append((STATUS_ORDER.get(b["status"], 1), c["course"], b))
    rows.sort(key=lambda r: r[0])
    return [{"course": course, "title": b["title"], "edition": b["edition_asked"], "url": b["catalog_search_url"]}
            for _, course, b in rows[:limit]]
