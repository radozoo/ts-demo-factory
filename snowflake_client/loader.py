"""Snowflake DDL creation and bulk data loading from TableDef."""
from __future__ import annotations

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key, Encoding, PrivateFormat, NoEncryption,
)
import snowflake.connector
from config.settings import Settings
from schema.retail.tables import TableDef


def _load_private_key(path: str):
    with open(path, "rb") as f:
        return load_pem_private_key(f.read(), password=None, backend=default_backend())


def _get_connection(settings: Settings):
    private_key = _load_private_key(settings.sf_private_key_path)
    private_key_der = private_key.private_bytes(
        encoding=Encoding.DER,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )
    return snowflake.connector.connect(
        account=settings.sf_account,
        user=settings.sf_user,
        private_key=private_key_der,
        database=settings.sf_database,
        schema=settings.sf_schema,
        warehouse=settings.sf_warehouse,
        role=settings.sf_role,
    )


def create_table(settings: Settings, table_def: TableDef, drop_if_exists: bool = False) -> None:
    """Create Snowflake table from TableDef. Optionally drops first."""
    col_ddl = ",\n    ".join(
        f"{col.name} {col.db_type}" for col in table_def.columns
    )
    with _get_connection(settings) as conn:
        with conn.cursor() as cur:
            if drop_if_exists:
                cur.execute(f"DROP TABLE IF EXISTS {table_def.name}")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_def.name} (
                    {col_ddl}
                )
            """)


def bulk_insert(settings: Settings, table_def: TableDef, rows: list[dict]) -> None:
    """Insert rows (list of dicts) into Snowflake table via executemany."""
    if not rows:
        return
    col_names = [col.name for col in table_def.columns]
    placeholders = ", ".join(["%s"] * len(col_names))
    sql = f"INSERT INTO {table_def.name} ({', '.join(col_names)}) VALUES ({placeholders})"
    data = [tuple(row[c] for c in col_names) for row in rows]

    with _get_connection(settings) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, data)
        conn.commit()
