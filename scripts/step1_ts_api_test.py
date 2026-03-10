"""
Step 1 — ThoughtSpot REST API smoke test.

Validates:
  1. Settings loaded from .env
  2. Snowflake connection works (ping)
  3. ThoughtSpot Bearer token acquired
  4. thoughtspot_tml library works (round-trip parse/dump)
  5. TML import pipeline works (export existing table → VALIDATE_ONLY re-import)

Note: VALIDATE_ONLY requires the physical Snowflake table to already be registered
in the ThoughtSpot connection. We reuse the first registered table found in the
connection rather than trying to register a new one via API.

Run:
    python -m scripts.step1_ts_api_test
"""
import sys

import requests
import snowflake.connector
from thoughtspot_tml import Table

from config.settings import Settings
from ts_client.auth import ThoughtSpotAuth
from ts_client.tml_api import TMLClient


def run() -> None:
    print("=" * 60)
    print("ts-demo-factory  |  Step 1: ThoughtSpot API smoke test")
    print("=" * 60)

    # ── Step 1: Load settings ─────────────────────────────────────
    print("\n[1/5] Loading settings from .env …")
    try:
        settings = Settings.from_env()
    except EnvironmentError as exc:
        print(f"[FAIL] {exc}")
        sys.exit(1)
    print(f"      TS host          : {settings.ts_host}")
    print(f"      TS username      : {settings.ts_username}")
    print(f"      Connection name  : {settings.ts_connection_name}")
    print(f"      SF account       : {settings.sf_account}")
    print(f"      SF database      : {settings.sf_database}.{settings.sf_schema}")

    # ── Step 2: Snowflake ping ────────────────────────────────────
    print("\n[2/5] Connecting to Snowflake …")
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.serialization import (
            load_pem_private_key, Encoding, PrivateFormat, NoEncryption,
        )
        with open(settings.sf_private_key_path, "rb") as f:
            private_key = load_pem_private_key(f.read(), password=None, backend=default_backend())
        private_key_der = private_key.private_bytes(
            encoding=Encoding.DER, format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )
        conn = snowflake.connector.connect(
            account=settings.sf_account,
            user=settings.sf_user,
            private_key=private_key_der,
            database=settings.sf_database,
            schema=settings.sf_schema,
            warehouse=settings.sf_warehouse,
            role=settings.sf_role,
        )
        cur = conn.cursor()
        cur.execute("SELECT CURRENT_VERSION()")
        sf_version = cur.fetchone()[0]
        conn.close()
    except Exception as exc:
        print(f"[FAIL] Snowflake: {exc}")
        sys.exit(1)
    print(f"      Snowflake version: {sf_version}")

    # ── Step 3: ThoughtSpot Bearer token ─────────────────────────
    print("\n[3/5] Acquiring ThoughtSpot Bearer token …")
    auth = ThoughtSpotAuth(settings)
    try:
        token = auth.get_token()
    except RuntimeError as exc:
        print(f"[FAIL] {exc}")
        sys.exit(1)
    print(f"      Token (first 20 chars): {token[:20]}…")

    # ── Step 4: TML round-trip via thoughtspot_tml ────────────────
    print("\n[4/5] TML round-trip (export existing table → parse → dump) …")
    client = TMLClient(settings, auth)

    # Find any registered table in this connection
    registered_table_guid = _find_registered_table(settings, auth)
    if not registered_table_guid:
        print("[FAIL] No registered tables found in the ThoughtSpot connection.")
        print("       Register at least one Snowflake table in the TS connection first.")
        sys.exit(1)

    try:
        tml_strings = client.export_tml([registered_table_guid])
        raw_tml = tml_strings[0]
    except RuntimeError as exc:
        print(f"[FAIL] Export TML: {exc}")
        sys.exit(1)

    try:
        table_obj = Table.loads(raw_tml)
        roundtripped = table_obj.dumps()
    except Exception as exc:
        print(f"[FAIL] TML round-trip failed: {exc}")
        sys.exit(1)

    print(f"      Exported table   : {table_obj.name}")
    print("      TML snippet (first 5 lines):")
    for line in roundtripped.splitlines()[:5]:
        print(f"        {line}")

    # ── Step 5: VALIDATE_ONLY import ─────────────────────────────
    print("\n[5/5] VALIDATE_ONLY TML import …")
    try:
        results = client.import_tml([roundtripped], policy="VALIDATE_ONLY")
    except RuntimeError as exc:
        print(f"[FAIL] VALIDATE_ONLY: {exc}")
        sys.exit(1)

    ok = True
    for item in results:
        status = item.get("response", {}).get("status", {}).get("status_code", "—")
        name = item.get("response", {}).get("header", {}).get("name", "—")
        guid = item.get("response", {}).get("header", {}).get("id_guid", "—")
        err = item.get("response", {}).get("status", {}).get("error_message", "")
        print(f"      name={name} | guid={guid} | status={status}")
        if err:
            print(f"      error: {err}")
        if status not in ("OK",):
            ok = False

    if ok:
        print(f"\n[PASS] Step 1 complete — all systems operational.")
        print(f"       TS token ✓  |  Snowflake ✓  |  TML round-trip ✓  |  Import API ✓")
    else:
        print("\n[FAIL] TML import returned non-OK status.")
        sys.exit(1)


def _find_registered_table(settings: Settings, auth: ThoughtSpotAuth) -> str | None:
    """Return the GUID of the first table registered in the TS connection."""
    headers = {"Authorization": f"Bearer {auth.get_token()}"}
    resp = requests.post(
        f"{settings.ts_host}/api/rest/2.0/connection/search",
        json={"connection_identifier": settings.ts_connection_name, "include_details": True},
        headers=headers,
        timeout=30,
    )
    if not resp.ok:
        return None
    data = resp.json()
    connections = data if isinstance(data, list) else [data]
    for conn in connections:
        tables = conn.get("details", {}).get("tables", []) or []
        if tables:
            return tables[0]["id"]
    return None


if __name__ == "__main__":
    run()
