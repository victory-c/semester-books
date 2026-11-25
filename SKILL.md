---
name: semester-books
description: Use when a student asks what books or materials their courses need or whether to buy a book; lists books, editions, access codes, free copies and price links. Reads the Canvas syllabi; legal sources only.
---

# Semester Books

Reads every syllabus in the student's Canvas and texts back one short list of books. It never quotes prices: it
links to a price-comparison page.

## When to use

- "What books do I need this semester?"
- "Do I have to buy anything for CHEM 1A?"
- "Is there a textbook for my econ class?"
- A photo of a bookstore book list or a syllabus.

Only when the student asks; don't bring it up on your own (not after the first Canvas sync either).

Do not use it to summarize a book or make study notes. Never use it to find unauthorized copies (see "Legal routes
only").

## Steps

1. **Pick the courses.** Use the courses the student named, otherwise all current-term courses in Canvas. If they are
   asking about next term, use next term's courses if Canvas already shows them.
   If Canvas is not connected, ask the student to connect it, or to send a screenshot of their bookstore book list or
   their course codes (default: "Send me a screenshot of your bookstore list"). Then stop and wait.
   Reuse an earlier list of the same courses only if you know it is under a week old; say the date you checked. If
   not, if a course had no book list or a library result was unconfirmed, or the student asks to recheck, do every step again.

2. **Read each course's book list.** For each course, read the syllabus page, and search the course files and pages
   for "syllabus", "textbook", "required materials" or "course materials"; read the PDF if the syllabus is a file.
   Save the syllabus text of each course in the working folder.
   The course overview cuts the syllabus text at about 2,000 characters. If it ends cut off ("…") with no book list
   yet, read the files it links to, then the course files and modules for a syllabus PDF. If none has the list, mark
   the course for a bookstore screenshot (step 6); don't guess from the cut text.

3. **Write the book list file** `books.json` in the working folder, following `references/books-json.md`. Only
   what the syllabus says; never guess an ISBN or an edition. Per book: title, author, edition, ISBN, `status`,
   `access_code`/`courseware`, `kind` (book, courseware, reader), `older_edition_ok`, `custom`, `provided`/`url`.
   Per course: `no_textbook`, `syllabus_empty`, `inclusive_access`. A course with no books still goes in.

4. **Check the student's library** (Berkeley and ASU; for other schools skip to step 5). From this Skill's folder:

   ```bash
   python3 scripts/tbfind.py --books <working folder>/books.json --school <school> --library-todo
   ```

   It prints up to eight catalog searches, one JSON line each. Open each `url` in the browser (not a web search or
   page read: the catalog is a JavaScript app), without signing in, and classify the result as `open_access`,
   `timed_loan`, `ebook`, `print` or `none` using `references/library-check.md`. Add it to that book in `books.json`
   as `"library": {"status": "...", "url": "<the result's own page>"}`. Never sign in, borrow or request anything.

5. **Run the script** for the reply. Pass `--school berkeley` or `--school asu` for those schools, otherwise leave
   `--school` out:

   ```bash
   python3 scripts/tbfind.py --books <working folder>/books.json --school <school> --json <working folder>/result.json
   ```

   It checks each ISBN and edition against Open Library, finds free OpenStax and public-domain copies, turns your
   library findings into plain lines, flags access codes, inclusive access and course readers, and prints the reply
   text.

   Then send the script's text as the reply (see "Replies"). You may translate it into the student's language,
   but do not shorten it or drop anything: every price-comparison link, library link and warning stays. Use only
   the ISBNs, links and facts it printed.

6. **Courses with no book list.** The script names them ("couldn't find a book list"). Ask for a screenshot of the
   bookstore list for those courses; when it arrives, read it, add the books to `books.json` and run steps 4 and 5 again.

7. **Next term not in Canvas yet.** Courses often appear in Canvas only days before the term. Offer one check-in and
   suggest a default: "Want me to check again when your spring courses show up?" Create it only after the student
   agrees, worded to make sense on its own later: "Semester Books: check Canvas for <term> courses and text only new books."

## Book list file

Format and an example: `references/books-json.md`. `edition` is a number. Exit code 2 names any wrong field.

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
about 30 seconds in total), still prints the list, and says plainly that some editions and ISBNs aren't confirmed. Send
that line as it is. Don't rerun in a loop; offer to check again later.
If stderr says it skipped an entry in a course after cleaning, ask the student for that course's bookstore list.
Never fill in an ISBN or a price yourself.
