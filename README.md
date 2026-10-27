# working_place

> A small set of **Claude Code mods**. Type `/mods` and a hub opens next to your session: live context/cost gauges, the status of every `claude agents` session, a session activity feed, a memo you can send to the session, Tetris, and an unofficial Pokémon collection game that grows with the tokens you spend.

![The mods hub next to a Claude session](docs/images/hub.png)

Every screen switches between English and Korean with the hub's `[ 한/EN ]` button.

## What's inside

| Plugin / mode | What it does |
|---|---|
| `pane-tools` | `/mods` opens the **hub** — even while the session is busy. Gauges, a partner Pokémon with a speech bubble, the awake sessions, and one button per mode. |
| ├ `feed` | **Session activity** — when each `claude agents` session finishes ✔, asks ▲ or starts ●, newest first, with its one-line summary. |
| ├ `memo` | A memo for the session. **send** queues it until the session is idle, then submits it. One memo per session. |
| ├ `tetris` | Tetris with hold (`c`). Draws a half-height board in short panes. |
| └ `pokemon` | Catch, evolve and battle with the tokens you spend — a fan-made game, see the [notice](#pokémon--unofficial-fan-project). |
| `long-run-watch` | Estimates how long a Bash command will take (median of its last runs, or "(about 30 min)" in the description), shows it in the status line and warns when it overruns. |

New modes are one file: drop a curses program at `pane-tools/bin/<name>.py` and the hub grows a `[ <name> ]` button. Files starting with `_` are helpers, not buttons. Text goes through `from _lang import L` → `L('한국어', 'English')`.

## The hub

- **Gauges** — context, cost and rate limits of the session it follows (each session's mod writes them every 2 s).
- **Speech bubble** — the partner reacts in one line: a session waiting for input (yellow after 10 minutes), ready to evolve, rewards, medals, gym badges and eggs, a session that just finished (it claps when it shipped a PR or a deploy), or rustling grass.
- **Sessions** — the awake `claude agents` sessions on the right, in the same colors as `claude agents` (needs yellow, working gray, completed green).
- **Partner art** — real sprites: Kitty graphics (cmux, Ghostty, kitty) or Sixel (Windows Terminal 1.22+, WezTerm, foot), detected automatically, `▀▄` blocks otherwise. Inside tmux the hub enables passthrough for its own pane only; add `set -as terminal-features ',xterm*:sixel'` to `~/.tmux.conf` (`install.sh --tmux-layout` does it).
- Keys work with a Korean keyboard layout too; on macOS with [`macism`](https://github.com/laishulu/macism) the hub switches to an English layout while focused.

### Session activity and memo

![Session activity feed](docs/images/feed.png)

![Memo](docs/images/memo.png)

### Tetris

<img src="docs/images/tetris.png" alt="Tetris" width="420">

## Pokémon

Tokens you spend in Claude Code turn into encounters. Fill the Pokédex generation by generation (1–9); the next generation opens when you beat that generation's Elite Four and Champion **or** complete its Pokédex, whichever comes first. The grass shows the newest open generation; species left in older generations are still yours to finish through evolution.

![Pokémon screen with showcased medals and badges](docs/images/pokemon.png)

**Catching** — one explore every 30k tokens. Starters come first, legendaries and mythicals last. Three balls per encounter plus the ones you own:
Poké Ball, Great Ball (×1.5), Ultra Ball (×2) and Master Ball (always catches). A Poké Ball catches 35–70% depending on the species' original catch rate. Legendaries and mythicals only fall to Ultra or Master Balls.
A species already in your bag shows up rarely and turns into Poké Balls. Trade 100 Poké Balls for an Ultra Ball with the bag's **trade** button.

**Rewards from work** — one Great Ball on any day a session finishes with a push, a PR merge or a deploy (read from the `claude agents` timelines; one per day). Three such days in a row (the 3rd, 6th, 9th day of a streak) bring an Ultra Ball.

**Eggs** — each wild catch has a 10% chance to come with an **egg** (up to three; the region conquest gives one too): a hidden first-stage species that hatches after its hatch steps × 5k tokens, shiny at 1/64, always with a bonus ball (Poké ×1 60% · ×2 20% · ×3 10% · Great 7% · Ultra 3%).

**Weekly challenge** — one task per week (changes on Monday, the same on every PC): catch 8, explore 15 times, win 5 gym/league battles, evolve twice, ship on 4 days or hatch an egg. Finishing it gives 2 Ultra Balls, 3 Great Balls and a **Rare Candy**, which evolves your partner on the spot when it has a form to evolve into (one candy a week).

**Partner and evolution** — the partner gains the tokens you spend and evolves past a threshold. It never evolves into a form already in your bag.

**Shinies** — 1/256 per encounter, counted apart from the normal form, shown in gold. Completing a generation gives that generation's **Shiny Charm** (I–IX), doubling the shiny rate for its species. One explore in five draws from all earlier generations instead (caught species included, legendaries excluded), so a finished generation can still be shiny-hunted.

**Medals** — 41 achievements (catches, generations, shinies, legendaries, evolutions, Great Balls, region conquests, champions), drawn with item sprites. Pick up to five medals or gym badges in the medal screen to show at the top of the Pokémon screen.

![Medals](docs/images/medals.png)

**Pokédex** — each uncaught entry shows how to get it (wild · evolve from … · legendary/mythical), and the bottom line counts what is left in the wild, evolve-only and legendary, plus who is in the grass right now. Pick a species and press Enter (←→ switches generation): category, types, height and weight, base stats, weaknesses (×4 marked), resistances and immunities, the Pokédex entry and a crisp sprite.

![Pokédex detail](docs/images/dex.png)

### Gyms, Elite Four and Champion

Eight gyms per opened generation, in the original type order (Alola uses its trial types). Build a team of up to six with the bag's **team** button or let the gym screen suggest one (**pick**, then **apply**) — it picks the combination from your Pokémon that raises the win rate most.

![Gym list with real gym badges](docs/images/gyms.png)

![Gym detail with win rate and a suggested team](docs/images/gym.png)

A challenge costs two explores and plays a fully automatic battle line by line: base stats, level (15 + 12 per evolution stage + one per 50 battle XP, up to +40; a loss gives the team +30 XP, a win +60 + 10 × gym number — the bag shows each Pokémon's progress like `Lv16 (10/50)`), each Pokémon's own type attack, type matchups and speed. The first win gives that gym's **badge** (the real badge art); every battle gives the team experience. After a win `q` goes straight back to the hub, after a loss back to the prep screen.

![A gym battle](docs/images/battle.png)

Each gym's first win gives an Ultra Ball. Clearing all eight gyms of a generation gives the region conquest medal, a Master Ball and an egg — and opens that generation's **Elite Four and Champion**: five battles in a row (four members with four Pokémon each, a champion with six), four explores per run. The first clear gives the champion medal and a Master Ball — two Master Balls per generation.

Controls — arrow keys, Enter and `q` only (2026-10-21; there were too many letter shortcuts). Arrows move between buttons and Enter presses the highlighted one; in lists (bag, medals, gyms, Pokédex) ↑↓ picks the row and ←→ the button below it, which acts on that row. In the Pokédex ←→ switches generation, in the detail view the previous/next species. `q` goes back or closes. The mouse works too.

## Install

### Marketplace (just use it)

Requires [Claude Code](https://docs.claude.com/claude-code) and `python3` (tmux is optional).

```
/plugin install pane-tools --marketplace Shin-junyeob/working_place
/plugin install long-run-watch --marketplace Shin-junyeob/working_place
```

From a shell: `claude plugin install pane-tools --marketplace Shin-junyeob/working_place`. Then type `/mods` in any session.
Auto-update is off for third-party marketplaces: turn it on in `/plugin` → Marketplaces → `working-place`, or run `claude plugin update pane-tools@working-place`.

### Clone (hack on it, keep several PCs in sync)

```bash
git clone https://github.com/Shin-junyeob/working_place.git ~/.claude/mods
bash ~/.claude/mods/install.sh                   # load this folder in every new session + self-check
bash ~/.claude/mods/install.sh --tmux-layout     # optional: tmux mouse, Sixel passthrough, the `sett` layout
bash ~/.claude/mods/install.sh --pokemon-backup  # optional: back up the Pokémon save daily at 17:59
bash ~/.claude/mods/install.sh --auto-pull       # optional: pull new commits from GitHub at boot and every 10 minutes
```

`install.sh` sets `CLAUDE_CODE_PLUGIN_DIRS` in `~/.claude/settings.json`, so every new session loads these mods and reloads them when a file changes. Don't enable the marketplace copy at the same time. `--auto-pull` adds two cron lines: one every 10 minutes and one `@reboot` that runs as soon as the machine (or WSL) starts, retrying every 2 s for up to 2 minutes until the network is up. It skips when there are local edits or unpushed commits and logs to `~/.claude/pane-tools/autopull.log`. An open hub restarts itself when any file in `pane-tools/bin/` changes; an open mode screen (Pokémon, Tetris…) gets the new code the next time you open it.

The `sett` layout (`--tmux-layout`) is `claude agents` on the left and, on the right, a spare shell, the activity feed and the hub — both started automatically.

## Where the hub opens

Choose in the hub's **setup** (`s`) or in `/config` → pane-tools; the hub's choice wins and applies from the next `/mods`.

![Hub setup](docs/images/setup.png)

| Option | Value | Behavior |
|---|---|---|
| `launcher` | `auto` (default) | split the current tmux window, or open a new terminal window outside tmux |
| | `tmux` | `tmuxTarget` empty → split the current window; set (e.g. `dev:0.3`) → replace that pane when it is an idle shell or the hub |
| | `window` | a new terminal window — Windows Terminal on WSL, Terminal on macOS, `x-terminal-emulator` on Linux |
| | `command` | your own command; `{cmd}` becomes the hub command, e.g. `wezterm cli split-pane -- bash -lc {cmd}` or `zellij run -- bash -lc {cmd}` |
| `followPane` | empty (default) | follow the session that ran `/mods` |
| | e.g. `dev:0.0` / `cmux:0` | follow whichever Claude session is open in that pane |
| `feedTarget` | e.g. `dev:0.2` | `/mods` also opens the activity feed there when that pane is an idle shell |

![The same options while installing](docs/images/install-config.png)

## Data on disk

Nothing below is in the repository. Everything lives in `~/.claude/pane-tools/`:
`settings.json` (language, partner art color, hub setup), `pokemon.json` (your progress), `pokedex.json` · `pokedex_detail.json` · `battle.json` (data from PokeAPI), `sprites/` (Pokémon, `shiny/`, gym `badges/`, `items/` — fetched from PokeAPI one by one when first shown), `memos/`, `usage/` (gauges and token counts per session), `inbox/` (memos waiting to be sent).

## Pokémon — unofficial fan project

- This is an **unofficial, non-commercial fan project**. It is not affiliated with, endorsed or sponsored by Nintendo, Creatures, GAME FREAK or The Pokémon Company. Pokémon and Pokémon character names are trademarks of their respective owners.
- **No Pokémon data or images ship in this repository.** Everything is downloaded on your machine from [PokeAPI](https://pokeapi.co/):
  - data — the public CSVs in [PokeAPI/pokeapi](https://github.com/PokeAPI/pokeapi) (`data/v2/csv`): names, generations, evolutions, capture rates, baby/hatch info, Pokédex entries, base stats and type matchups;
  - images — [PokeAPI/sprites](https://github.com/PokeAPI/sprites): `sprites/pokemon/<id>.png`, `sprites/pokemon/shiny/<id>.png`, `sprites/badges/<n>.png` and `sprites/items/<name>.png`, each fetched the first time it is shown.
  - The code only holds sprite numbers and names, the gym/Elite Four type tables and the game rules. Re-download the data with `python3 pane-tools/bin/_pokedata.py`.
- The screenshots in `docs/images/` are captures of this program running in a test environment; the sprites in them were drawn from PokeAPI at runtime.
- The Pokémon mode will be taken down on request from the rights holders.

## Development

- Self-checks: `python3 pane-tools/bin/<name>.py --selftest` for `memo`, `tetris`, `hub`, `feed` and `pokemon` (after the Pokédex has been downloaded once); `python3 pane-tools/bin/_battle.py` (battle rules) and `python3 pane-tools/bin/_place.py` (hub setup); `claude plugin test pane-tools` and `claude plugin test long-run-watch`.
- Bump `version` in the plugin's `.claude-plugin/plugin.json` so marketplace users see the update.

## License

MIT — see `LICENSE`. Pokémon names, PokeAPI data and sprites (Pokémon, badges, items) are not covered.
