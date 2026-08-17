# Polar AccessLink authentication

One-time setup. Once done, the resulting access token is effectively permanent — Polar's docs state
*"Access tokens will not expire unless explicitly revoked by partners or users"*, and the `expires_in`
they return is on the order of 15 years.

---

## What the four values actually are

This trips everyone up, so be precise:

| Value | Where it comes from | What it identifies |
|---|---|---|
| `POLAR_CLIENT_ID` | Credentials tab at [admin.polaraccesslink.com](https://admin.polaraccesslink.com) | **Your application** |
| `POLAR_CLIENT_SECRET` | Credentials tab, same place | **Your application** |
| `POLAR_ACCESS_TOKEN` | The token exchange in step 3 below | **Your Polar account's grant to your app** |
| `POLAR_USER_ID` | `x_user_id` in that same token response | **Your Polar account** |

**The client id is not the user id, and the client secret is not the access token.** The first pair
says "this is the polarexport app". The second pair is produced only after you, as a Polar user, log
in and consent — that's what actually unlocks your data.

`POST /v3/users` does **not** generate the token either. It runs *after* you already have the token,
and it links your account to your application. Without it, every data request returns `403`.

---

## Prerequisites

At [admin.polaraccesslink.com](https://admin.polaraccesslink.com), your client must have a registered
**redirect URI**. This guide assumes:

```
http://localhost:8000/auth/polar/callback
```

The redirect URI is used — in step 2 the browser is sent there with the authorization code, and in
step 3 it must be passed again and match exactly. You don't need a running web server for it to work
(step 2 shows a trick that makes it more convenient), but the value must match what you registered,
character for character.

---

## Step 1 — Export your client credentials

```bash
export POLAR_CLIENT_ID='paste-from-the-credentials-tab'
export POLAR_CLIENT_SECRET='paste-from-the-credentials-tab'
export POLAR_REDIRECT_URI='http://localhost:8000/auth/polar/callback'
```

## Step 2 — Authorize in a browser and grab the code

Optionally, start a throwaway listener first so the redirect resolves and logs the code for you:

```bash
python3 -m http.server 8000
```

It will answer the callback with a 404 page, but its access log prints the full request line —
including the `code` query parameter. Leave it running in another terminal.

Now build the authorization URL and open it:

```bash
python3 - <<'EOF'
import os, urllib.parse
params = {
    "response_type": "code",
    "client_id": os.environ["POLAR_CLIENT_ID"],
    "redirect_uri": os.environ["POLAR_REDIRECT_URI"],
    "scope": "accesslink.read_all",
}
print("https://flow.polar.com/oauth2/authorization?" + urllib.parse.urlencode(params))
EOF
```

Open the printed URL, log in with your Polar account, and accept the consent screen. You will be
redirected to:

```
http://localhost:8000/auth/polar/callback?code=71682f9544255285736fb6d2d8acb6cf
```

If you started the listener, the code appears in its log. If you didn't, the browser shows a
"connection refused" page — the code is still right there in the address bar. Copy it either way.

```bash
export CODE='71682f9544255285736fb6d2d8acb6cf'
```

> The authorization code expires in **10 minutes** and is **single-use**. If step 3 fails, redo
> step 2 to get a fresh one.

## Step 3 — Exchange the code for an access token

```bash
curl -sS -X POST 'https://polarremote.com/v2/oauth2/token' \
  -u "${POLAR_CLIENT_ID}:${POLAR_CLIENT_SECRET}" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Accept: application/json;charset=UTF-8' \
  -d 'grant_type=authorization_code' \
  -d "code=${CODE}" \
  -d "redirect_uri=${POLAR_REDIRECT_URI}"
```

`curl -u` sends `Authorization: Basic base64(client_id:client_secret)` for you.

Response:

```json
{
  "access_token": "9d43ac9b6e1f4a0b8f4d2c3e5a7b9c11",
  "token_type": "bearer",
  "expires_in": 473039999,
  "x_user_id": 12345678
}
```

```bash
export POLAR_ACCESS_TOKEN='9d43ac9b6e1f4a0b8f4d2c3e5a7b9c11'
export POLAR_USER_ID='12345678'
```

`x_user_id` **is** your `POLAR_USER_ID`.

## Step 4 — Register yourself with your application

Required once. Until this succeeds, every data endpoint returns `403`.

```bash
curl -sS -X POST 'https://www.polaraccesslink.com/v3/users' \
  -H "Authorization: Bearer ${POLAR_ACCESS_TOKEN}" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{"member-id": "yannick"}'
```

`member-id` is any stable string you choose to identify yourself within your own app.

- `200` — registered. The response echoes `polar-user-id` (same number as `x_user_id`).
- `409 Conflict` — already registered. Harmless, carry on.
- `403 Forbidden` — missing consents. Review them at [account.polar.com](https://account.polar.com).

## Step 5 — Write `.env`

```bash
cat >> .env <<EOF
POLAR_CLIENT_ID=${POLAR_CLIENT_ID}
POLAR_CLIENT_SECRET=${POLAR_CLIENT_SECRET}
POLAR_ACCESS_TOKEN=${POLAR_ACCESS_TOKEN}
POLAR_USER_ID=${POLAR_USER_ID}
POLAR_REDIRECT_URI=${POLAR_REDIRECT_URI}
EOF
```

`.env` is gitignored. Never commit it, and never paste the access token into an issue or a prompt.

polarexport itself only reads `POLAR_ACCESS_TOKEN` and `POLAR_USER_ID`. The client id, secret and
redirect URI are stored so you can repeat this flow (or so a future `polarexport auth login` command
can automate it) — they are not used at export time.

## Step 6 — Verify

```bash
curl -sS -H "Authorization: Bearer ${POLAR_ACCESS_TOKEN}" \
  "https://www.polaraccesslink.com/v3/users/${POLAR_USER_ID}"

curl -sS -H "Authorization: Bearer ${POLAR_ACCESS_TOKEN}" \
  "https://www.polaraccesslink.com/v3/users/sleep/$(date -d '2 days ago' +%F)"
```

The first returns your profile. The second returns a night of sleep data — or `404` if that
particular night has none, which is normal and not an error.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `invalid_grant` on step 3 | Code expired (>10 min), already used, or `redirect_uri` doesn't match step 2 exactly |
| `401 Unauthorized` on step 3 | Wrong `client_id` / `client_secret` |
| `403` on every data endpoint | Step 4 never succeeded, or a consent is missing at [account.polar.com](https://account.polar.com) |
| `404` on a specific night | No data for that date. Expected — polarexport records it as a gap |
| `204 No Content` on a range endpoint | No data in that window |
| Empty results older than 28 days | Polar AccessLink v3 only retains the last **28 days**. See the README's "Why a local `data/` store" section |

## Revoking

Revoke the grant at [account.polar.com](https://account.polar.com) under connected applications. The
access token dies immediately and you must repeat steps 2–4.
