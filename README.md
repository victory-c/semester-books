# semester-books

Cubbie Skill: lists the books each course needs this term, read from the syllabi in Canvas, with the exact edition, access code warnings, free copies, a price-comparison link and a library link. No API keys; Python standard library only.

- `SKILL.md`: what Cubbie does (Canvas → book list file → script → reply)
- `scripts/tbfind.py`: checks ISBN/edition against Open Library, finds OpenStax/public-domain copies, prints catalog search links for the school library (Berkeley, ASU) with `--library-todo`, and writes the reply text
- Library check: Cubbie opens each catalog link in its own browser (no sign-in), records ebook / open_access / timed_loan / print / none in `books.json`, then reruns the script. The script itself never contacts the library.
- `python3 scripts/tbfind.py --sample`: runs offline on the bundled example
- `python3 -m unittest discover -s tests`: tests (offline)
- `python3 tests/eval_real.py`: rule-based extraction scored on 15 real public syllabi (hand-labelled in `tests/samples/real/EXPECTED.json`). The syllabi themselves are not in this repo; the eval and its test run only where they exist locally.
- `python3 tests/eval_agent.py`: the same score for a book list written by an agent following SKILL.md (`tests/samples/agent_real_books.json`)

Install: text this repository's link to Cubbie and reply "yes".
