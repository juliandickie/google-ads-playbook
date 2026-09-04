"""gads command line. Global flags go after the subcommand."""
import argparse, os, sys
from pathlib import Path
from . import __version__, io, schema

API_SUBCOMMANDS = {"auth", "accounts", "pull"}

UV_WITH = ["google-ads>=25", "google-auth-oauthlib>=1.2", "pyyaml>=6"]

def uv_command(argv):
    root = str(Path(__file__).resolve().parents[1])
    cmd = ["uv", "run", "--python", "3.12"]
    for w in UV_WITH:
        cmd += ["--with", w]
    cmd += ["python", "-m", "gads_playbook.cli"] + list(argv)
    return cmd, root

def workspace_from(args):
    ws = getattr(args, "workspace", None) or os.environ.get("GADS_WORKSPACE")
    if not ws:
        raise io.MissingInput("no workspace. Pass --workspace ~/gads/<customer-id> or set GADS_WORKSPACE.")
    return Path(os.path.expanduser(ws))

def add_common(p):
    p.add_argument("--workspace", help="account workspace, default $GADS_WORKSPACE")
    p.add_argument("--run-date", help="YYYY-MM-DD folder under runs/, default today")

def cmd_validate(args):
    ws = workspace_from(args)
    data = io.load_workspace(ws)
    print(f"workspace {ws} customer {data.get('customer_id','?')} currency {data.get('currency','?')} window {data.get('window_start','?')} to {data.get('window_end','?')}")
    present = []
    for name in schema.REPORT_TYPES:
        p = ws / "exports" / f"{name}.csv"
        n = len(io.read_csv(p)) if p.exists() else 0
        print(f"  {name}.csv: {'%d rows' % n if p.exists() else 'missing'}")
        if p.exists():
            present.append(name)
    feed = (ws / "feed.csv").exists() or (ws / "feed.tsv").exists()
    print(f"  feed: {'present' if feed else 'missing'}")
    can = []
    if {"campaigns", "search_terms"} <= set(present): can += ["leakage", "misallocate"]
    if "campaigns" in present: can.append("windows")
    if feed: can.append("feedscore")
    print("can run: " + (", ".join(can) or "nothing yet"))
    return 0

def build_parser():
    p = argparse.ArgumentParser(prog="gads", description="Google Ads playbook tools (read-only).")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="show workspace state and which calculators can run")
    add_common(v); v.set_defaults(func=cmd_validate)
    return p, sub

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in API_SUBCOMMANDS and not os.environ.get("GADS_IN_UV"):
        cmd, root = uv_command(argv)
        env = dict(os.environ, GADS_IN_UV="1", PYTHONPATH=root + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""))
        try:
            os.execvpe(cmd[0], cmd, env)
        except FileNotFoundError:
            print("gads: uv is required for auth, accounts, and pull (brew install uv).", file=sys.stderr)
            return 2
    parser, sub = build_parser()
    # later tasks register subcommands via register_all(sub)
    try:
        from . import registry
        registry.register_all(sub, add_common)
    except ImportError:
        pass
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except io.MissingInput as e:
        print(f"gads {args.cmd}: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
