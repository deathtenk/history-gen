#!/usr/bin/env python3
"""

Generate a history.md with entries per commit:
- Prompt (commit message)
- File name
- Line number
- Change (+/- line)

Now supports:
  --user-id "<email or pattern>"  # filters commits by author (matches git --author)
  --limit N
  --output history.md

Usage examples:
  python history-gen.py --user-id "henk@yetanalytics.com" --limit 50
  python history-gen.py --user-id ".*@yetanalytics\\.com"   # regex ok
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None  # graceful fallback; will print UTC if tz not available

ET_TZNAME = "America/New_York"

def run(cmd):
    return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).splitlines()

def get_commits(limit=None, user_id=None):
    # %H = hash, %s = subject (commit message), %cI = committer date, strict ISO 8601 in UTC/Z
    # %ae = author email (we also pass --author to git to filter up front)
    fmt = "%H%x1f%s%x1f%cI%x1f%ae"
    cmd = ["git", "log", f"--pretty={fmt}", "--no-color", "--first-parent"]
    if user_id:
        cmd.insert(2, f'--author={user_id}')
    if limit:
        cmd.insert(2, f"-n{limit}")

    for line in run(cmd):
        parts = line.split("\x1f")
        if len(parts) == 4:
            yield {
                "hash": parts[0],
                "subject": parts[1],
                "date_utc": parts[2],   # ISO 8601 with Z
                "author_email": parts[3],
            }

def get_diff_lines(commit_hash):
    # Diff vs first parent, zero context for exact line numbers, text-only
    cmd = [
        "git", "show", "--first-parent", "--no-renames",
        "--unified=0", "--pretty=format:", "--no-color", commit_hash
    ]
    return run(cmd)

def iter_changes(diff_lines):
    """
    Yield dicts:
      {
        'file': 'path/to/file',
        'line': <int>,       # line number in new file for additions, old file for deletions
        'type': 'add'|'del',
        'text': 'line contents without +/-',
      }
    """
    cur_file = None
    old_line = None
    new_line = None

    for raw in diff_lines:
        line = raw.rstrip("\n")

        # File headers
        if line.startswith("diff --git "):
            cur_file = None
            continue
        if line.startswith("+++ "):
            path = line[4:]
            cur_file = path[2:] if path.startswith("b/") else None
            continue
        if line.startswith("--- "):
            continue

        # Binary or no-content hunks
        if "Binary files" in line or line.startswith("GIT binary patch"):
            cur_file = None
            continue

        # Hunk header: @@ -old_start,old_count +new_start,new_count @@
        if line.startswith("@@ "):
            try:
                header = line.split("@@")[1].strip()  # "-a,b +c,d"
                left, right = header.split(" ")
                old_start = int(left.split(",")[0][1:])  # strip '-'
                new_start = int(right.split(",")[0][1:]) # strip '+'
                old_line = old_start
                new_line = new_start
            except Exception:
                old_line = new_line = None
            continue

        if cur_file is None or old_line is None or new_line is None:
            continue
        if not line or line.startswith("\\ No newline at end of file"):
            continue

        if line.startswith("+"):
            yield {"file": cur_file, "line": new_line, "type": "add", "text": line[1:]}
            new_line += 1
        elif line.startswith("-"):
            yield {"file": cur_file, "line": old_line, "type": "del", "text": line[1:]}
            old_line += 1
        else:
            # shouldn't occur with --unified=0, but keep counters aligned
            old_line += 1
            new_line += 1

def to_et(dt_iso_utc: str) -> str:
    """
    Convert strict ISO 8601 UTC (e.g., 2025-09-02T12:34:56Z) to US Eastern Time.
    Returns a full timestamp with numeric offset and ET tag, e.g.:
    2025-09-02 08:34:56 -0400 (ET)
    """
    try:
        # normalize 'Z' to '+00:00' for fromisoformat
        if dt_iso_utc.endswith("Z"):
            dt_iso_utc = dt_iso_utc.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt_iso_utc)
        if ZoneInfo is not None:
            et = dt.astimezone(ZoneInfo(ET_TZNAME))
            return et.strftime("%Y-%m-%d %H:%M:%S %z") + " (ET)"
        else:
            # fallback: show UTC clearly if zoneinfo unavailable
            return dt.strftime("%Y-%m-%d %H:%M:%S +0000") + " (UTC)"
    except Exception:
        # on any parsing issue, return original string for transparency
        return dt_iso_utc + " (raw)"

def write_history(commits, output_path: Path):
    out = []
    out.append("# Change Notes\n")

    for c in commits:
        diff = get_diff_lines(c["hash"])
        changes = list(iter_changes(diff))
        if not changes:
            continue

        dt_et = to_et(c["date_utc"])
        out.append(f"### {c['subject']}  \n*{c['hash'][:7]} — {dt_et}*")
        by_file = {}
        for ch in changes:
            by_file.setdefault(ch["file"], []).append(ch)

        for fname, items in by_file.items():
            out.append(f"\n**File:** `{fname}`\n")
            out.append(f"```diff")
            for ch in items:
                sign = "+" if ch["type"] == "add" else "-"
                ln = ch["line"]
                text = ch["text"].replace("`", "\\`")
                out.append(f"- L{ln}: {sign} {text}")
        out.append("```")

    output_path.write_text("\n".join(out), encoding="utf-8")

def main():
    # Ensure we're in a git repo
    try:
        run(["git", "rev-parse", "--is-inside-work-tree"])
    except subprocess.CalledProcessError:
        print("Error: Not a git repository (or no access to git).", file=sys.stderr)
        sys.exit(1)

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="Limit number of commits (most recent first)")
    ap.add_argument("--output", default="history.md", help="Output file (default: history.md)")
    ap.add_argument(
        "--user-id",
        default=None,
        help="Author filter passed to `git log --author`. Usually the email (e.g., 'henk@yetanalytics.com'), regex allowed."
    )
    args = ap.parse_args()

    commits = list(get_commits(limit=args.limit, user_id=args.user_id))
    if not commits:
        msg = "No commits found"
        if args.user_id:
            msg += f" for author filter: {args.user_id!r}"
        print(msg + ".", file=sys.stderr)
        sys.exit(0)

    write_history(commits, Path(args.output))
    print(f"Wrote {args.output}")

if __name__ == "__main__":
    main()