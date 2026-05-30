# inReach 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/vinay-singh-engineer/inreach/blob/main/LICENSE)
![CI](https://github.com/vinay-singh-engineer/inreach/actions/workflows/ci.yml/badge.svg)


TCP connectivity checker for one or many hosts. A Python tool available as both a **CLI** and a **Web UI** — verify reachability from any source host to any destination:port, with live results as each check completes.

---

## How it works

**CLI — single host:**

```bash
python inReach.py --source host01.example.com  --destination google.com --port 443
```

```
╭─ inReach  v1.0.0 ───────────────────────────────────────╮
│  Destination: google.com   Port: 443                    │
╰─────────────────────────────────────────────────────────╯

      Source              Destination          Status           Detail
  ──────────────────────────────────────────────────────────────────────
 ✔   host01.example.com   google.com:443       ● REACHABLE      Connection to google.com 443 port [tcp/https] succeeded!
```

**CLI — many hosts from a file:**

```bash
python inReach.py --sourceFile hosts.txt --destination google.com,8.8.8.8 --port 443
```

```
 ⠿   host01.example.com   google.com:443     checking… (1/8)
 ✔   host01.example.com   google.com:443     ● REACHABLE   …
 ✔   host02.example.com   google.com:443     ● REACHABLE   …
 ✘   host03.example.com   8.8.8.8:443        ● UNREACHABLE Timed out

╭─ Summary ─────╮
│ Total       8 │
│ Reachable   6 │
│ Unreachable 2 │
╰───────────────╯
```

**Web UI:**

```bash
python app.py
# → http://127.0.0.1:5050
```

Paste hosts, pick source, enter destination and port, click **Check** or **Check All Hosts**. Results stream in one by one.

---

## Quick start

**Prerequisites:** Python 3.9+, SSH access to source hosts (for remote checks).

```bash
git clone https://github.com/vinay-singh-engineer/inreach.git
cd inreach
pip install -r requirements.txt
```

**CLI:**

```bash
python inReach.py --help
```

**Web UI:**

```bash
python app.py
```

Open `http://127.0.0.1:5050` in your browser.

---

## CLI Usage

```bash
# Check from localhost
python inReach.py --destination google.com --port 443

# Check from a specific source host
python inReach.py --source myhost.example.com --destination google.com --port 443

# Check from all hosts in a file
python inReach.py --sourceFile /path/to/inventory --destination google.com --port 443

# Check multiple destinations (comma-separated)
python inReach.py --sourceFile hosts.txt --destination google.com,8.8.8.8 --port 443

# Show version
python inReach.py --version
```

| Flag | Description |
| :--- | :--- |
| `-d, --destination` | Destination host(s) — comma-separated for multiple **(required)** |
| `-s, --source` | Source host to check from (default: `localhost`) |
| `-p, --port` | Port number (default: `443`) |
| `-f, --sourceFile` | Path to hosts file — one per line or Ansible INI inventory |
| `-v, --version` | Show version and exit |
| `-h, --help` | Show help message |

---

## Web UI Usage

1. **Paste hosts** (one per line) or point to an **inventory file path** → click **Load Hosts**
2. Select or type a **Source** (auto-populated from loaded hosts)
3. Enter **Destination** host or IP and **Port**
4. Click **Check** (single source) or **Check All Hosts** (iterates every loaded host)
5. Results appear one-by-one as each check completes — no waiting for the full batch

---

## Running tests

```bash
pytest tests/ -v
```

24 unit tests covering `_clean_output`, `parse_hosts_file`, `check_local`, `run_check`, and version format. No network access required — remote calls are mocked.

---

## Project structure

```
connectivityCheckTool/
├── app.py                  # Flask web server — REST API + serves UI
├── inReach.py              # CLI — rich terminal output, spinner per host
├── requirements.txt        # Python dependencies (Flask + rich)
├── VERSION                 # Single source of truth for version number
└── templates/
    └── index.html          # Web UI (Tailwind CSS, vanilla JS)
```

---

## How remote checks work

For a **localhost** source, inReach opens a TCP socket directly using Python's `socket` module.

For a **remote source**, inReach SSHes into that host and runs `nc -vz <dest> <port>`:

```
inReach → SSH → source host → nc -vz → destination:port
```

SSH gateway banner noise (SSHgate warnings, known-hosts notices, etc.) is automatically stripped from the output — only the relevant `nc` result line is shown.

---

## Stack

| Layer | Technology |
| :--- | :--- |
| CLI | Python 3 — `argparse`, `socket`, `subprocess` |
| CLI output | `rich` — live spinners, colored tables, summary panel |
| Web server | Flask |
| Web UI | Tailwind CSS (CDN), vanilla JS — streaming results |
| Remote check | SSH + `nc -vz` |
| Local check | Python `socket.create_connection` |

---

## Key Design Decisions

**Live streaming results** — Both the CLI and the Web UI show each result as soon as it arrives rather than waiting for the full batch. On a 20-host run you see progress immediately, not a 60-second wait followed by a wall of text.

**Unified check engine** — The same `run_check` function powers localhost checks (Python socket, no SSH overhead) and remote checks (SSH + nc). The CLI and web server both call it — no duplicated logic.

**Source file flexibility** — The `--sourceFile` flag accepts either a plain text file (one host per line) or an Ansible INI-style inventory. Groups, comments, and variable lines are automatically skipped.

**Banner noise filtering** — Internal SSH gateways inject multi-line banners into stderr. inReach strips these before displaying results so the output stays clean regardless of what your SSH proxy emits.

**Comma-separated destinations** — A single command can verify a source-file × destination matrix. All `(source, dest)` pairs are checked sequentially with a live spinner per pair and a summary at the end.

**Exit code** — The CLI exits `0` if all checks pass, `1` if any fail — CI/CD and shell scripts can act on it directly.

---

## License

MIT — use freely, attribute appreciated.

---

## 💻 Author

[Vinay Singh](https://vinay-singh-engineer.github.io)
