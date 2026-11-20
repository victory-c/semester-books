---
name: semester-books
description: Use when a student asks what books or materials their courses need, whether to buy a book, or right after Canvas first syncs; lists books, editions, access codes, free copies and price links. It reads the syllabi in Canvas, confirms editions, flags access codes and inclusive access, finds free and library copies, and links to a price-comparison page.
---

# Semester Books

Finding out which books a term needs means opening every syllabus, working out the edition and checking for access
codes. This Skill does that from the student's Canvas in one go and texts back one short list. It does not compare
prices itself: it links to a price-comparison page and the student checks there.

## When to use

- "What books do I need this semester?"
- "Do I have to buy anything for CHEM 1A?"
- "Is there a textbook for my econ class?"
- Right after the student connects Canvas and the first sync is done, offer it once: "Want me to list the books for
  your classes this term?"
- A photo of a bookstore book list or a syllabus.

Do not use it to summarize a book or make study notes. Never use it to find unauthorized copies (see "Legal routes
only").

## Steps

1. **Pick the courses.** Use the courses the student named, otherwise all current-term courses in Canvas. If they are
   asking about next term, use next term's courses if Canvas already shows them.
   If Canvas is not connected, ask the student to connect it, or to send a screenshot of their bookstore book list or
   their course codes (default: "Send me a screenshot of your bookstore list"). Then stop and wait.

2. **Read each course's book list.** For each course, read the syllabus page, and search the course files and pages
   for "syllabus", "textbook", "required materials" or "course materials"; read the PDF if the syllabus is a file.
   Save the syllabus text of each course in the working folder.

3. **Write the book list file** `books.json` in the working folder (format below). Write down only what the
   syllabus says; never guess an ISBN or an edition, leave it out. For each course:
   - Every book the student is told to get: title, author (the first author's surname is enough), edition,
     ISBN, and `status` from the syllabus wording (required, recommended, optional; `unspecified` if it does not
     say). Include lab manuals and study guides the syllabus names. Include a book that appears only in the
     reading schedule, as `unspecified`.
   - `access_code: true` and `courseware` when the book comes with paid online homework (WebAssign, MyLab,
     Mastering, Connect, ALEKS, Achieve...), even if the syllabus says "no access code" but the platform is
     billed or required.
   - A paid platform that is not a book (Labflow, iClicker, Aktiv, an access card sold alone): its own entry with
     `kind: "courseware"`. A course reader or coursepack: an entry with `kind: "reader"`.
   - `older_edition_ok: true` when the syllabus says earlier editions are fine; `custom: true` for a school-specific
     custom edition.
   - A book the course gives out free (posted in Canvas, linked on archive.org or the publisher's open site):
     `provided: true`, with `url` if the syllabus gives one.
   - Leave out free short readings (articles, short stories, handouts posted in Canvas).
   - Course-level facts: `no_textbook: true` when the syllabus says there is no book to buy;
     `syllabus_empty: true` when the course's syllabus in Canvas has no content (only a title) and you found no
     syllabus file, so you cannot tell (never guess "no textbook" from that);
     `inclusive_access: true` when materials are billed automatically (inclusive access, first-day access, "the
     bookstore will bill your account").
   - Put the course's syllabus text in `syllabus_text` if it is short enough; the script double-checks it. A course
     with no books still goes in, with an empty `books` list.

4. **Check the student's library** (Berkeley and ASU; for other schools skip to step 5). From this Skill's folder:

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

5. **Run the script** for the reply. Pass `--school berkeley` or `--school asu` for those schools, otherwise leave
   `--school` out:

   ```bash
   python3 scripts/tbfind.py --books <working folder>/books.json --school <school> --json <working folder>/result.json
   ```

   It checks each ISBN and edition against Open Library, finds free OpenStax and public-domain copies, turns your
   library findings into plain lines, flags access codes, inclusive access and course readers, and prints the reply
   text. It needs no setup or key (Python standard library only).

   Then send the script's text as the reply (see "Replies"). You may translate it into the student's language,
   but do not shorten it or drop anything: every price-comparison link, library link and warning stays. Use only
   the ISBNs, links and facts it printed.

6. **Courses with no book list.** The script names them ("couldn't find a book list"). Ask for a screenshot of the
   bookstore list for those courses; when it arrives, read it, add the books to `books.json` and run steps 4 and 5 again.

7. **Next term not in Canvas yet.** Courses often appear in Canvas only days before the term. Offer one check-in and
   suggest a default: "Want me to check again when your spring courses show up? I'll look every few days until
   then." Create it only after the student agrees. Word it so it makes sense later on its own: "Semester Books: check
   Canvas for <term> courses; for any course whose syllabus is now posted, list its books and text only the new ones."

## Book list file

```json
{
  "school": "asu",
  "courses": [
    {
      "course": "BIO 181",
      "inclusive_access": true,
      "books": [
        {"title": "Biological Science", "author": "Freeman", "edition": 8, "status": "required",
         "access_code": true, "courseware": "Mastering"},
        {"title": "Investigating Biology Lab Manual", "author": "Morgan", "edition": 9, "status": "required"}
      ]
    },
    {"course": "CSE 110", "no_textbook": true, "books": []},
    {"course": "LAW 202", "books": [{"kind": "reader", "title": "Course reader", "status": "required"}]}
  ]
}
```

- Each book needs a `title` or an `isbn`. `edition` is a number. `status` is `required`, `recommended`, `optional`
  or `unspecified`. `kind` is `book` (default), `courseware` or `reader`.
- If a course has `syllabus_text` and no books, the script tries to find the books itself.
- `python3 scripts/tbfind.py --sample` shows the output without network or saved state.

## Replies

In every answer about a book the student may need to buy, including a short answer about one course and a reply
to "send me a free PDF", include that book's price-comparison link from the script, on its own line. When there is
no free copy, say what the cheapest legal routes are (an older edition if the syllabus allows it, the library, the
comparison link) instead of stopping at "I couldn't find one".

Keep it short and plain, no Markdown. One course per block, links on their own line. Lead with the count of books
and how many are free. If there are more than six courses or twelve books, add `--full-text <working folder>/full.txt`
to the run command: it prints a one-screen summary to text, and writes the full list to `full.txt`. Make a PDF from
`full.txt`, send it, then text the summary. If you can't make a PDF in the sandbox (pypdf can't write one from text),
send `full.txt` as a file instead. Replies over about 4,000 characters are split into several bubbles, so prefer the
summary mode over one long text.

When the library has an ebook, lead that book with it: it is free with the student's campus login. Say plainly
when it is only a short timed loan, and that some library ebooks allow only a few readers at once.

Always pass on these, in one line each:
- An access code is needed: a used book will not include one.
- The syllabus mentions inclusive or first-day access: the student may be billed automatically, so check the opt-out
  deadline before buying elsewhere. Opting out is the student's own step.
- The script could not confirm the ISBN: check it against the bookstore list before buying.

If the student asks whether an older edition is OK, offer to draft an email to the professor; the student sends it.

## Legal routes only

Only point to the course's own materials, free open textbooks, public-domain copies, the library, and legitimate
sellers through the comparison link. Never link to or describe "free PDF" sites, shadow libraries or file-sharing
posts. If the student asks for one, say in one line that you can only point to legal copies and carry on.
Never buy, rent or check out anything for the student.

## When something fails

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 0 | Done (some courses may still need a screenshot) | Reply; ask for screenshots for the courses it names |
| 2 | `books.json` is missing, not JSON, or a field is wrong (the message names it) | Fix the file and run again; do not show the error to the student |
| 3 | No books found in any course | Ask for a screenshot of the bookstore book list or the course codes |
| 1 | Unexpected error (one line on stderr) | Run once more; if it fails again, tell the student you couldn't finish the book list right now |

If Open Library is unreachable, rate-limited or slow, the script stops calling it for that run (it gives the network
about a minute in total), still prints the list, and says plainly that some editions and ISBNs aren't confirmed. Send
that line as it is. Don't rerun in a loop; offer to check again later.
Never fill in an ISBN or a price yourself.
