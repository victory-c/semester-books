"""Links for the student, and catalog search links Cubbie opens in its own browser. The script never fetches them."""
import urllib.parse

# Catalog view ids (vid) checked by hand on 2026-11-17; search links opened in a browser on 2026-11-18.
SCHOOLS = {
    "berkeley": {
        "name": "UC Berkeley Library",
        "login": "CalNet",
        "catalog": "https://search.library.berkeley.edu/discovery/search?{q}&tab=LibraryCatalog"
                   "&search_scope=MyInstitution&vid=01UCS_BER:UCB&offset=0",
        "search": "https://search.library.berkeley.edu/discovery/search?query=any,contains,{q}&vid=01UCS_BER:UCB",
        "reserves_hint": "Course reserves are listed on the course's bCourses site.",
    },
    "asu": {
        "name": "ASU Library",
        "login": "ASURITE",
        "catalog": "https://search.lib.asu.edu/discovery/search?{q}&tab=LibraryCatalog"
                   "&search_scope=MyInstitution&vid=01ASU_INST:01ASU&offset=0",
        "search": "https://search.lib.asu.edu/discovery/search?query=any,contains,{q}&vid=01ASU_INST:01ASU",
        "reserves_hint": "ASU Library search has a Course Reserves tab; reserves can also show up in Canvas.",
    },
}


def compare_link(isbn=None, title=None, author=None):
    """One price-comparison page the student opens themselves."""
    if isbn:
        return f"https://www.directtextbook.com/isbn/{isbn}"
    q = " ".join(x for x in (title, author) if x)
    return "https://www.directtextbook.com/search.php?" + urllib.parse.urlencode({"query": q}) if q else None


def library_link(school, isbn=None, title=None):
    q = isbn or title
    if not q:
        return None
    s = SCHOOLS.get((school or "").lower())
    if s:
        return s["search"].format(q=urllib.parse.quote(q))
    if isbn:
        return f"https://search.worldcat.org/isbn/{isbn}"
    return "https://search.worldcat.org/search?" + urllib.parse.urlencode({"q": title})


def reserves_hint(school):
    s = SCHOOLS.get((school or "").lower())
    return s["reserves_hint"] if s else "Ask the library whether the course has a copy on reserve."


def catalog_search_url(school, isbn=None, title=None, author=None):
    """The school's own catalog search for this book (Berkeley, ASU), for Cubbie to open in its browser."""
    s = SCHOOLS.get((school or "").lower())
    if not s or not s.get("catalog"):
        return None
    if isbn:
        q = "query=" + urllib.parse.quote(f"isbn,exact,{isbn}", safe=",")
    elif title:
        q = "query=" + urllib.parse.quote(f"title,contains,{title},AND", safe=",")
        if author:
            surname = author.split(",")[0].split()[-1]
            q += "&query=" + urllib.parse.quote(f"creator,contains,{surname},AND", safe=",")
        q += "&mode=advanced"
    else:
        return None
    return s["catalog"].format(q=q)
