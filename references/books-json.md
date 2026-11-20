# books.json: what to write

Write down only what the syllabus says; never guess an ISBN or an edition, leave it out.

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

## Example

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
