# History Gen

A small CLI tool that generates a history.md file from your Git commit history.
Each entry includes:
	•	Commit message (prompt)
	•	Commit hash and date (converted to Eastern Time)
	•	File name
	•	Line numbers
	•	Added (+) and removed (-) lines, colorized in Markdown with diff fences

⸻

## Installation

Make sure you have pipx installed:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Then install this package (from your local repo):


```bash
pipx install .
```

Now the git-history-gen command is available globally.

⸻

## Usage

Run from the root of any Git repository:

git-history-gen [OPTIONS]

Common options:
	•	--user-id "<email>"
Filter commits by author email (or regex pattern).
Example:


```bash
git-history-gen --user-id "user@example.com"
```

	•	--limit N
Limit the number of commits (most recent first).
Example:

```bash
git-history-gen --limit 20
```

	•	--output FILE
Output file name (default: history.md).
Example:

```bash
git-history-gen --output my_changes.md
``````



⸻

## Example Output

### Fix parser for headers
*1a2b3c4 — 2025-09-02 08:34:56 -0400 (ET)*

**File:** `src/parser.py`

```diff
- L42: header = line.split("@@")[1]
+ L42: header = line.split("@@")[1].strip()
+ L88: return result
```


⸻

Updating

If you pull changes to this repo, reinstall with:

pipx install . --force

