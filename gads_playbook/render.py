"""Markdown rendering helpers shared by every calculator."""

def table(rows, columns, headers=None):
    headers = headers or columns
    def cell(v):
        return str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(cell(r.get(c)) for c in columns) + " |")
    return "\n".join(lines)

def money(micros, currency=""):
    v = (micros or 0) / 1_000_000
    s = f"{v:,.2f}"
    return f"{currency} {s}".strip()

def pct(x, digits=1):
    if x is None:
        return "n/a"
    return f"{x * 100:.{digits}f}%"

def ratio(x, digits=2):
    if x is None:
        return "n/a"
    return f"{x:.{digits}f}x"
