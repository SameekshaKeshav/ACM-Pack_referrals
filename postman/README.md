# Postman collection

`pack-referrals.postman_collection.json` covers every endpoint on main (42 method and path pairs, 88 requests including the error cases). Each request has tests and one saved example, taken from a real local run.

**Local only.** It creates and deletes data, and `seed_demo_data` refuses to run without `DEBUG`. Never point it at staging.

## Run it all from the terminal

```bash
postman/run_collection.sh
```

The script migrates a throwaway SQLite file, so your `db.sqlite3` is never touched. It then runs `seed_demo_data`, starts its own `runserver` on port 8765 (set `PORT` to change it) and runs the collection with newman. The script needs Node, because newman is fetched through `npx`.

Throttles are raised for the run so reruns don't get 429s. `manage.py test` covers the throttles themselves.

## Run it in the Postman app

1. Import the collection.
2. Run `python manage.py seed_demo_data`. It prints `name: value` lines such as `sender_token`, `recipient_id` and `verify_code`.
3. Paste each value into the collection variable of the same name (Variables tab, *Current value*). Keep `base_url` as `http://127.0.0.1:8000`.
4. Run the folders top to bottom. Later folders use ids that earlier ones save, such as `connection_id` and `conversation_id`. Rerun the seed before running again. The verify code is single-use, and the seed resets the rows the collection creates.

Requests act as the sender unless their Authorization tab names `recipient_token` or `outsider_token`. Public routes use *No Auth*.

## Change a request or add one

1. Edit the collection, in the app (then export it over this file as Collection v2.1) or as JSON.
2. Give a new request a test that checks its status, for example `pm.response.to.have.status(201)`.
3. Regenerate every example from a real run:

   ```bash
   postman/run_collection.sh --save-examples
   ```

   This replaces each request's example with the response it just got. It writes nothing if any test fails or any request did not run. JWTs in response bodies are redacted, and examples keep `{{variables}}` rather than the values that were sent.

**Referral fields:** the Referrals folder has a folder-level test with `REFERRAL_FIELDS`, the exact set of fields every referral in a response must have. When the API gains a field, add it there and to the request bodies, then regenerate the examples.

## Not covered yet (not on main)

- Referral accept and decline: `PATCH /api/connections/referrals/<id>/accept|decline/`.

The Reports, Blocks and Interview experiences folders cover #39. When #57 merges, add the accept and decline requests and move them out of this list.
