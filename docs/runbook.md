Runbook

Step 1 — One-time setup (2 min, do it now)

mkdir -p /home/yannick/Projects/PERSONAL/polarexport/.claude
cp /home/yannick/Projects/PERSONAL/museflow/.claude/settings.local.json \
   /home/yannick/Projects/PERSONAL/polarexport/.claude/settings.local.json

This allowlists uv, make, docker compose, git, find, grep so you're not clicking through permission prompts all night.

Step 2 — Get your Polar token (10 min, needs a browser)

Do this any time before phase 5 — you can do it while phases 1–4 run. Open docs/authentication.md and follow steps 2 → 5. It's copy-paste curl commands. The short version:

1. Build the authorization URL, open it in a browser, log in, accept
2. Copy the code from the redirect URL (expires in 10 min, single use)
3. curl the token exchange → gives you access_token and x_user_id
4. curl POST /v3/users to register yourself (409 = already done, fine)
5. Append POLAR_ACCESS_TOKEN and POLAR_USER_ID to .env

Step 3 — Switch model

Type /model, pick Sonnet 5.

Step 4 — Run the phases

For each phase: /clear, then paste the prompt. Change only the number and filename.

Read docs/plans/00-overview.md, then docs/plans/01-scaffolding.md.
Implement that phase completely and nothing else.
Follow the museflow conventions exactly as the phase file instructs.
When finished, run `make lint` and `make test` and make sure both are green.

┌───────┬─────────────────────────────┬───────────────────────────────────────────────────────────────────────────────┬────────────────┐
│ Phase │            File             │                                 What it does                                  │     Needs      │
├───────┼─────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼────────────────┤
│ 1     │ 01-scaffolding.md           │ pyproject, Makefile, CI, docker-compose, README, git init, empty package tree │ —              │
├───────┼─────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼────────────────┤
│ 2     │ 02-config-infrastructure.md │ settings, logging, HTTP client, bare CLI. polarexport --version works         │ —              │
├───────┼─────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼────────────────┤
│ 3     │ 03-domain.md                │ entities, value objects, night merger                                         │ —              │
├───────┼─────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼────────────────┤
│ 4     │ 04-application.md           │ ports + the two use cases (sync, export)                                      │ —              │
├───────┼─────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼────────────────┤
│ 5     │ 05-polar-adapter.md         │ the Polar client + mappers                                                    │ token + Docker │
├───────┼─────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼────────────────┤
│ 6     │ 06-data-store.md            │ the data/ filesystem store                                                    │ —              │
├───────┼─────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼────────────────┤
│ 7     │ 07-zip-archiver.md          │ the .zip writer                                                               │ —              │
├───────┼─────────────────────────────┼───────────────────────────────────────────────────────────────────────────────┼────────────────┤
│ 8     │ 08-cli-and-docs.md          │ the night command + README                                                    │ token + Docker │
└───────┴─────────────────────────────┴───────────────────────────────────────────────────────────────────────────────┴────────────────┘

Start Docker before phases 5 and 8 — make test brings WireMock up and down itself, but the daemon needs to be running.

---
Two things to watch

Phase 5 is the one that can surprise you. It starts by curl-ing your real account and building the data models from what actually comes back — the field names in the plan are from Polar's public docs and unverified. Expect the agent to correct some enum values, and expect one or two sources to return 403 if your watch doesn't support them (skin temperature needs an Elixir-capable device). That's handled, not a failure.

Every phase must end green. If make lint or make test fails and the agent can't fix it in ~3 tries, stop and tell me rather than letting it grind — the plans specify 100% branch coverage, which is a strict gate and occasionally needs a human call about whether a branch is worth keeping.

---

Prompt to new session with sonnet models:

```
Read docs/plans/00-overview.md, then docs/plans/02-config-infrastructure.md.
  Implement that phase completely and nothing else.
  Follow the museflow conventions exactly as the phase file instructs.
  When finished, run `make lint` and `make test` and make sure both are green.
```
