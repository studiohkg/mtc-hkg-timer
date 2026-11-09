# Split

A tiny shared-expenses app for two people. Everything is in Euro.

- Add an expense: what it was for, the amount, the date and who paid
- Split it equally, have the other person owe all of it, or split it by exact amounts or by percent
- Tap an entry to edit or delete it
- One balance shows who owes whom. **Settle up** records a full or partial payment back
- **📊 Stats**: total spent, who paid how much, each person's share, a monthly bar chart and the biggest expenses, for this month, last month, this year or all time

It is one Python file (`server.py`, standard library only) that serves the page and stores
everything in a single SQLite file, run with Docker. It is meant to be reached privately over Tailscale.

## Install on the server (Ubuntu + Docker)

```bash
git clone -b claude/great-edison-nqx5tg https://github.com/studiohkg/mtc-hkg-timer.git
cd mtc-hkg-timer/split
docker compose up -d --build
curl http://localhost:8765/health        # → {"ok": true}
```

The container listens only on `127.0.0.1:8765`, so it can't be reached from your LAN or the internet.

## Make it available on your tailnet (with HTTPS)

```bash
sudo tailscale serve --bg 8765
```

Then open **https://samserver.tail456694.ts.net** on your phone.
If `tailscale serve` already serves something else on that server, use another port instead:
`sudo tailscale serve --bg --https=8443 8765` → https://samserver.tail456694.ts.net:8443

Do **not** use `tailscale funnel`: it would put the app on the public internet.

## Give your partner access

1. They install the Tailscale app on their phone and sign in with their own account.
2. In the Tailscale admin console → Machines → samserver → **Share…**, invite them.
   That gives access to this one machine only. Alternatively, invite them to your tailnet.
3. They open the URL above. In Safari or Chrome, use "Add to Home Screen" so it works like an app.

## First use

The first PIN anyone enters becomes the shared PIN (minimum 6 characters).
Change the PIN and both names under ⚙️ Settings.

## Backup

All data is in one file inside the Docker volume `split_split-data`:

```bash
docker cp split:/data/split.db ~/split-backup-$(date +%F).db
```

To back up nightly, add a crontab entry (`crontab -e`):
`0 3 * * * docker cp split:/data/split.db $HOME/split-backups/split-$(date +\%F).db`
(create `~/split-backups` first).

To restore: `docker cp backup.db split:/data/split.db && docker compose restart`.

## Update

```bash
git pull && docker compose up -d --build
```
