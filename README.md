# Pinoy Economy Bot 🇵🇭

A Discord economy bot themed around everyday Filipino life — trabaho, tambay,
sugal, palengke, budol, and more. Built with `discord.py` (slash commands)
and a SQLite database for persistent player data.

## Does data get lost when I update my code?

**No — balances live in a SQLite database file (`data/economy.db`), completely
separate from your code.** Pushing new commits to GitHub, or redeploying,
never touches that file, so nobody loses their money when you ship an update.

**The one exception is Railway's ephemeral filesystem.** By default, Railway
wipes the container's disk on every redeploy — including the `data/` folder.
To make money persist there, you must attach a **Volume**:

1. In your Railway project, go to your service → **Settings** → **Volumes**.
2. Click **New Volume**, set the mount path to `/data`.
3. Go to **Variables** and add `DATA_DIR=/data`.
4. Redeploy once. From then on, `economy.db` lives on that volume and survives
   every future deploy.

If you skip this step, the bot will still work, but everyone's balance resets
every time you redeploy on Railway.

## Local setup

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:
- `DISCORD_TOKEN` — from the [Discord Developer Portal](https://discord.com/developers/applications) → your app → **Bot** → Reset/Copy Token.
- `GUILD_ID` (optional, recommended while testing) — right-click your test server icon in Discord (enable Developer Mode first) → Copy Server ID. Commands registered to a single guild show up instantly; global commands can take up to an hour.

Then invite the bot to your server: Developer Portal → your app → **OAuth2 → URL Generator** → scopes `bot` and `applications.commands` → permissions `Send Messages`, `Embed Links`, `Use Slash Commands` → open the generated URL.

Run it:

```bash
python main.py
```

## Deploying on Railway

1. Push this project to a GitHub repo.
2. In Railway: **New Project → Deploy from GitHub repo** → select the repo.
3. Railway will detect the `Procfile` and use `python main.py` as the start command. If it instead tries to detect a web server, go to **Settings → Deploy** and set the **Start Command** manually to `python main.py`.
4. Go to **Variables** and add:
   - `DISCORD_TOKEN` = your bot token
   - `GUILD_ID` = your test server ID (optional, or leave blank for global commands)
   - `DATA_DIR` = `/data`
5. Attach a Volume mounted at `/data` (see the section above) — **don't skip this**.
6. Deploy. Check the **Logs** tab for `Logged in as ...` to confirm it's online.

## Commands

Run `/help` in Discord once the bot is online for the full in-app list. Summary:

| Command | What it does |
|---|---|
| `/help` | Lists all commands |
| `/jobs` | Shows job pay ranges |
| `/trabaho job:<pick>` | Pick/switch job, or work it to earn (30 min cd) |
| `/tambay` | Hang out, 70% small win / 30% small loss (1 min cd) |
| `/sugal amount:<₱>` | 50/50 coinflip bet, no limit |
| `/palengke presyo` | View market prices |
| `/palengke bili item:<pick> quantity:<n>` | Buy goods |
| `/palengke benta item:<pick> quantity:<n>` | Sell goods |
| `/load bili quantity:<n>` | Buy mobile load |
| `/load benta quantity:<n>` | Resell load for profit/loss |
| `/utang lender:<@user> amount:<₱>` | Borrow from another player |
| `/bayad lender:<@user> amount:<₱>` | Pay back a debt |
| `/budol target:<@user>` | Scam attempt, 1 day cd, risky |
| `/karaoke` | Sing for tips ₱50-500 (5 min cd) |
| `/baon` | Daily allowance ₱50-100 (24 hr cd) |

## Project structure

```
main.py           # bot entry point, loads cogs, syncs slash commands
database.py        # SQLite connection + schema
db_utils.py        # shared helper functions (balances, cooldowns, etc.)
jobs_data.py        # job definitions
cogs/
  economy.py        # /jobs /trabaho /tambay /sugal /baon
  market.py          # /palengke /load
  social.py          # /utang /bayad /budol /karaoke
  help.py            # /help
```

## Notes / things you may want to tweak

- Pay ranges, cooldowns, and odds all live near the top of each cog file —
  easy to rebalance without digging through logic.
- `/budol` success chance is 40% by default; adjust `BUDOL_SUCCESS_CHANCE` in `cogs/social.py`.
- `/karaoke` has a 5-minute cooldown added for game balance since the original
  spec didn't specify one — change `KARAOKE_COOLDOWN_SECONDS` in `cogs/social.py` if you'd rather it be uncapped.
- Everything uses SQLite via Python's built-in `sqlite3` module — no external
  database service needed.
