"""
seed_olist_subset.py
--------------------

Purpose:
    Seed the Insightful-Orders API with a realistic subset of the Olist e-commerce dataset.

What it does:
    1. Registers a demo merchant (if not already registered).
    2. Logs in to obtain a JWT access token.
    3. Reads downsampled Olist orders from data/sample/olist_orders_dataset.csv.
    4. For each order:
        - Generates a fake customer block (email, first_name, last_name).
        - Maps order_id → external_id, order_status → status, purchase_timestamp → created_at.
    5. Sends data in batches of 200 via POST /orders/bulk.

Usage:
    $ python scripts/seed_olist_subset.py

Notes:
    - Adjust SAMPLE_FILE or BATCH_SIZE if needed.
    - Requires API_URL environment variable or defaults to local dev (http://localhost:5000).
    - Safe to re-run; duplicate emails will just map to same customers.
"""

import os
import requests
import pandas as pd
import argparse

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
API_URL = os.getenv("API_URL", "http://localhost:5050")
REGISTER_URL = f"{API_URL}/auth/register"
LOGIN_URL = f"{API_URL}/auth/login"
BULK_ORDERS_URL = f"{API_URL}/orders"

SAMPLE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "sample", "olist_orders_dataset.csv")
BATCH_SIZE = 200

DEMO_EMAIL = "olist_demo@example.com"
DEMO_PASSWORD = "your_password"


# ----------------------------------------------------------------------
# Auth Helpers
# ----------------------------------------------------------------------
def register_demo_user():
    """Register the demo merchant (idempotent)."""
    payload = {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
    try:
        r = requests.post(REGISTER_URL, json=payload, timeout=10)
        if r.status_code == 201:
            print("✅ Demo merchant registered.")
        elif r.status_code == 409:
            print("ℹ️ Demo merchant already exists.")
        else:
            print(f"⚠️ Unexpected register status {r.status_code}: {r.text}")
    except Exception as e:
        print(f"⚠️ Error registering demo merchant: {e}")


def login_demo_user():
    """Login and return JWT token."""
    r = requests.post(LOGIN_URL, json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=10)
    r.raise_for_status()
    token = r.json()["access_token"]
    print("🔑 Logged in, got token.")
    return token


# ----------------------------------------------------------------------
# Data Loading
# ----------------------------------------------------------------------
def load_orders():
    """Load downsampled orders CSV into DataFrame."""
    if not os.path.exists(SAMPLE_FILE):
        raise FileNotFoundError(f"Missing {SAMPLE_FILE}")
    df = pd.read_csv(SAMPLE_FILE)
    print(f"📂 Loaded {len(df)} orders from {SAMPLE_FILE}")
    return df


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def chunked_iterable(iterable, size):
    """Yield successive chunks of size `size` from iterable."""
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def make_customer_from_row(row):
    """Generate a fake customer block from order_id + customer_id (if present)."""
    cust_id = row.get("customer_id", row["order_id"])  # fallback to order_id
    return {
        "email": f"{cust_id}@olistdemo.com",
        "first_name": "Demo",
        "last_name": str(cust_id)[:6],  # short suffix to differentiate
    }


# ----------------------------------------------------------------------
# Main Seeding Logic
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Build payloads but do not POST to API")
    args = parser.parse_args()

    register_demo_user()
    token = login_demo_user()
    headers = {"Authorization": f"Bearer {token}"}

    df = load_orders()
    orders = []
    for _, row in df.iterrows():
        customer = make_customer_from_row(row)
        orders.append(
            {
                "customer": customer,
                "external_id": str(row["order_id"]),
                "status": row.get("order_status", "created"),
                "currency": "BRL",
                "total_amount": "100.00",
            }
        )

    if args.dry_run:
        print(f"💡 DRY RUN: prepared {len(orders)} orders")
        print("Example payload:", {"orders": orders[:2]})
        return

    for chunk in chunked_iterable(orders, BATCH_SIZE):
        payload = {"orders": chunk}
        r = requests.post(BULK_ORDERS_URL, headers=headers, json=payload, timeout=20)
        if r.status_code == 201:
            created = len(r.json()["created"])
            print(f"✅ Bulk created {created} orders.")
        else:
            print(f"⚠️ Failed bulk create ({r.status_code}): {r.text}")


# Entrypoint
if __name__ == "__main__":
    main()
