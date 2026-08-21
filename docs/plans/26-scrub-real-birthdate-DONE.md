# Phase 26 — Scrub the real birthdate from the repository

**Depends on:** nothing. Standalone, and independent of phase 27.
**Needs a Polar token:** no.
**Size:** tiny. One commit.
**Priority:** do this one first — `github.com/ychab/polarexport` is a **public** repository.

## Where this came from

The phase-23 instruction to scrub PII from the committed Polar asset was followed correctly:
`tests/assets/polar/user-profile.json` carries `"Test" / "User"`, `"redacted-member"` and a
fabricated birthdate `1990-03-15`.

The leak came in through the plan documents instead. Phases 21 and 24 used the account owner's **real
birthdate, `1987-06-22`**, as the worked example for `UserProfile.age` and for the `manifest.json`
sample, and the implementing agents faithfully copied that literal into the tests. It is now in four
committed, publicly visible files.

A birthdate is not a harmless test constant: combined with the gender, height and weight already in
`manifest.json`, it is directly identifying. This is exactly the class of data the phase-23 asset rule
existed to keep out of git.

## 1 — Replace the literal

Use `1990-03-15` — the date already in `tests/assets/polar/user-profile.json`, so the fixture and the
asset finally agree instead of carrying two different birthdates.

| File | What to change |
|---|---|
| `tests/unit/infrastructure/adapters/archivers/test_exercise_serializers.py` | the `"birthdate"` fixture value and the `assert "1987-06-22" in note` expectation |
| `tests/integration/infrastructure/adapters/archivers/test_zip_exercise.py` | the `"birthdate"` fixture value |
| `docs/plans/21-exercise-domain-DONE.md` | the `UserProfile.age` acceptance example |
| `docs/plans/24-exercise-store-and-archiver-DONE.md` | the `manifest.json` worked example |

**The derived expectations move with it.** Any test asserting an age or an estimated max heart rate
has to be recomputed, not just find-replaced:

- `1987-06-22` on 2026-08-20 → age **39**, `estimated_max_heart_rate` **181**
- `1990-03-15` on 2026-08-20 → age **36**, `estimated_max_heart_rate` **184**

Grep for `39` and `181` in the two test files and fix whatever the birthdate feeds. Do not assume
those numbers appear only where you expect.

Update the `-DONE.md` plan files too. They are the reference the next phase copies from, and leaving
the real date there is how this happened in the first place.

## 2 — Verify

```bash
grep -rn "1987-06-22" . --exclude-dir=.git --exclude-dir=data --exclude-dir=htmlcov
```

Must return nothing. Then `make lint` clean and `make test` green at 100 %.

## What this phase deliberately does not do

**No history rewrite.** The date is in the commit history of a public repo; a `git filter-repo` would
break every existing clone and force-push a rewritten `main`. That is the account owner's call to
make, not an implementation detail — this phase removes the value from the working tree and says
plainly that the history still holds it.

Note also that `data/raw/polar-accesslink-v3/profile.json` holds the real first name, last name and
member id. That is correct and intended — it is the untouched Polar payload, it is mode 0600, `data/`
is git-ignored, and the export path already proves it never reaches an archive. Leave it alone.

## Acceptance

- The grep above is empty.
- `tests/assets/polar/user-profile.json` and the test fixtures agree on one fabricated birthdate.
- Age and max-heart-rate expectations recomputed, not blindly substituted.
- `make lint` clean, `make test` green at 100 % branch coverage.
