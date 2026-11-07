# Split

A tiny shared-expenses app for two people. Everything is in Euro.

- Add an expense: what it was for, the amount, the date and who paid
- Split it equally, have the other person owe all of it, or split it by exact amounts or by percent
- Tap an entry to edit or delete it
- One balance shows who owes whom. **Settle up** records a full or partial payment back

## Setup
1. In Supabase, open the SQL editor and run `supabase/schema.sql`.
2. In `index.html`, set `SUPABASE_URL` and `SUPABASE_KEY` (Project Settings → API, anon/publishable key).
3. Deploy the folder to Netlify (no build step, publish directory = repo root).
4. Open the site and pick a shared PIN (min. 6 characters). The first PIN anyone enters becomes the PIN. You can change it and both names in Settings.

The anon key is public. The tables have RLS turned on with no policies, so the key can only call
the `split_*` functions, and every one of them checks the PIN.
