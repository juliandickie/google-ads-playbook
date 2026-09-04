"""OAuth desktop flow and credential files (spec section 7). gcloud is not required."""
import json, os
from pathlib import Path
from . import io

CONFIG_DIR = Path(os.environ.get("GADS_CONFIG_DIR", Path.home() / ".config" / "google-ads-playbook"))
SCOPES = ["https://www.googleapis.com/auth/adwords"]

def _write_0600(path, text):
    """Create or truncate path with mode 0600 from the first byte written (ruling R27), never a window at the umask."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)

def write_credential_files(config_dir, client_id, client_secret, refresh_token, developer_token, login_customer_id):
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    adc = config_dir / "adc.json"
    _write_0600(adc, json.dumps({"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "type": "authorized_user"}, indent=2) + "\n")
    yaml = config_dir / "google-ads.yaml"
    _write_0600(yaml, "\n".join([f"developer_token: {developer_token}", f"client_id: {client_id}", f"client_secret: {client_secret}",
                               f"refresh_token: {refresh_token}", f"login_customer_id: {login_customer_id}", "use_proto_plus: true"]) + "\n")
    for p in (adc, yaml):  # explicit chmod also corrects a pre-existing file's mode
        os.chmod(p, 0o600)
    return {"adc": adc, "yaml": yaml}

def run_oauth(client_json):
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(client_json), scopes=SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    return creds.client_id, creds.client_secret, creds.refresh_token

def _read_op(ref):
    """Read a developer token from 1Password (ruling R26). Wraps a missing op binary, an unauthenticated
    session, or a bad reference into io.MissingInput naming the reference and the op error text, instead of
    letting a raw traceback escape cmd_auth."""
    import subprocess
    try:
        return subprocess.run(["op", "read", ref], check=True, capture_output=True, text=True).stdout.strip()
    except FileNotFoundError as e:
        raise io.MissingInput(f"op read {ref} failed: the op binary was not found. Install the 1Password CLI, sign in (op signin), or pass --developer-token.") from e
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or str(e)).strip()
        raise io.MissingInput(f"op read {ref} failed: {detail}. Sign in to 1Password (op signin) or pass --developer-token.") from e

def cmd_auth(args):
    client_json = Path(args.client_json).expanduser()
    if not client_json.exists():
        raise io.MissingInput(f"OAuth client file not found: {client_json}. Download the desktop client JSON from Google Cloud Console, APIs and Services, Credentials.")
    token = args.developer_token or (_read_op(args.op_ref) if args.op_ref else None)
    if not token:
        import getpass
        token = getpass.getpass("Google Ads developer token (from the manager account API Center): ").strip()
    cid, csec, rtok = run_oauth(client_json)
    paths = write_credential_files(CONFIG_DIR, cid, csec, rtok, token, args.login_customer_id.replace("-", ""))
    print(f"auth: wrote {paths['adc']} and {paths['yaml']} (mode 600). Set adc_path in the plugin config to {paths['adc']}.")
    return 0

def register(sub, add_common):
    p = sub.add_parser("auth", help="run the OAuth desktop flow and write adc.json and google-ads.yaml")
    p.add_argument("--client-json", required=True, help="OAuth desktop client secrets JSON from Google Cloud Console")
    p.add_argument("--login-customer-id", required=True, help="manager (MCC) customer id, digits only")
    p.add_argument("--developer-token", help="developer token; omit to be prompted")
    p.add_argument("--op-ref", help="1Password reference, e.g. op://<vault>/<item>/<field>")
    p.set_defaults(func=cmd_auth)
