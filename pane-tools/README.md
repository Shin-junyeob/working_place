# pane-tools — the /mods hub

Type `/mods` in Claude Code and a small hub opens next to your session in a terminal pane. It shows live gauges for the session (context, cost, 5-hour and 7-day limits), the status of every `claude agents` session, and buttons for a few terminal mods: a session activity feed, a memo you can send to a session, Tetris, and an unofficial Pokémon collection game that grows with the tokens you spend. Every screen switches between Korean (the default) and English with `l`.

## Install

```
/plugin install pane-tools --marketplace Shin-junyeob/working_place
```

Full guide and screenshots: https://github.com/Shin-junyeob/working_place

## Requirements

- Python 3 with the standard library only (curses). No packages are installed.
- A terminal with 256 colours. Sprites use Sixel or the Kitty graphics protocol when the terminal supports it, and coloured blocks otherwise.
- tmux is optional. Without it the hub opens in a new terminal window.

## Options

Set them with `/plugin` → Installed → pane-tools → Configure, or from the hub's `[ setup ]` screen.

| Option | What it does |
|---|---|
| `launcher` | where the hub opens: `auto`, `tmux`, `window` or `command` |
| `tmuxTarget` | a tmux pane to reuse (for example `dev:0.3`); empty splits the current window |
| `followPane` | a pane whose Claude session the hub and memo follow; empty follows the session that ran `/mods` |
| `command` | your own launch command for `command` mode, with `{cmd}` replaced by the hub command |
| `feedTarget` | a tmux pane where `/mods` also opens the activity feed |

## What it runs, reads, writes and fetches

- **Commands.** `/mods` starts `python3 bin/hub.py` from this plugin, through one of: `tmux split-window` or `tmux respawn-pane` (also `tmux has-session`, `display`, `show`, `set` and `resize-pane` on the chosen pane), `wt.exe` on WSL, `osascript` to open Terminal on macOS, or the command you set. It runs `uname -s` to detect macOS. The hub runs `claude agents --json` to list sessions.
- **Files it reads.** `~/.claude/jobs/*/state.json` and `timeline.jsonl` (session status and the activity feed), and `~/.claude/pane-tools/`.
- **Files it writes.** Everything goes under `~/.claude/pane-tools/`: settings, memos, per-session gauges, the Pokémon save and downloaded game data. Nothing is written elsewhere.
- **Shipping work.** The mod looks at each Bash command a session runs. When a `git push`, `gh pr create`/`gh pr merge` or a deploy script succeeds, it writes a small file to `~/.claude/pane-tools/ships/` (the time, the session id and the kind — no command text). The Pokémon mode counts those days for its work rewards. The command and its result are not changed.
- **Memos.** A memo you send is stored in `~/.claude/pane-tools/inbox/<session id>.json`. The receiving session's copy of this plugin submits it as a user prompt and writes an `.ack` file.
- **Network.** Only the Pokémon mode uses the network. It downloads public data and sprites from the PokeAPI projects on GitHub (`https://raw.githubusercontent.com/PokeAPI/pokeapi/...` and `https://raw.githubusercontent.com/PokeAPI/sprites/...`) the first time they are needed, and caches them. Nothing about you or your sessions is sent anywhere.
- **Not run by the plugin.** `backup_pokemon.sh` is an optional daily backup of the Pokémon save. It runs only if you install it yourself with the repository's `install.sh --pokemon-backup`.

## Fan project notice

The Pokémon mode is an unofficial fan project. It is not affiliated with or endorsed by Nintendo, Game Freak or The Pokémon Company. Pokémon names and sprites belong to their owners and are fetched from PokeAPI at run time; none are bundled in this plugin.

## License

MIT
