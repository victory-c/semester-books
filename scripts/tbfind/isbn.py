"""ISBN helpers: find, validate and normalise ISBN-10/13 strings."""
import re

# Digits with optional hyphens/spaces, 10 or 13 significant characters, last may be X.
_CANDIDATE = re.compile(r"(?<![\dX])(?:97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx](?![\dX])")


def _digits(s):
    return re.sub(r"[^\dXx]", "", s).upper()


def valid13(s):
    d = _digits(s)
    if len(d) != 13 or not d.isdigit() or not d.startswith(("978", "979")):
        return False
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(d[:12]))
    return (10 - total % 10) % 10 == int(d[12])


def valid10(s):
    d = _digits(s)
    if len(d) != 10 or not d[:9].isdigit() or not (d[9].isdigit() or d[9] == "X"):
        return False
    total = sum((10 - i) * int(c) for i, c in enumerate(d[:9]))
    check = 10 if d[9] == "X" else int(d[9])
    return (total + check) % 11 == 0


def to13(s):
    """Return the ISBN-13 for a valid ISBN-10 or ISBN-13, else None."""
    d = _digits(s)
    if valid13(d):
        return d
    if valid10(d):
        core = "978" + d[:9]
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core))
        return core + str((10 - total % 10) % 10)
    return None


def find_isbns(text):
    """All valid ISBNs in text, as ISBN-13, in order, without duplicates."""
    out = []
    for m in _CANDIDATE.finditer(text):
        isbn = to13(m.group(0))
        if isbn and isbn not in out:
            out.append(isbn)
    return out
