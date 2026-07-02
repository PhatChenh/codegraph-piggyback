# Piggyback — simple install & update guide

No jargon. Two things you ever do: **install once** on a new machine, **update** later.

You need a Mac with **Claude Code** installed. That's it.

---

## 1. Install (once per machine)

Open Terminal. Paste this, press Enter:

```sh
curl -fsSL https://raw.githubusercontent.com/PhatChenh/codegraph-piggyback/main/install.sh | sh
```

What it does: downloads piggyback, sets it up, wires the global helper. One line.

Then, for **each project** where you want the smart code lookup:

```sh
cd /path/to/your/project
piggyback init --all
```

What it does: turns on piggyback's hooks for that project. Safe to re-run.

Last step — **restart Claude Code** (quit and reopen). Hooks only load at startup.

---

## 2. Update (later, when the team improved piggyback)

Two commands. Once per machine, then once per project.

**A. Anywhere — refreshes the machine-wide helper:**

```sh
piggyback update
```

**B. Inside each project — refreshes that project's hooks:**

```sh
cd /path/to/your/project
piggyback init --all
```

Then **restart Claude Code**.

That's the whole update routine.

---

## Troubleshooting (one line each)

- `piggyback: command not found` → run `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc`, restart Terminal.
- Hooks not firing → you forgot to restart Claude Code. Quit and reopen.
- Weird path errors on Read/Grep → run `piggyback update` + `piggyback init --all` in the project, restart. (This is the bug this guide was written after.)

## Uninstall

```sh
piggyback uninstall
rm -rf ~/.codegraph-piggyback
```