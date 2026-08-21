# Phase 20 — CI and coverage badges

**Depends on:** nothing. Standalone, and independent of phases 21–25.
**Needs a Polar token:** no.
**Size:** tiny. One commit.

## Where this came from

The user asked for a test-coverage badge in `README.md`, "like we did with the museflow project".

Most of the work is already done and nobody noticed: `.github/workflows/ci.yml` **already** runs the
suite and uploads to Codecov (`codecov/codecov-action@v7`, `files: coverage.xml,junit.xml`), and
`pyproject.toml` already emits both files (`--cov-report=xml`, `--junitxml=junit.xml`). What is
missing is only the two badges in `README.md`. polarexport's README currently carries Python, Ruff,
mypy, uv and License badges — museflow's carries a CI badge and a Codecov badge as well, plus
pre-commit.

## 1 — Add the badges

`README.md`, in the existing badge block. Match museflow's order: Python, CI, codecov, License on the
first line; Ruff, mypy, uv, pre-commit on the second.

```markdown
[![CI](https://github.com/ychab/polarexport/actions/workflows/ci.yml/badge.svg)](https://github.com/ychab/polarexport/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ychab/polarexport/graph/badge.svg)](https://codecov.io/gh/ychab/polarexport)
```

The remote is `git@github.com:ychab/polarexport.git`, so `ychab/polarexport` is the right slug —
confirm with `git remote -v` before writing it rather than copying museflow's `ychab/museflow`.

Add the pre-commit badge too while you are in there, since `.pre-commit-config.yaml` exists:

```markdown
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
```

## 2 — Say what the badge means

The coverage number is not a target that drifts — `fail_under = 100` means a red build, not a lower
percentage. Add one line under the badges, or in the Development section, saying so:

> Coverage is enforced at 100 % branch coverage by `pytest --cov-fail-under`; the badge reports the
> figure, the build enforces it.

## 3 — Optional: pin the Codecov flag

Nothing to change unless the badge renders "unknown" after the first push. If it does, the cause is
almost always the missing repository secret (see below), not the workflow.

## Files

| File | Change |
|---|---|
| `README.md` | add CI, codecov and pre-commit badges; add the one-line note about `fail_under` |

No source changes, no test changes.

## Tests

None. This phase touches documentation only. `make lint` and `make test` must still pass unchanged.

## Prerequisite for the user — do this before merging

The Codecov badge renders "unknown" until the repository is linked:

1. Sign in at <https://codecov.io> with GitHub and add `ychab/polarexport`.
2. Copy the upload token.
3. Add it as a repository secret named `CODECOV_TOKEN` (Settings → Secrets and variables → Actions).

The workflow step already references `${{ secrets.CODECOV_TOKEN }}`, so nothing in CI changes. The
CI badge itself needs no setup and works from the first push to `main`.

## Acceptance criteria

- `README.md` shows CI, codecov, pre-commit badges alongside the existing ones.
- The badge URLs use the `ychab/polarexport` slug, not museflow's.
- `make lint` clean, `make test` green at 100 % branch coverage.
