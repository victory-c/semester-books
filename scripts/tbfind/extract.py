"""Find the books a syllabus asks for.

This is the rule-based fallback. In the Cubbie Skill the agent reads the syllabus
and writes the book list itself; this module then double-checks it (ISBNs, access
codes, inclusive access) and is what runs when no model is available.
"""
import html
import re

from .isbn import find_isbns

# Courseware that needs a paid, single-use access code.
ACCESS_CODE_TOOLS = [
    "MyLab", "Mastering", "Revel", "Pearson+", "Connect", "ALEKS", "SmartBook",
    "WebAssign", "MindTap", "OWLv2", "Cengage Unlimited", "WileyPLUS", "Achieve",
    "Sapling", "LaunchPad", "zyBooks", "Top Hat", "Perusall", "Packback",
    "Macmillan Learning", "Norton Illumine", "InQuizitive", "Knewton",
]
_TOOL_RE = re.compile(r"\b(" + "|".join(re.escape(v) for t in ACCESS_CODE_TOOLS for v in (t, t.upper())) + r")\b")
_TOOL_NAME = {t.upper(): t for t in ACCESS_CODE_TOOLS}


def _tool(m):
    return _TOOL_NAME.get(m.group(1).upper(), m.group(1))

INCLUSIVE_RE = re.compile(
    r"inclusive access|first day(?:™)? (?:complete|access|program)|day one access|"
    r"equitable access|immediate access|auto-?access|textbook fee (?:is|will be) (?:charged|billed)|"
    r"automatically bill|billed (?:directly )?to your (?:student |ASU )?account|bill (?:to )?your (?:ASU |student )?account|"
    r"opt[- ]out (?:of|by|deadline|before)",
    re.I,
)
NO_BOOK_RE = re.compile(
    r"no (?:required )?(?:textbook|text ?book|text)s? (?:is |are )?(?:required|needed|for this course)|"
    r"there is no (?:required )?(?:textbook|text)|"
    r"(?:you )?(?:do not|don't) need to (?:buy|purchase) (?:a |any )?(?:textbook|book)s?|"
    r"all (?:required )?readings (?:will be|are) (?:posted|available|provided) (?:on|in|via) (?:bcourses|canvas|the course site)",
    re.I,
)
READER_RE = re.compile(r"course reader|coursepack|course pack|reader is available|a reader will be used|"
                       r"reader (?:is|will be) (?:required|sold)", re.I)
SEE_STORE_RE = re.compile(r"see (?:the )?(?:class )?syllabus or .{0,80}(?:bookstore|calstudentstore|textbooks)|"
                          r"check (?:with )?the (?:campus )?bookstore|textbook lookup", re.I)
OPENSTAX_URL = re.compile(r"openstax\.org/(?:details/)?books/([a-z0-9\-]+)", re.I)
_BOOK_WORDS = re.compile(r"\b(text ?books?|texts|books?|materials|readings|book information)\b", re.I)
_PROSE_START = re.compile(r"^\W*(note|if|you|this|it|please|we|i|use|there|they|students?|the (?:required|following)|"
                          r"for|in|all|each|when|soon|after|because|as|feel|online homework|homework)\b", re.I)
_POSSESSIVE = re.compile(r"^\W*((?:[A-Z][\w.\-]*\s+){0,3}[A-Z][\w\-]+)[’']s\s+(.+)$")
_LABEL = re.compile(r"^(?:(?:lecture|lab|laboratory|main|required|course|primary|recommended|optional|supplementary)\s+)?"
                    r"(?:text ?book|text|book|manual|reader)s?\s*:\s*", re.I)
_NOT_A_BOOK = re.compile(r"^\W*(short story|story|essay|article|poem|film|movie|video|podcast|website)\b", re.I)
OER_RE = re.compile(r"openstax|libretexts|open textbook|open educational resource|\bOER\b|free online textbook", re.I)
RESERVE_RE = re.compile(r"(?:on|course) reserve|reserve desk|library reserve", re.I)

_HEADING_BOOKS = re.compile(
    r"^\W*(?P<status>required|recommended|optional|supplementary|suggested)?\s*"
    r"(?:course\s+)?(?:text\s*books?|texts?|readings?|books?|materials?|course materials|"
    r"reading materials?|required materials?)\s*(?:and\s+(?:materials?|software|resources))?\W*$",
    re.I,
)
_OTHER_HEADINGS = re.compile(
    r"^\W*(grading|grades|assessment|evaluation|schedule|course schedule|calendar|attendance|"
    r"office hours|instructor|contact|course description|description|overview|learning (?:outcomes|objectives)|"
    r"objectives|policies|course policies|exams?|homework|assignments|prerequisites?|academic (?:integrity|honesty)|"
    r"accommodations?|disability|week \d+|lectures?|sections?|discussion|labs?|technology|software)\b.{0,40}$",
    re.I,
)
_EDITION_RE = re.compile(
    r"\b(?P<n>\d{1,2})(?:st|nd|rd|th)?\s*(?:ed\.?|edition)\b|\bedition\s*(?P<n2>\d{1,2})\b|\b(?P<n3>\d{1,2})e\b",
    re.I,
)
_STATUS_WORDS = re.compile(r"\b(required|recommended|optional|suggested|supplementary)\b", re.I)


def clean_text(raw):
    """Turn Canvas HTML or plain text into tidy lines."""
    text = raw
    if "<" in text and ">" in text:
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
        text = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|tr)>", "\n", text)
        text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
        text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).replace(" ", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return [ln for ln in lines]


def _strip_prefix(line):
    return re.sub(r"^\s*(?:[A-Z]|\d{1,2}|[IVX]{1,4})[.)]\s+", "", line)


def _is_book_heading(line):
    l = _strip_prefix(line)
    if _HEADING_BOOKS.match(l):
        return True
    words = l.split()
    return (len(l) <= 80 and len(words) <= 9 and bool(_BOOK_WORDS.search(l)) and not find_isbns(l)
            and not re.search(r"\b(is|are|will|should|can|must|was)\b", l, re.I) and not l.rstrip().endswith("."))


def _is_heading(line):
    l = _strip_prefix(line)
    short = len(l) <= 70
    return _is_book_heading(line) or (short and (bool(_OTHER_HEADINGS.match(l))
                                                 or (l.endswith(":") and len(l) <= 40)))


def _norm_status(word):
    if not word:
        return None
    word = word.lower()
    if word in ("suggested", "supplementary"):
        return "optional" if word == "supplementary" else "recommended"
    return word


_ORDINALS = ("first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth "
             "fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth").split()
_WORD_EDITION = re.compile(r"\b(" + "|".join(_ORDINALS) + r")\s+(?:ed\.|edition)\b", re.I)


def _edition(line):
    m = _EDITION_RE.search(line)
    if m:
        return int(m.group("n") or m.group("n2") or m.group("n3"))
    w = _WORD_EDITION.search(line)
    return _ORDINALS.index(w.group(1).lower()) + 1 if w else None


def _title_author(line):
    """Best-effort split of a citation line into title and author."""
    s = re.sub(r"^\s*(?:[-*•▪◦~]|\d+[.)])\s*", "", line)
    s = re.sub(_LABEL, "", s)
    s = re.split(r"\s+or the\s+", s)[0]
    s = re.sub(r"\(?\bISBN(?:-1[03])?\b\s*:?\s*[\dXx\-\s]{10,17}\)?", "", s, flags=re.I)
    s = re.sub(r"\b97[89][\d\-\s]{10,14}\b", "", s)
    s = _STATUS_WORDS.sub("", s)
    s = s.strip(" .,;:-–—()")
    author = None
    apa = re.match(r"^(.{3,80}?)\.?\s*\((?:19|20)\d\d\)\.\s*(.+)$", s)
    pos = _POSSESSIVE.match(s)
    m = re.search(r"\bby\s+([A-Z][^,;()]+?)(?:[,;(]|$)", s)
    if apa and not m:
        author, title = apa.group(1).strip(" .,"), apa.group(2)
        title = re.split(r"\.\s", title)[0]
    elif pos and not m:
        author, title = pos.group(1).strip(), re.split(r"\s*[(—–]", pos.group(2))[0]
    elif m:
        author = m.group(1).strip(" .")
        title = s[: m.start()].strip(" ,.;:-–—\"'“”")
    else:
        # "Lastname, F. (Year). Title." or "Lastname & Other, Title, ..."
        m = re.match(r"^([A-Z][A-Za-z'\-]+,\s*[A-Z]\.(?:\s*[A-Z]\.)?(?:\s*(?:&|and)\s*[A-Z][A-Za-z'\-]+(?:,\s*[A-Z]\.)?)*)"
                     r"\s*(?:\(\d{4}\))?(?:[.,:]\s+|\s+)(.+)$", s)
        m2 = re.match(r"^((?:[A-Z][a-z]+\.?\s+){1,2}[A-Z][A-Za-z'\-]+(?:\s*(?:&|and)\s*(?:[A-Z][a-z]+\.?\s+){1,2}[A-Z][A-Za-z'\-]+)*)"
                      r",\s+(.+)$", s)
        if m and len(m.group(1)) < 60:
            author, title = m.group(1).strip(" .,"), m.group(2)
        elif m2 and len(m2.group(1)) < 50 and len(m2.group(2)) > 3:
            author, title = m2.group(1).strip(), m2.group(2)
        else:
            title = s
        # "Leviathan. Penguin Classics." -> drop the publisher after the first sentence.
        if ". " in title and not re.search(r"\b(?:Vol|No|Mr|Dr|St)\. ", title):
            title = title.split(". ")[0]
    title = re.split(r",\s*(?:\d{1,2}(?:st|nd|rd|th)?\s*ed|edition|publisher|pub\.|isbn)", title, flags=re.I)[0]
    title = re.sub(r"\s*\(\s*\d{1,2}(?:st|nd|rd|th)?\s*ed(?:ition|\.)?\s*\)", "", title, flags=re.I)
    title = re.sub(_WORD_EDITION, "", re.sub(_EDITION_RE, "", title)).strip(" ,.;:-–—\"'“”")
    return (title or None), author


def _looks_like_book(line):
    if len(line) < 8 or not re.search(r"[A-Za-z]{3}", line):
        return False
    if find_isbns(line) or _edition(line):
        return True
    if re.search(r"\bby\s+[A-Z]", line) or re.search(r"\b(Pearson|McGraw|Cengage|Wiley|Norton|Macmillan|Oxford|"
                                                   r"Cambridge|Springer|Elsevier|OpenStax|Sage|Routledge|Penguin|"
                                                   r"Vintage|Princeton|MIT Press|Freeman|Sinauer|Bedford|Hackett|Dover|Knopf|Harper|"
                                                   r"Basic Books|Yale|Harvard|Chicago|Stanford|Bantam|Signet|"
                                                   r"University Press|Press)\b", line):
        return True
    if re.match(r"^\W*[A-Z][A-Za-z'\-]+,\s*[A-Z]\.", line) or re.search(r"\((?:19|20)\d\d\)\.", line):
        return True
    pos = _POSSESSIVE.match(line)
    if pos and not _NOT_A_BOOK.match(pos.group(2)) and not re.search(
            r"\b(program|site|website|policy|page|account|office|portal)\b|please", line, re.I):
        return True
    return False


def _is_prose(line):
    if find_isbns(line):
        return False
    if _PROSE_START.match(line):
        return True
    cues = re.search(r"\bby\s+[A-Z]|\((?:19|20)\d\d\)|\bedition\b|\bed\.|press\b|publish", line, re.I)
    return len(line.split()) >= 16 and not cues


def extract(raw_text, course=None):
    """Return {'course', 'books': [...], 'flags': {...}} from a syllabus."""
    lines = clean_text(raw_text)
    full = "\n".join(lines)
    books = []
    section_status = None
    in_section = False

    def add(line, status, title=None, author=None):
        isbns = find_isbns(line)
        if title is None:
            title, author = _title_author(line)
        tool = _TOOL_RE.search(line)
        needs_code = bool(tool) or bool(re.search(r"access code|access card", line, re.I))
        word = _STATUS_WORDS.search(line)
        books.append({
            "raw": line,
            "title": title,
            "author": author,
            "edition": _edition(line),
            "isbns": isbns,
            "status": _norm_status(word.group(1)) if word else (status or "unspecified"),
            "access_code": needs_code,
            "courseware": _tool(tool) if tool else None,
        })

    section_start = 0
    for i, line in enumerate(lines):
        if not line:
            continue
        if _is_heading(line):
            in_section = _is_book_heading(line)
            word = _STATUS_WORDS.search(line)
            section_status = _norm_status(word.group(1)) if (in_section and word) else None
            section_start = len(books)
            continue
        if in_section and re.search(r"\bnot required\b", line, re.I):
            section_status = "recommended" if "recommend" in line.lower() else "optional"
            for b in books[section_start:]:
                b["status"] = section_status
            continue
        prev = books[-1] if books else None
        # An "ISBN: ..." line (or a wrapped "Learning. ISBN ...") belongs to the book above it.
        cur_title = _title_author(line)[0]
        if prev and find_isbns(line) and (re.match(r"^\W*ISBN", line, re.I) or
                                          (not prev["isbns"] and (not cur_title or len(cur_title.split()) <= 2))):
            for isbn in find_isbns(line):
                if isbn not in prev["isbns"]:
                    prev["isbns"].append(isbn)
            continue
        if in_section and line.count(";") >= 2:
            parts = [p.strip() for p in line.split(";")]
            pairs = [re.match(r"^([A-Z][\w'’\-]+),\s+(.+)$", p) for p in parts]
            if sum(1 for m in pairs if m) >= 2:
                for p, m in zip(parts, pairs):
                    if m:
                        add(p, section_status, m.group(2).strip(" ."), m.group(1))
                continue
        if _LABEL.match(line) and _looks_like_book(line):
            add(line, section_status)
            continue
        if in_section and _is_prose(line):
            continue
        pos = _POSSESSIVE.match(line)
        if pos and _NOT_A_BOOK.match(pos.group(2)):
            continue
        if (in_section and _looks_like_book(line)) or (not in_section and find_isbns(line)):
            add(line, section_status)

    # An OpenStax link anywhere in the syllabus names a free book.
    if not any("openstax" in (b["raw"] or "").lower() for b in books):
        for slug in dict.fromkeys(m.group(1).lower() for m in OPENSTAX_URL.finditer(full)):
            add("openstax " + slug, None, slug.replace("-", " ").title().replace(" 2E", " 2e").replace(" 3E", " 3e"), None)

    # Drop repeats (the same book listed twice).
    seen, unique = set(), []
    for b in books:
        key = (" ".join(re.findall(r"[a-z0-9]+", (b["title"] or "").lower())), b["edition"])
        if key in seen and key[0]:
            continue
        seen.add(key)
        unique.append(b)
    books[:] = unique

    flat = re.sub(r"\s+", " ", full)   # phrases broken across lines
    tools = sorted(set(_tool(m) for m in _TOOL_RE.finditer(flat)))
    reader = False
    for m in READER_RE.finditer(flat):
        if not re.search(r"\bno\b[^.]{0,50}$", flat[max(0, m.start() - 55):m.start()], re.I):
            reader = True
            break
    flags = {
        "courseware": tools,
        "inclusive_access": bool(INCLUSIVE_RE.search(flat)),
        "no_textbook": bool(NO_BOOK_RE.search(flat)) and not books,
        "see_bookstore": bool(SEE_STORE_RE.search(flat)) and not books,
        "course_reader": reader,
        "mentions_oer": bool(OER_RE.search(full)),
        "mentions_reserve": bool(RESERVE_RE.search(full)),
    }
    return {"course": course, "books": books, "flags": flags}
