#!/usr/bin/env bash
# Auth demo walkthrough — Pack Referrals, BE1 (Sprint 1 / week 4).
# Not committed; local demo aid only.
#
# Usage:  ./demo_auth.sh your_unity_id@ncsu.edu
# Needs the dev server already running in another terminal.

set -u
EMAIL="${1:-kmpanick@ncsu.edu}"
BASE="http://localhost:8000"
H='Content-Type: application/json'
PY=./.venv/bin/python

bold()  { printf "\n\033[1;36m%s\033[0m\n" "$*"; }
note()  { printf "\033[2m%s\033[0m\n" "$*"; }
pause() { printf "\n\033[2m[enter]\033[0m"; read -r _; }

call() {  # call METHOD PATH JSON
  printf "\033[1m%s %s\033[0m  %s\n" "$1" "$2" "$3"
  curl -s -w $'\n\033[1mHTTP %{http_code}\033[0m\n' -X "$1" "$BASE$2" -H "$H" -d "$3"
}

db() { $PY manage.py shell --no-imports -c "$1" 2>/dev/null; }

curl -sf "$BASE/api/health/" >/dev/null || { echo "Dev server is not running on :8000"; exit 1; }

bold "0. Where we are"
note "Verified NC State students only. No passwords anywhere in this system."
note "Demo account: $EMAIL"
pause

bold "1. The domain gate — anyone outside NC State is rejected"
call POST /api/accounts/auth/signup/ '{"email":"someone@gatech.edu"}'
note "400. The validator runs before any database write."
pause

bold "2. Sign up with a real NC State address"
call POST /api/accounts/auth/signup/ "{\"email\":\"$EMAIL\"}"
note "201. Now switch to the server terminal — the email is printed there."
pause

bold "3. What the database holds right now"
db "
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(email='$EMAIL')
v = u.verification_codes.first()
print(f'  account active      : {u.is_active}')
print(f'  profile status      : {u.profile.account_status}')
print(f'  has a password      : {u.has_usable_password()}')
print(f'  stored code         : {v.code_hash[:46]}...')
print(f'  expires at          : {v.expires_at:%H:%M:%S} UTC')
"
note "The code is stored only as a PBKDF2 hash — the same hasher Django uses for"
note "passwords. If this database leaked, nobody could recover a usable code."
pause

bold "4. A wrong code is rejected"
call POST /api/accounts/auth/verify/ "{\"email\":\"$EMAIL\",\"code\":\"000000\"}"
pause

bold "5. An address that was never registered gets the IDENTICAL response"
call POST /api/accounts/auth/verify/ '{"email":"nobody-here@ncsu.edu","code":"000000"}'
note "Same status, same body, same timing. The endpoint will not tell you which"
note "NC State addresses have accounts."
pause

bold "6. Now the real code — read it off the server terminal"
printf "   code: "; read -r CODE
RESP=$(curl -s -X POST "$BASE/api/accounts/auth/verify/" -H "$H" \
       -d "{\"email\":\"$EMAIL\",\"code\":\"$CODE\"}")
echo "$RESP" | $PY -m json.tool
pause

bold "7. What is inside that token"
echo "$RESP" | $PY -c "
import sys, json, base64, datetime
t = json.load(sys.stdin)
def claims(tok):
    s = tok.split('.')[1]; s += '=' * (-len(s) % 4)
    return json.loads(base64.urlsafe_b64decode(s))
for name in ('access', 'refresh'):
    c = claims(t[name])
    life = c['exp'] - c['iat']
    print(f\"  {name:8} user_id={c['user_id']}  lives {life//3600}h  expires {datetime.datetime.utcfromtimestamp(c['exp'])} UTC\")
print()
print('  Readable by anyone — a JWT is signed, not encrypted.')
print('  But the signature means nobody can change user_id without the server key.')
"
pause

bold "8. The account is now verified, and the code is gone"
db "
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(email='$EMAIL')
print(f'  account active      : {u.is_active}')
print(f'  profile status      : {u.profile.account_status}')
print(f'  codes left          : {u.verification_codes.count()}')
"
pause

bold "9. Replaying the same code fails — codes are single use"
call POST /api/accounts/auth/verify/ "{\"email\":\"$EMAIL\",\"code\":\"$CODE\"}"
pause

bold "10. Signing up again does NOT lock the address out"
call POST /api/accounts/auth/signup/ "{\"email\":\"$EMAIL\"}"
note "409 — this account is already verified, so it is a genuine conflict."
note "An UNverified address would instead get a fresh code, so nobody can be"
note "locked out by a missed code, a failed send, or someone else claiming it."
pause

bold "11. What is NOT done yet — enforcement"
ACCESS=$(echo "$RESP" | $PY -c "import sys,json; print(json.load(sys.stdin)['access'])")
printf "\033[1mGET /api/accounts/profiles/\033[0m  with NO token\n"
curl -s -w $'\n\033[1mHTTP %{http_code}\033[0m\n' "$BASE/api/accounts/profiles/" | head -c 300; echo
note ""
note "200 — it answered without a token. DRF still defaults to AllowAny, and no"
note "JWT authentication class is registered, so a valid token is currently"
note "ignored: request.user comes back as AnonymousUser."
note ""
note "That is sprint 2: register JWTAuthentication, switch the default permission"
note "to IsAuthenticated, add login, a refresh endpoint, throttling, and a cap on"
note "verify attempts. This endpoint should answer 401 without the token and 200"
note "with it."
echo
