#!/usr/bin/env python3
"""piggyback — install/manage codegraph-piggyback hook scripts.

Wires the repo's hook scripts (impact-analyzer, codegraph-gate, …) into
Claude Code's settings.json. Stays decoupled from codegraph itself:
codegraph is installed officially (install.sh / npm); this only registers
hooks that *query* it.

Two roles:
  - DEV machine (where you develop): edit scripts + `piggyback add/rm` to
    mutate manifest.json, then `git commit && git push`. Source of truth.
  - ANY machine (consumer): `piggyback install` / `init` / `update` pull the
    newest manifest from your remote and make settings.json MATCH it —
    adding new hooks AND removing ones the manifest no longer lists.

Design:
  - The repo checkout IS the install root (cloned to ~/.codegraph-piggyback by
    install.sh). Hooks point at absolute paths under it, so new script content
    ships via `git pull` with zero settings.json churn.
  - manifest.json declares each script's event/matcher/scope.
  - RECONCILE, not add-only: install/init/update sync settings.json to the
    manifest. A hook is "ours" (removable) iff its command runs a script under
    the install root; your own hand-added hooks are never touched.
  - Idempotent + surgical: dedupe on command string, never clobber siblings,
    abort rather than corrupt an unparseable settings file.

Commands:
  install                 self-update + install codegraph (if absent) +
                          reconcile global hooks + install the `piggyback` launcher
  init                    self-update + index repo (if needed) + reconcile repo hooks
  update                  self-update + reconcile global (and repo, if cwd indexed)
  add <name> ...          DEV: upsert a manifest entry, then apply locally
  rm <name>               DEV: delete a manifest entry, then apply locally
  register / unregister   manual single-script add / remove (override)
  uninstall               remove every hook we own + the launcher
  status                  show what's registered where
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = Path(os.environ.get("PIGGYBACK_MANIFEST", ROOT / "manifest.json"))
HOOK_TIMEOUT = 5  # seconds; gate/impact both return fast
CODEGRAPH_INSTALL_URL = "https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh"
KNOWN_EVENTS = {  # not exhaustive; used only to warn on likely typos in `add`
    "PreToolUse", "PostToolUse", "UserPromptSubmit", "SessionStart",
    "Stop", "SubagentStart", "SubagentStop", "PreCompact",
}


# ── manifest ──────────────────────────────────────────────────────────────────

def load_manifest_doc() -> dict:
    try:
        data = json.loads(MANIFEST.read_text())
    except FileNotFoundError:
        die(f"manifest not found: {MANIFEST}")
    except json.JSONDecodeError as e:
        die(f"manifest.json is not valid JSON: {e}")
    if not isinstance(data.get("scripts"), dict):
        die("manifest.json missing top-level 'scripts' object")
    return data


def load_manifest() -> dict:
    return load_manifest_doc()["scripts"]


def save_manifest_doc(doc: dict) -> None:
    tmp = MANIFEST.with_suffix(MANIFEST.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n")
    os.replace(tmp, MANIFEST)


def script_entry(scripts: dict, name: str) -> dict:
    if name not in scripts:
        die(f"unknown script '{name}'. Known: {', '.join(sorted(scripts)) or '(none)'}")
    return scripts[name]


def hook_command(entry: dict) -> str:
    """The exact command string written into settings.json — also the
    dedupe/ownership key, so it must be stable across runs."""
    abs_path = (ROOT / entry["script"]).resolve()
    if not abs_path.exists():
        warn(f"script file missing (registering anyway): {abs_path}")
    return f"python3 {shlex.quote(str(abs_path))}"


def is_owned(command: str) -> bool:
    """A hook is ours (and thus removable on reconcile) iff its command runs a
    script under the install root. Distinguishes our hooks from the user's own."""
    return isinstance(command, str) and command.startswith("python3 ") and str(ROOT) in command


# ── settings.json paths + io ──────────────────────────────────────────────────

def settings_path(scope: str) -> Path:
    if scope == "global":
        return Path.home() / ".claude" / "settings.json"
    if scope == "repo":
        return Path.cwd() / ".claude" / "settings.json"
    die(f"bad scope '{scope}' (want global|repo)")


def read_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        text = path.read_text()
    except OSError as e:
        die(f"cannot read {path}: {e}")
    if not text.strip():
        return {}
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        die(f"{path} exists but is not valid JSON ({e}). Fix it by hand, then re-run.")
    if not isinstance(obj, dict):
        die(f"{path} top-level is not a JSON object; refusing to edit.")
    return obj


def write_settings(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2) + "\n")
    os.replace(tmp, path)  # atomic


# ── hook add / remove primitives ──────────────────────────────────────────────

def _event_groups(settings: dict, event: str) -> list:
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        die("settings.json 'hooks' is not an object; refusing to edit.")
    groups = hooks.setdefault(event, [])
    if not isinstance(groups, list):
        die(f"settings.json hooks.{event} is not an array; refusing to edit.")
    return groups


def add_hook(settings: dict, event: str, matcher: str, command: str) -> bool:
    """Add command under (event, matcher). True if changed. Dedupe on
    (matcher, command); preserve sibling hooks/groups."""
    groups = _event_groups(settings, event)
    for g in groups:
        if isinstance(g, dict) and g.get("matcher") == matcher:
            g.setdefault("hooks", [])
            if any(isinstance(h, dict) and h.get("command") == command for h in g["hooks"]):
                return False
            g["hooks"].append({"type": "command", "command": command, "timeout": HOOK_TIMEOUT})
            return True
    groups.append({
        "matcher": matcher,
        "hooks": [{"type": "command", "command": command, "timeout": HOOK_TIMEOUT}],
    })
    return True


def _prune_empty(settings: dict) -> None:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event in list(hooks.keys()):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        hooks[event] = [g for g in groups
                        if not (isinstance(g, dict) and isinstance(g.get("hooks"), list) and not g["hooks"])]
        if not hooks[event]:
            del hooks[event]
    if not hooks:
        settings.pop("hooks", None)


def remove_hook(settings: dict, event: str, matcher: str, command: str) -> bool:
    """Remove an exact (event, matcher, command) hook. True if changed."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict) or not isinstance(hooks.get(event), list):
        return False
    changed = False
    for g in hooks[event]:
        if isinstance(g, dict) and g.get("matcher") == matcher and isinstance(g.get("hooks"), list):
            before = len(g["hooks"])
            g["hooks"] = [h for h in g["hooks"]
                          if not (isinstance(h, dict) and h.get("command") == command)]
            if len(g["hooks"]) != before:
                changed = True
    if changed:
        _prune_empty(settings)
    return changed


# ── reconcile: make a scope's settings.json MATCH the manifest ─────────────────

def desired_for_scope(scope: str) -> set:
    """Set of (event, matcher, command) the manifest wants for this scope."""
    want = set()
    for entry in load_manifest().values():
        if entry.get("scope") != scope:
            continue
        cmd = hook_command(entry)
        for h in entry.get("hooks", []):
            want.add((h["event"], h["matcher"], cmd))
    return want


def reconcile(scope: str) -> tuple[int, int]:
    """Sync settings.json[scope] to the manifest. Returns (added, removed).
    Removes only OWNED hooks no longer desired; leaves the user's own hooks
    and any other scope's hooks untouched."""
    path = settings_path(scope)
    settings = read_settings(path)
    want = desired_for_scope(scope)

    removed = 0
    hooks = settings.get("hooks")
    if isinstance(hooks, dict):
        for event in list(hooks.keys()):
            groups = hooks.get(event)
            if not isinstance(groups, list):
                continue
            for g in groups:
                if not isinstance(g, dict) or not isinstance(g.get("hooks"), list):
                    continue
                matcher = g.get("matcher")
                kept = []
                for h in g["hooks"]:
                    cmd = h.get("command", "") if isinstance(h, dict) else ""
                    stale = is_owned(cmd) and (event, matcher, cmd) not in want
                    if stale:
                        removed += 1
                    else:
                        kept.append(h)
                g["hooks"] = kept
        _prune_empty(settings)

    added = 0
    for (event, matcher, cmd) in want:
        if add_hook(settings, event, matcher, cmd):
            added += 1

    if added or removed:
        write_settings(path, settings)
    return added, removed


def reconcile_report(scope: str) -> None:
    added, removed = reconcile(scope)
    path = settings_path(scope)
    if added or removed:
        ok(f"synced {scope} ({path}): +{added} hook(s), -{removed} stale")
    else:
        ok(f"{scope} already in sync ({path})")


# ── self-update ───────────────────────────────────────────────────────────────

def self_update(args) -> None:
    """git pull --ff-only the install root before acting, so a consumer always
    runs the newest manifest/scripts. Best-effort: offline / dirty tree /
    non-fast-forward → warn and proceed on the local copy (never blocks)."""
    if getattr(args, "no_update", False):
        return
    if not (ROOT / ".git").is_dir():
        return  # not a git checkout (tarball/dev copy) — nothing to pull
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "pull", "--ff-only"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            warn("self-update skipped (offline / local changes / non-fast-forward); using local copy.")
    except Exception:
        warn("self-update skipped (git unavailable or timed out); using local copy.")


# ── codegraph + launcher ──────────────────────────────────────────────────────

def check_codegraph(warn_only: bool) -> bool:
    found = shutil.which("codegraph") is not None
    if not found and warn_only:
        warn("`codegraph` not on PATH. Hooks register fine, but the scripts "
             "no-op until codegraph is installed + a repo is indexed.")
    return found


def install_codegraph() -> None:
    """Run codegraph's OFFICIAL installer (stock, not a fork). Best-effort."""
    info(f"codegraph not found — installing stock codegraph via {CODEGRAPH_INSTALL_URL}")
    rc = subprocess.call(f"curl -fsSL {shlex.quote(CODEGRAPH_INSTALL_URL)} | sh", shell=True)
    if rc != 0:
        warn(f"codegraph installer exited {rc}; continuing with hook registration.")
    elif shutil.which("codegraph") is None:
        warn("codegraph installed but not on this shell's PATH yet — add its bin dir "
             "(usually ~/.local/bin) to PATH, or restart your shell.")
    else:
        ok("stock codegraph installed.")


def install_launcher() -> None:
    """Drop a `piggyback` launcher on PATH so you run `piggyback init`, not
    `python3 ~/.codegraph-piggyback/piggyback.py init`."""
    bindir = Path.home() / ".local" / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    launcher = bindir / "piggyback"
    launcher.write_text(f'#!/bin/sh\nexec python3 "{ROOT / "piggyback.py"}" "$@"\n')
    launcher.chmod(0o755)
    ok(f"launcher → {launcher}")
    if str(bindir) not in os.environ.get("PATH", "").split(os.pathsep):
        warn(f'{bindir} not on PATH — add it: export PATH="$HOME/.local/bin:$PATH"')


def remove_launcher() -> None:
    launcher = Path.home() / ".local" / "bin" / "piggyback"
    if launcher.exists():
        launcher.unlink()
        ok(f"removed launcher {launcher}")


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_install(args) -> None:
    self_update(args)
    if not check_codegraph(warn_only=True):
        if args.no_codegraph:
            warn("skipping codegraph install (--no-codegraph); hooks no-op until it's present.")
        else:
            install_codegraph()
    reconcile_report("global")
    install_launcher()
    restart_note()


def cmd_init(args) -> None:
    self_update(args)
    if (Path.cwd() / ".codegraph").is_dir():
        ok("repo already indexed (.codegraph/ present) — skipping `codegraph init`")
    elif not check_codegraph(warn_only=False):
        die("codegraph not on PATH and repo not indexed. Run `piggyback install` "
            "first, then re-run `piggyback init`.")
    else:
        info("running `codegraph init`…")
        rc = subprocess.call(["codegraph", "init"])
        if rc != 0:
            die(f"`codegraph init` exited {rc}; not reconciling repo hooks.")
    reconcile_report("repo")
    restart_note()


def cmd_update(args) -> None:
    self_update(args)
    reconcile_report("global")
    if (Path.cwd() / ".codegraph").is_dir():
        reconcile_report("repo")
    info("restart your agent session to pick up new hooks/scripts.")


def cmd_register(args) -> None:
    self_update(args)
    scripts = load_manifest()
    entry = script_entry(scripts, args.name)
    scope = args.scope or entry.get("scope")
    if scope not in ("global", "repo"):
        die(f"'{args.name}' has no scope in manifest; pass --scope global|repo")
    path = settings_path(scope)
    settings = read_settings(path)
    cmd = hook_command(entry)
    changed = False
    for h in entry.get("hooks", []):
        if add_hook(settings, h["event"], h["matcher"], cmd):
            changed = True
    if changed:
        write_settings(path, settings)
    ok(f"{'registered' if changed else 'already present'}: '{args.name}' in {path}")
    restart_note()


def cmd_unregister(args) -> None:
    scripts = load_manifest()
    entry = script_entry(scripts, args.name)
    scope = args.scope or entry.get("scope")
    if scope not in ("global", "repo"):
        die(f"'{args.name}' has no scope in manifest; pass --scope global|repo")
    path = settings_path(scope)
    if not path.exists():
        ok(f"no settings at {path} — nothing to remove")
        return
    settings = read_settings(path)
    cmd = hook_command(entry)
    changed = False
    for h in entry.get("hooks", []):
        if remove_hook(settings, h["event"], h["matcher"], cmd):
            changed = True
    if changed:
        write_settings(path, settings)
    ok(f"{'unregistered' if changed else 'not present'}: '{args.name}' in {path}")


def cmd_uninstall(args) -> None:
    """Remove every hook we own from a scope (global by default) + the launcher."""
    path = settings_path(args.scope)
    if path.exists():
        settings = read_settings(path)
        removed = 0
        hooks = settings.get("hooks")
        if isinstance(hooks, dict):
            for event in list(hooks.keys()):
                for g in hooks.get(event, []):
                    if isinstance(g, dict) and isinstance(g.get("hooks"), list):
                        before = len(g["hooks"])
                        g["hooks"] = [h for h in g["hooks"]
                                      if not (isinstance(h, dict) and is_owned(h.get("command", "")))]
                        removed += before - len(g["hooks"])
            _prune_empty(settings)
        if removed:
            write_settings(path, settings)
        ok(f"removed {removed} owned hook(s) from {path}")
    if args.scope == "global":
        remove_launcher()


def cmd_add(args) -> None:
    """DEV: upsert a manifest entry (overwrite by name = add or full update)."""
    hooks = []
    for spec in args.hook:
        if ":" not in spec:
            die(f"--hook must be EVENT:MATCHER, got {spec!r}")
        event, matcher = spec.split(":", 1)
        if not event or not matcher:
            die(f"--hook must be EVENT:MATCHER, got {spec!r}")
        if event not in KNOWN_EVENTS:
            warn(f"'{event}' is not a common Claude hook event — typo? (continuing)")
        hooks.append({"event": event, "matcher": matcher})

    if not (ROOT / args.script).exists():
        warn(f"script file not found under repo: {ROOT / args.script}")

    doc = load_manifest_doc()
    existed = args.name in doc["scripts"]
    doc["scripts"][args.name] = {"script": args.script, "scope": args.scope, "hooks": hooks}
    save_manifest_doc(doc)
    ok(f"manifest: {'updated' if existed else 'added'} '{args.name}'")
    info("commit + push to propagate — consumers apply it on `piggyback init`/`update`.")
    if not args.no_apply:
        reconcile_report(args.scope)


def cmd_rm(args) -> None:
    """DEV: delete a manifest entry, then reconcile so its hook is dropped locally."""
    doc = load_manifest_doc()
    if args.name not in doc["scripts"]:
        die(f"no manifest entry '{args.name}'")
    scope = doc["scripts"][args.name].get("scope")
    del doc["scripts"][args.name]
    save_manifest_doc(doc)
    ok(f"manifest: removed '{args.name}'")
    info("commit + push to propagate — consumers drop it on `piggyback init`/`update`.")
    if not args.no_apply and scope in ("global", "repo"):
        reconcile_report(scope)


def cmd_status(args) -> None:
    scripts = load_manifest()
    for scope in ("global", "repo"):
        path = settings_path(scope)
        print(f"\n{scope}: {path}" + ("" if path.exists() else "  (none)"))
        settings = read_settings(path) if path.exists() else {}
        for name, entry in scripts.items():
            if entry.get("scope") != scope:
                continue
            cmd = hook_command(entry)
            present = []
            for h in entry.get("hooks", []):
                groups = settings.get("hooks", {}).get(h["event"], [])
                hit = any(isinstance(g, dict) and g.get("matcher") == h["matcher"]
                          and any(isinstance(x, dict) and x.get("command") == cmd
                                  for x in g.get("hooks", []))
                          for g in groups)
                present.append(f"{h['event']}({h['matcher']}){'' if hit else ' [MISSING]'}")
            mark = "x" if all("[MISSING]" not in p for p in present) else " "
            print(f"  [{mark}] {name}: {', '.join(present)}")


# ── helpers ───────────────────────────────────────────────────────────────────

def restart_note() -> None:
    info("note: Claude Code loads hooks at session start — restart your agent session to activate.")


def info(msg: str) -> None:
    print(msg, file=sys.stderr)


def ok(msg: str) -> None:
    print(f"✓ {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    print(f"! {msg}", file=sys.stderr)


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="piggyback", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_no_update(sp):
        sp.add_argument("--no-update", action="store_true",
                        help="skip the git-pull self-update for this run")

    pin = sub.add_parser("install", help="codegraph + reconcile global hooks + launcher")
    pin.add_argument("--no-codegraph", action="store_true", help="don't auto-install codegraph")
    add_no_update(pin)
    pin.set_defaults(fn=cmd_install)

    pi = sub.add_parser("init", help="index repo if needed + reconcile repo hooks")
    add_no_update(pi)
    pi.set_defaults(fn=cmd_init)

    pup = sub.add_parser("update", help="self-update + reconcile global (and repo if indexed)")
    add_no_update(pup)
    pup.set_defaults(fn=cmd_update)

    pa = sub.add_parser("add", help="DEV: upsert a manifest entry")
    pa.add_argument("name")
    pa.add_argument("--script", required=True, help="path relative to repo root")
    pa.add_argument("--scope", required=True, choices=["global", "repo"])
    pa.add_argument("--hook", action="append", required=True, metavar="EVENT:MATCHER",
                    help="repeatable, e.g. --hook 'PostToolUse:Edit|Write'")
    pa.add_argument("--no-apply", action="store_true", help="edit manifest only, don't reconcile locally")
    pa.set_defaults(fn=cmd_add)

    prm = sub.add_parser("rm", help="DEV: delete a manifest entry")
    prm.add_argument("name")
    prm.add_argument("--no-apply", action="store_true", help="edit manifest only, don't reconcile locally")
    prm.set_defaults(fn=cmd_rm)

    pr = sub.add_parser("register", help="manually add one script's hooks")
    pr.add_argument("name")
    pr.add_argument("-s", "--scope", choices=["global", "repo"])
    add_no_update(pr)
    pr.set_defaults(fn=cmd_register)

    pu = sub.add_parser("unregister", help="manually remove one script's hooks")
    pu.add_argument("name")
    pu.add_argument("-s", "--scope", choices=["global", "repo"])
    pu.set_defaults(fn=cmd_unregister)

    pun = sub.add_parser("uninstall", help="remove all owned hooks + launcher")
    pun.add_argument("-s", "--scope", choices=["global", "repo"], default="global")
    pun.set_defaults(fn=cmd_uninstall)

    sub.add_parser("status", help="show registered hooks").set_defaults(fn=cmd_status)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
