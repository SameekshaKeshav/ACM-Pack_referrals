# Pack Referrals frontend

React + Vite + React Router + Tailwind. Includes the shared profile/directory work,
email-code authentication and the Chat/Connect UI.

## Run locally

Use Node 24, at least 24.15 (`.nvmrc` selects 24). Start Django on
`http://127.0.0.1:8000` using the root README, then:

```bash
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173/signup** for a new account, or `/login` for a returning
user. Both use an emailed six-digit code, not a password. Django's default local
email backend prints the code to the backend console. Real email requires
`EMAIL_BACKEND` and `BREVO_API_KEY` (see the root README).

Verification signs in and opens `/chat`. Access/refresh credentials persist across
reloads; protected requests attach Bearer auth and refresh once on 401. Log out
clears the session. Chat, profile, directory, company and `/chat-mock` require login.

Vite forwards `/api` to Django. To use a different development target, copy
`.env.example` to `.env.local`, set `VITE_API_PROXY_TARGET`, and restart Vite.

## Production build (served by Django)

Staging doesn't run Vite: Django serves the built app from the same origin as the
API (see Deployment in the root README). To try that setup locally:

```bash
cd frontend
npm run build                      # writes dist/
cd ..
python manage.py runserver
```

Open **http://127.0.0.1:8000/**. With `DEBUG=True`, `runserver` serves `dist/`
directly, so `collectstatic` isn't needed. Rebuild after frontend changes;
there's no hot reload in this mode.

Builds link their files under `/static/` (`base` in `vite.config.js`), where
WhiteNoise serves them. `npm run dev` and `npm run preview` are unaffected and
still open at `/`.

## Live chat

- `/chat`: authenticated conversation sidebar.
- `/chat/<id>`: full history sorted by timestamp and ID; pagination is described in
  `../docs/chat-auth-integration.md`.
- Send appends a temporary bubble immediately, then replaces it on acknowledgement.
  Errors leave a failed bubble with explicit Retry. A send stays in its originating
  conversation if the user switches threads.
- The composer caps text at 2000 Unicode code points and rejects blank sends.

**Backend dependency:** inspected main still exposes raw chat CRUD, without nested
history or the required sidebar/send representations. The frontend is wired to the
requested contract and tested; real chat is not integrated until its backend owner
implements it. Unsupported responses show errors rather than fictional history.
Auth was checked using actual Django HTTP requests.

## Previous mock demo

After signing in, open `/chat-mock`. This retains 3 incoming fixture requests, 2
outgoing rows, a selectable sidebar and Avery's 5-message thread. Accept/Decline
remove cards locally and log PATCH; mock chat Send remains disabled. Reset demo
restores fixtures. Only `/chat` uses live chat requests.

The mock's separate Send Request form posts `{recipient_id,message_text}` to
`/api/connections/` with a 500-code-point limit/counter. It now uses the signed-in
session/shared client; users do not paste JWTs into the routed page. The inherited
main has canonical connection routes, but integrating them is separate from the
old local Accept/Decline demonstration.

## Verify

```bash
npm run build
npm run test:dom
npx playwright install chromium
npm test
```

The 29 DOM tests cover auth screens, refresh/logout races, persistence, ordered
history, optimistic send/retry and the original mock. The 14 Playwright cases also
cover real page reloads and mobile layout with intercepted backend responses.
The frontend GitHub Actions workflow runs the build and both suites on Node 24.

Detailed API shapes, backend dependencies, storage tradeoffs and acceptance steps:
[chat-auth-integration.md](../docs/chat-auth-integration.md).
