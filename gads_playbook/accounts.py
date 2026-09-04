"""List accessible customers under the manager account. Read-only, search_stream only."""
from . import render
from .pull import make_client, api_error

QUERY = ("SELECT customer_client.id, customer_client.descriptive_name, customer_client.manager, customer_client.level, "
         "customer_client.currency_code, customer_client.status FROM customer_client WHERE customer_client.level <= 1")

def run(login_customer_id, client=None):
    client = client or make_client()
    svc = client.get_service("GoogleAdsService")
    try:
        batches = list(svc.search_stream(customer_id=login_customer_id, query=QUERY))
    except Exception as e:  # GoogleAdsException, transport, or auth error from the API client
        raise api_error(QUERY, e) from e
    out = []
    for batch in batches:
        for row in batch.results:
            c = row.customer_client
            out.append({"id": str(c.id), "name": c.descriptive_name, "manager": "yes" if c.manager else "", "level": str(c.level),
                        "currency": c.currency_code, "status": getattr(c.status, "name", str(c.status))})
    return out

def cmd_accounts(args):
    rows = run(args.login_customer.replace("-", ""))
    print(render.table(rows, ["id", "name", "manager", "level", "currency", "status"], ["Customer ID", "Name", "Manager", "Level", "Currency", "Status"]))
    print(f"{len(rows)} accounts under {args.login_customer}")
    return 0

def register(sub, add_common):
    p = sub.add_parser("accounts", help="list client accounts under the manager account")
    p.add_argument("--login-customer", required=True, help="manager (MCC) id, digits only")
    p.set_defaults(func=cmd_accounts)
