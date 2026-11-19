import json, os, subprocess, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("TBFIND_CACHE", os.path.join(ROOT, ".cache"))
from tbfind import extract, isbn, links, lookup, report

def S(name):
    with open(os.path.join(ROOT, "tests", "samples", name)) as f:
        return f.read()


class Isbn(unittest.TestCase):
    def test_validate_and_convert(self):
        self.assertTrue(isbn.valid13("978-0-13-409341-3"))
        self.assertFalse(isbn.valid13("978-0-13-409341-4"))
        self.assertEqual(isbn.to13("0-393-33764-2"), "9780393337648")
        self.assertIsNone(isbn.to13("1234567890"))

    def test_find_ignores_phone_numbers(self):
        self.assertEqual(isbn.find_isbns("Call 510-642-6000 or ISBN 9781285741550"), ["9781285741550"])


class Extract(unittest.TestCase):
    def test_required_text_with_courseware(self):
        r = extract.extract(S("math1a.txt"))
        b, = r["books"]
        self.assertEqual((b["title"], b["author"], b["edition"], b["status"]),
                         ("Calculus: Early Transcendentals", "James Stewart", 8, "required"))
        self.assertEqual(r["flags"]["courseware"], ["WebAssign"])

    def test_canvas_html_and_inclusive_access(self):
        r = extract.extract(S("bio1a.html"))
        self.assertEqual([b["isbns"] for b in r["books"]], [["9780134093413"]])
        self.assertTrue(r["flags"]["inclusive_access"])
        self.assertEqual(r["flags"]["courseware"], ["Mastering"])

    def test_no_textbook(self):
        r = extract.extract(S("hist7b.txt"))
        self.assertEqual(r["books"], [])
        self.assertTrue(r["flags"]["no_textbook"])

    def test_nothing_listed(self):
        r = extract.extract(S("cs61a.txt"))
        self.assertEqual(r["books"], [])
        self.assertFalse(r["flags"]["no_textbook"])

    def test_citation_style_and_reader(self):
        r = extract.extract(S("polsci.txt"))
        self.assertEqual([(b["title"], b["author"]) for b in r["books"]],
                         [("Leviathan", "Hobbes, T"), ("Second Treatise of Government", "Locke, J")])
        self.assertTrue(r["flags"]["course_reader"])

    def test_isbn_on_its_own_line_and_status(self):
        r = extract.extract(S("econ1.txt"))
        self.assertEqual(r["books"][1]["isbns"], ["9780393337648"])
        self.assertEqual(r["books"][1]["status"], "recommended")


class Report(unittest.TestCase):
    def test_states_and_courseware_attach(self):
        courses = [extract.extract(S(f), f) for f in ("math1a.txt", "hist7b.txt", "cs61a.txt")]
        res = report.build(courses, school="asu", do_lookup=False)
        self.assertEqual([c["state"] for c in res["courses"]], ["found", "no_textbook", "not_found"])
        self.assertTrue(res["courses"][0]["books"][0]["access_code"])
        self.assertEqual(res["totals"]["need_input"], ["cs61a.txt"])
        txt = report.to_text(res)
        self.assertIn("access code for WebAssign", txt)
        self.assertIn("screenshot of the bookstore list", txt)
        self.assertIn("vid=01ASU_INST:01ASU", txt)

    def test_never_guess_isbn_for_missing_edition(self):
        """Edition 9 not listed -> no ISBN from another edition."""
        fake = {
            "search.json": {"docs": [{"key": "/works/W1", "title": "Principles of Economics",
                                      "author_name": ["N. Gregory Mankiw"], "edition_count": 2}]},
            "editions.json": {"entries": [
                {"edition_name": "5th ed.", "publish_date": "2009", "isbn_13": ["9780324589979"],
                 "languages": [{"key": "/languages/eng"}]},
                {"edition_name": "8th edition", "publish_date": "2017", "isbn_13": ["9781305585126"],
                 "languages": [{"key": "/languages/eng"}]}]},
        }
        orig = lookup.get_json
        lookup.get_json = lambda url, ttl=None: next((v for k, v in fake.items() if k in url), {"items": []})
        try:
            b = report.resolve_book({"title": "Principles of Economics", "author": "N. Gregory Mankiw",
                                     "edition": 9, "isbns": []}, None)
        finally:
            lookup.get_json = orig
        self.assertIsNone(b["isbn"])
        self.assertIsNone(b["free"])                      # same title as OpenStax is not enough
        self.assertEqual(b["older_editions"], [8, 5])
        self.assertIn("search.php", b["compare_url"])

    def test_links(self):
        self.assertEqual(links.library_link("nowhere", "9780134093413"),
                         "https://search.worldcat.org/isbn/9780134093413")
        self.assertEqual(links.compare_link("9780134093413"), "https://www.directtextbook.com/isbn/9780134093413")


class Library(unittest.TestCase):
    """Catalog links for Cubbie's browser, and the results it writes back into books.json (no network)."""
    def test_catalog_links(self):
        self.assertEqual(links.catalog_search_url("berkeley", isbn="9780134093413"),
                         "https://search.library.berkeley.edu/discovery/search?query=isbn,exact,9780134093413"
                         "&tab=LibraryCatalog&search_scope=MyInstitution&vid=01UCS_BER:UCB&offset=0")
        u = links.catalog_search_url("asu", title="Linear Algebra Done Right", author="Sheldon Axler")
        self.assertIn("query=title,contains,Linear%20Algebra%20Done%20Right,AND&query=creator,contains,Axler,AND", u)
        self.assertIn("mode=advanced", u)
        self.assertIsNone(links.catalog_search_url("purdue", isbn="9780134093413"))

    def _build(self, lib_by_title, school="berkeley"):
        books = [{"title": t, "isbns": [], "edition": 3, "status": "required", **({"library": l} if l else {})}
                 for t, l in lib_by_title.items()]
        return report.build([{"course": "X 1", "flags": {}, "books": books}], school=school, do_lookup=False)

    def test_todo_then_wording(self):
        res = self._build({"Book A": None, "Book B": None})
        todo = report.library_todo(res)
        self.assertEqual([r["title"] for r in todo], ["Book A", "Book B"])
        self.assertTrue(todo[0]["url"].startswith("https://search.library.berkeley.edu/"))
        res = self._build({"Book A": {"status": "ebook", "url": "https://lib/a"},
                           "Book B": {"status": "timed_loan", "url": "https://lib/b"},
                           "Book C": {"status": "print"}, "Book D": {"status": "open_access", "url": "https://oa/d"},
                           "Book E": {"status": "none"}})
        self.assertEqual(report.library_todo(res), [])
        txt = report.to_text(res)
        self.assertIn("with your CalNet login", txt)
        self.assertIn("short timed loans (CalNet login)", txt)
        self.assertIn("library has a print copy", txt)
        self.assertIn("open access", txt)
        self.assertNotIn("Library check", txt)
        self.assertIn("2 you can read free through the library", txt)

    def test_unchecked_course_keeps_generic_link(self):
        txt = report.to_text(self._build({"Book A": None}))
        self.assertIn("Library check", txt)

    def test_custom_edition_compares_regular_book(self):
        res = report.build([{"course": "MATH 54", "flags": {}, "books": [
            {"title": "Linear Algebra and Differential Equations for UC Berkeley", "author": "Lay", "edition": 2,
             "isbns": ["9780137114030"], "custom": True, "older_edition_ok": True}]}], school="berkeley", do_lookup=False)
        b = res["courses"][0]["books"][0]
        self.assertIn("search.php", b["compare_url"])
        self.assertNotIn("Berkeley", b["compare_url"])
        self.assertTrue(b["compare_url"].endswith("query=Linear+Algebra+and+Differential+Equations+Lay"), b["compare_url"])
        self.assertEqual(report._surname("Lay–Nagle–Saff–Snider"), "Lay")
        self.assertEqual(report._surname("Freeman et al."), "Freeman")
        self.assertIn("searches the regular book", report.to_text(res))

    def test_empty_syllabus_wording(self):
        res = report.build([{"course": "ENGIN 183A", "books": [], "flags": {"syllabus_empty": True}}], do_lookup=False)
        txt = report.to_text(res)
        self.assertIn("syllabus for this course is empty in Canvas", txt)
        self.assertNotIn("No textbook to buy", txt)

    def test_bad_library_status_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"courses": [{"course": "X", "books": [{"title": "T", "library": {"status": "maybe"}}]}]}, f)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "tbfind.py"), "--books", f.name, "--no-lookup"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("library.status", r.stderr)


REAL = os.path.join(ROOT, "tests", "samples", "real", "EXPECTED.json")


@unittest.skipUnless(os.path.exists(REAL), "real syllabi are kept out of the public repo")
class RealSyllabi(unittest.TestCase):
    """15 real public syllabi, hand-labelled. Floors, so changes can't quietly make extraction worse."""
    def test_floor(self):
        import re as _re
        out = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "eval_real.py")],
                             capture_output=True, text=True).stdout.strip().splitlines()[-1]
        found, total = map(int, _re.search(r"books found (\d+)/(\d+)", out).groups())
        extra = int(_re.search(r"extra (\d+)", out).group(1))
        flags_ok, flags_n = map(int, _re.search(r"flags (\d+)/(\d+)", out).groups())
        self.assertGreaterEqual(found / total, 0.70, out)
        self.assertLessEqual(extra, 3, out)
        self.assertGreaterEqual(flags_ok / flags_n, 0.95, out)


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "tbfind.py"), *args, "--no-lookup"],
                              capture_output=True, text=True, cwd=ROOT)

    def test_sample_mode(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "tbfind.py"), "--sample"],
                           capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, HOME=tempfile.mkdtemp()))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("WebAssign", r.stdout)

    def test_exit_codes(self):
        self.assertEqual(self.run_cli("tests/samples/math1a.txt").returncode, 0)
        self.assertEqual(self.run_cli("tests/samples/cs61a.txt").returncode, 3)
        self.assertEqual(self.run_cli("tests/samples/missing.txt").returncode, 2)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"courses": [{"course": "X", "books": [{"author": "nobody"}]}]}, f)
        r = self.run_cli("--books", f.name)
        self.assertEqual(r.returncode, 2)
        self.assertIn("needs a title or an isbn", r.stderr)

    def test_agent_fields_on_real_list(self):
        r = self.run_cli("--books", "tests/samples/agent_real_books.json")
        self.assertEqual(r.returncode, 0, r.stderr)
        for want in ("No textbook to buy", "Course reader: usually sold only", "paid online access, bought separately",
                     "older edition is fine", "custom edition", "inclusive/first-day access"):
            self.assertIn(want, r.stdout)

    def test_summary_mode(self):
        out = os.path.join(tempfile.mkdtemp(), "full.txt")
        r = self.run_cli("--books", "tests/samples/agent_real_books.json", "--full-text", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(len(r.stdout.splitlines()), 25, r.stdout)
        self.assertIn("Need an access code", r.stdout)
        self.assertIn("Nothing to buy: berkeley_cs70", r.stdout)
        with open(out) as f:
            self.assertIn("Compare prices", f.read())

    def test_agent_book_list(self):
        r = self.run_cli("--books", "tests/samples/agent_books.json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("access code for Mastering", r.stdout)
        self.assertIn("vid=01UCS_BER:UCB", r.stdout)


if __name__ == "__main__":
    unittest.main()
