"""CSV, number, and workspace helpers. Stdlib only."""
import csv, json, re
from datetime import date
from pathlib import Path

class MissingInput(Exception):
    """Raised when a required file or column is absent. Message names the file and what would produce it."""

_NUM = re.compile(r"[^0-9.\-]")

def _decode(path):
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")

def read_csv(path):
    """Read a CSV or TSV (utf-8, utf-8-sig, or utf-16) into a list of dicts. Delimiter is sniffed from the header line."""
    text = _decode(path)
    lines = text.splitlines()
    if not lines:
        return []
    delim = "\t" if lines[0].count("\t") > lines[0].count(",") else ","
    return [dict(r) for r in csv.DictReader(lines, delimiter=delim)]

def write_csv(path, rows, columns):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})

def money_to_micros(text):
    if text is None:
        return None
    s = str(text).strip()
    if s in ("", "--", "-"):
        return None
    s = _NUM.sub("", s)
    if s in ("", "-", "."):
        return None
    return int(round(float(s) * 1_000_000))

def micros_to_money(micros):
    return (micros or 0) / 1_000_000

def parse_percent(text):
    if text is None:
        return None
    s = str(text).strip()
    if s in ("", "--", "-"):
        return None
    had_pct = "%" in s
    s = _NUM.sub("", s)
    if s in ("", "-", "."):
        return None
    v = float(s)
    return v / 100 if had_pct else v

def parse_number(text):
    if text is None:
        return 0.0
    s = _NUM.sub("", str(text))
    return float(s) if s not in ("", "-", ".") else 0.0

def require(path, columns):
    path = Path(path)
    if not path.exists():
        raise MissingInput(f"missing {path.name} at {path}. Run gads pull or gads normalise first.")
    rows = read_csv(path)
    header = set(rows[0].keys()) if rows else set()
    if rows:
        missing = [c for c in columns if c not in header]
        if missing:
            raise MissingInput(f"{path.name} is missing columns: {', '.join(missing)}")
    return rows

def load_workspace(ws):
    p = Path(ws) / "gads.json"
    if not p.exists():
        raise MissingInput(f"no gads.json in {ws}. Run gads setup (or gads pull) first.")
    return json.loads(p.read_text())

def save_workspace(ws, data):
    p = Path(ws) / "gads.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

def run_dir(ws, day=None):
    d = Path(ws) / "runs" / (day or date.today().isoformat())
    d.mkdir(parents=True, exist_ok=True)
    return d
