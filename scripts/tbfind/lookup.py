"""Identify the exact book and edition (Open Library) and free open copies (OpenStax).

Only public, keyless endpoints. Every response is cached on disk so a book looked
up once costs nothing the second time (the same course, the next classmate).
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

# Open Library allows ~1 request/s without contact details and ~3/s with an app contact email in the User-Agent.
# Adding a company contact address here would make cold runs about three times faster.
UA = "semester-books/0.1 (Cubbie Skill; low volume)"
GOOGLE_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY")   # optional; only used to find new editions Open Library lacks
# Cache lives under HOME so it survives restarts in the Cubbie sandbox.
CACHE_DIR = os.environ.get("TBFIND_CACHE", os.path.join(os.path.expanduser("~"), ".cache", "semester-books"))
CACHE_TTL = 7 * 24 * 3600   # book metadata barely changes
_last_call = [0.0]
OFFLINE = os.environ.get("TBFIND_OFFLINE") == "1"
TIMEOUT = 6            # seconds per request
BUDGET = 60            # seconds of network time for one run; after that, finish with what we have
_state = {"down": None, "started": None}   # down: why the network was given up on (shared by the whole run)


class LookupError_(Exception):
    pass


def network_down():
    """Why lookups were skipped in this run (None if they all went through)."""
    return _state["down"]


def _give_up(reason):
    if not _state["down"]:
        _state["down"] = reason
    raise LookupError_(reason)


def _cache_path(url):
    import hashlib
    return os.path.join(CACHE_DIR, hashlib.sha1(url.encode()).hexdigest() + ".json")


def _read_cache(path):
    try:
        with open(path) as f:
            hit = json.load(f)
        return hit if isinstance(hit, dict) and "t" in hit else None
    except (OSError, ValueError):
        return None   # missing or half-written: treat as not cached


def _write_cache(path, data, url):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump({"t": time.time(), "url": url, "data": data}, f)
        os.replace(tmp, path)   # atomic, so a parallel run never reads half a file
    except OSError:
        pass   # a cache we can't write only costs speed


def get_json(url, ttl=CACHE_TTL):
    path = _cache_path(url)
    hit = _read_cache(path)
    if hit and (OFFLINE or time.time() - hit["t"] < ttl):
        return hit["data"]
    try:
        return _fetch(url, path)
    except LookupError_:
        if hit:
            return hit["data"]   # stale beats nothing when the network is gone
        raise


def _fetch(url, path):
    if OFFLINE:
        _give_up("offline")
    if _state["down"]:
        raise LookupError_(_state["down"])
    now = time.time()
    _state["started"] = _state["started"] or now
    if now - _state["started"] > BUDGET:
        _give_up("too slow")
    wait = 1.05 - (now - _last_call[0])   # Open Library: about 1 request/second, counted from each start
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            # 429 or a server error: stop for this run instead of retrying every book.
            _give_up(f"HTTP {e.code}")
        data = None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        _give_up(type(e).__name__)
    _write_cache(path, data, url)
    return data


# ---------- editions ----------

_ORD = {w: i for i, w in enumerate(
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth "
    "fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth".split(), 1)}


def edition_number(name):
    if not name:
        return None
    s = name.lower()
    m = re.search(r"(\d{1,2})\s*(?:st|nd|rd|th)?\b", s)
    if m:
        return int(m.group(1))
    for w, n in _ORD.items():
        if re.search(r"\b" + w + r"\b", s):
            return n
    return None


def _year(date):
    m = re.search(r"(1[89]\d\d|20\d\d)", date or "")
    return int(m.group(1)) if m else None


def _edition_row(e):
    isbn13 = (e.get("isbn_13") or [None])[0]
    if not isbn13 and e.get("isbn_10"):
        from .isbn import to13
        isbn13 = to13(e["isbn_10"][0])
    return {
        "isbn13": isbn13,
        "edition": edition_number(e.get("edition_name")),
        "edition_name": e.get("edition_name"),
        "year": _year(e.get("publish_date")),
        "format": e.get("physical_format"),
        "publisher": (e.get("publishers") or [None])[0],
        "english": (not e.get("languages")) or any(l.get("key") == "/languages/eng" for l in e["languages"]),
    }


def work_editions(work_key, limit=100):
    data = get_json(f"https://openlibrary.org{work_key}/editions.json?limit={limit}") or {}
    rows = [_edition_row(e) for e in data.get("entries", [])]
    return [r for r in rows if r["isbn13"]]


def _pick_edition(rows, want):
    """Return (chosen row or None, older edition numbers).

    If an edition was asked for and is not listed, return None rather than
    another edition's ISBN: a wrong ISBN is worse than no ISBN.
    """
    rows = [r for r in rows if r["english"]] or rows
    if not rows:
        return None, []
    if want:
        match = [r for r in rows if r["edition"] == want]
        older = sorted({r["edition"] for r in rows if r["edition"] and r["edition"] < want}, reverse=True)
        if not match:
            return None, older
        match.sort(key=lambda r: (r["format"] or "").lower() not in ("hardcover", "paperback"))
        return match[0], older
    dated = sorted(rows, key=lambda r: (r["year"] or 0, r["edition"] or 0), reverse=True)
    return dated[0], []


def identify(book):
    """Add Open Library facts to one extracted book. Never raises on network errors."""
    out = {"match": None, "confidence": "none", "work_key": None, "authors": [],
           "edition_found": None, "older_editions": [], "public_domain_url": None, "notes": []}
    try:
        if book.get("isbns"):
            isbn = book["isbns"][0]
            ed = get_json(f"https://openlibrary.org/isbn/{isbn}.json")
            doc = None
            # The search call only adds author names (and a public-domain check, moot for a book with an ISBN
            # and a known author), so skip it when we already have both.
            if not (ed and book.get("author")):
                s = get_json("https://openlibrary.org/search.json?" + urllib.parse.urlencode(
                    {"isbn": isbn, "fields": "key,title,author_name,ebook_access", "limit": 1}))
                doc = (s or {}).get("docs", [None])[0] if s and s.get("docs") else None
            if ed:
                row = _edition_row(ed)
                row["isbn13"] = isbn
                out.update(match=row, confidence="isbn",
                           work_key=(ed.get("works") or [{}])[0].get("key"))
                out["title"] = ed.get("title")
            else:
                out["notes"].append("ISBN not in Open Library; using it as given")
                out.update(match={"isbn13": isbn, "edition": book.get("edition")}, confidence="isbn-unverified")
            if doc:
                out["authors"] = doc.get("author_name", [])[:3]
                out["work_key"] = out["work_key"] or doc.get("key")
                out["title"] = out.get("title") or doc.get("title")
                if doc.get("ebook_access") == "public":
                    out["public_domain_url"] = "https://openlibrary.org" + doc["key"]
            if out["work_key"] and book.get("edition"):
                _, older = _pick_edition(work_editions(out["work_key"]), book["edition"])
                out["older_editions"] = older[:2]
        elif book.get("title"):
            q = {"title": book["title"], "fields": "key,title,author_name,edition_count,ebook_access", "limit": 3}
            if book.get("author"):
                q["author"] = book["author"].split(",")[0].split(" and ")[0].split("&")[0].strip()
            s = get_json("https://openlibrary.org/search.json?" + urllib.parse.urlencode(q)) or {}
            docs = s.get("docs", [])
            if not docs:
                g = google_edition(book["title"], book.get("author"), book.get("edition")) if (
                    GOOGLE_KEY and book.get("edition")) else None
                if g:
                    out.update(match=g, confidence="title+edition", title=book["title"])
                else:
                    out["notes"].append("no Open Library match for the title")
                return out
            docs.sort(key=lambda d: d.get("edition_count", 0), reverse=True)
            doc = docs[0]
            out.update(work_key=doc["key"], authors=doc.get("author_name", [])[:3], title=doc.get("title"))
            if doc.get("ebook_access") == "public":
                out["public_domain_url"] = "https://openlibrary.org" + doc["key"]
            want = book.get("edition")
            chosen, older = None, []
            if not want:
                # No edition asked: we will not show an unconfirmed ISBN anyway, so skip the editions list.
                out.update(confidence="title-only")
                out["notes"].append("syllabus gives no edition")
                return out
            for d in docs[:2]:   # Open Library often splits one book into several "works"
                c, o = _pick_edition(work_editions(d["key"]), want)
                older = older or o
                if c and (not want or c["edition"] == want):
                    chosen = c
                    break
            if not chosen and want and GOOGLE_KEY:
                g = google_edition(book["title"], book.get("author"), want)
                if g:
                    chosen = g
            if chosen and want:
                out.update(match=chosen, older_editions=older[:2], confidence="title+edition")
            else:
                out.update(match=chosen if not want else None, older_editions=older[:2], confidence="title-only")
                out["notes"].append(f"couldn't confirm the ISBN for edition {want}" if want
                                    else "syllabus gives no edition")
    except LookupError_ as e:
        out["notes"].append("lookup failed: " + str(e))
    return out


# ---------- Google Books (optional) ----------

def google_edition(title, author, want):
    """Find the ISBN-13 of edition `want` on Google Books. Needs GOOGLE_BOOKS_API_KEY; None if unsure."""
    if not GOOGLE_KEY or not want:
        return None
    q = f'intitle:"{title}"' + (f" inauthor:{author.split(',')[0].split()[-1]}" if author else "")
    url = "https://www.googleapis.com/books/v1/volumes?" + urllib.parse.urlencode(
        {"q": q, "maxResults": 20, "printType": "books", "key": GOOGLE_KEY})
    try:
        data = get_json(url) or {}
    except LookupError_:
        return None
    for item in data.get("items", []):
        v = item.get("volumeInfo", {})
        label = " ".join(x for x in (v.get("title"), v.get("subtitle")) if x)
        if edition_number(re.search(r"\b\w+\s+edition\b|\b\d{1,2}(?:st|nd|rd|th)?\s*ed\b", label, re.I).group(0)
                          if re.search(r"\b\w+\s+edition\b|\b\d{1,2}(?:st|nd|rd|th)?\s*ed\b", label, re.I) else None) != want:
            continue
        isbn = next((i["identifier"] for i in v.get("industryIdentifiers", []) if i.get("type") == "ISBN_13"), None)
        if isbn:
            return {"isbn13": isbn, "edition": want, "edition_name": label, "year": _year(v.get("publishedDate")),
                    "format": None, "publisher": v.get("publisher"), "english": True, "source": "google"}
    return None


# ---------- OpenStax ----------

def _norm(t):
    t = re.sub(r"\(.*?\)", " ", (t or "").lower())
    t = re.sub(r"\b(\d+e|\d+(st|nd|rd|th)? edition|2e|3e)\b", " ", t)
    return " ".join(re.findall(r"[a-z0-9]+", t))


def openstax_catalog():
    url = ("https://openstax.org/apps/cms/api/v2/pages/?type=books.Book&fields=title,book_state,"
           "print_isbn_13,digital_isbn_13,webview_rex_link&limit=250")
    data = get_json(url, ttl=30 * 24 * 3600) or {}
    return [b for b in data.get("items", []) if b.get("book_state") in ("live", "new_edition_available")]


def openstax_match(title, isbns=(), allow_title=False):
    """The same book on OpenStax: by ISBN, or by exact title only when the syllabus itself points to OpenStax."""
    try:
        books = openstax_catalog()
    except LookupError_:
        return {"unchecked": True}   # catalog unreachable: the caller decides what to tell the student
    want = _norm(title)
    for b in books:
        ids = {b.get("print_isbn_13"), b.get("digital_isbn_13")}
        if any(i and i.replace("-", "") in isbns for i in ids) or (allow_title and want and _norm(b["title"]) == want):
            slug = b.get("meta", {}).get("slug")
            return {"title": b["title"],
                    "url": b.get("webview_rex_link") or (f"https://openstax.org/details/books/{slug}" if slug else None)}
    return None
