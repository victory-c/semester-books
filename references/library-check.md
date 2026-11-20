# Library check: how to read the catalog

```bash
python3 scripts/tbfind.py --books <working folder>/books.json --school <school> --library-todo
```

It prints up to eight catalog searches, one JSON line each (`course`, `title`, `edition`, `url`), for paid books
not checked yet, required ones first. Open each `url` in the browser, without signing in, and read the results.
Use the browser, not a web search or page read: the catalog is a JavaScript app, and fetching it any other way
returns an empty page. Wait a few seconds for the results to load before reading them.
- Count only results that are the same book: resource type BOOK (not audio or video), the same main title (a
  subtitle may differ), the same edition when one is given, and not a study guide or solutions manual. Open a
  result to see its edition if the list does not show it.
- `open_access`: it says "View open access version" or "open access": free for anyone.
- `timed_loan`: online, but through UC BEARS, "Electronic and Accessible Reserves", "controlled digital lending"
  or a loan of a few hours.
- `ebook`: otherwise online ("Available Online", "View Online", "Full text available").
- `print`: only on a shelf ("Available at <library>").
- `none`: no matching result.
Add what you found to that book in `books.json` as `"library": {"status": "<one of the above>", "url": "<the
result's own page>"}`. Never sign in, borrow or request anything for the student.
