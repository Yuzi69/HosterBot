# Hosting Bot

A standalone Telegram bot that lets any user send a `.zip` and have it hosted
on your VPS — static sites, Node.js apps, or Java apps (Maven/Gradle).
No web login — Telegram user ID is the identity.

## 1. Create the bot

- Talk to **@BotFather** on Telegram → `/newbot` → copy the token.

## 2. VPS setup

```bash
chmod +x install.sh
./install.sh
```

Installs Python, Node.js, PM2, Java (JDK+Maven+Gradle), and creates
`/var/www/hosted` for deployed projects.

## 3. Configure

```bash
cp .env.example .env
nano .env
```

Fill in:
- `BOT_TOKEN` — from BotFather
- `PUBLIC_BASE_URL` — your VPS's IP or domain, e.g. `http://1.2.3.4` (this is
  what gets shown as each project's live URL)
- `ALLOWED_USER_IDS` — optional, comma-separated Telegram user IDs. Leave
  empty to let anyone who finds the bot deploy code on your server (not
  recommended — see Security notes).

To find your own Telegram user ID, message **@userinfobot**.

## 4. Run it

```bash
source venv/bin/activate
pm2 start bot.py --name hosting-bot --interpreter venv/bin/python3
pm2 start webserver.py --name hosting-web --interpreter venv/bin/python3
pm2 save && pm2 startup   # survive reboots
```

`webserver.py` listens on port `8080` by default (`WEB_PORT` in `.env`) and
is what actually serves `/sites/<id>/` and proxies `/app/<id>/`. Put it
behind nginx on port 80/443 if you want a clean URL — see the
`nginx.conf.example` pattern from the web-panel version, same idea, just
point `proxy_pass` at `127.0.0.1:8080`.

## 5. Using the bot

1. `/start` in Telegram.
2. Send a `.zip`:
   - Has `package.json` → **Node.js**, run via PM2, reachable at `/app/<id>/`.
   - Has `pom.xml` or `build.gradle` → built with Maven/Gradle, run via PM2.
   - Otherwise → **static** site, reachable at `/sites/<id>/`.
3. Bot replies with colored inline buttons: **Open / Redeploy / Stop / Delete**.
4. `/projects` lists everything you've deployed.

## Security notes — please read

Anyone who can message this bot (unless you set `ALLOWED_USER_IDS`) can
**execute arbitrary code** on your VPS. Restrict `ALLOWED_USER_IDS` unless
you specifically want this open to the public. For real isolation between
users' projects, the next step would be running each deployed app inside its
own Docker container — this version runs everything directly on the host via
PM2, fine for trusted use, not a hard security boundary.
