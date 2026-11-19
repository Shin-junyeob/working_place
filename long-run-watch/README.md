# long-run-watch

Long Bash commands are easy to lose track of. This plugin gives each one an expected duration and shows it in Claude Code's status line while the command runs, for example `⏳ npm test · 2 min / est. 3 min`. When a command runs past its estimate, a notice pops up, so you or Claude can check whether it is stuck instead of waiting for it. Commands that took over a minute show a notice when they finish. Background commands can't be followed to the end, so a notice says when one starts and reminds you to check on it once its estimate has passed.

## Install

```
/plugin install long-run-watch --marketplace Shin-junyeob/working_place
```

Full guide: https://github.com/Shin-junyeob/working_place

## How the estimate is made

1. The median of the same command's last five runs, remembered across sessions.
2. Otherwise a duration written in the command's description, such as "(about 30 min)" or "(약 30 분)".
3. Otherwise no estimate, with a warning after 10 minutes.

Commands that finish within 30 seconds show nothing and are not recorded.

## What it runs, reads, writes and fetches

- **Commands.** None. It only observes Bash tool calls that Claude makes.
- **Data it keeps.** Up to five past durations per command, in Claude Code's plugin store (`$.store`) on your machine.
- **Files it reads.** `~/.claude/pane-tools/settings.json`, only to pick Korean or English text. That file is shared with the pane-tools plugin from the same repository and may not exist.
- **Network.** None. Nothing is sent anywhere.

## License

MIT
