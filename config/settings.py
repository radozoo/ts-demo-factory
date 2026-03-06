"""Central settings loaded from .env via python-dotenv."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    ts_host: str
    ts_username: str
    ts_password: str
    ts_org_id: int
    ts_connection_name: str

    sf_account: str
    sf_user: str
    sf_password: str
    sf_database: str
    sf_schema: str
    sf_warehouse: str
    sf_role: str

    @classmethod
    def from_env(cls) -> "Settings":
        missing = []
        required = [
            "TS_HOST", "TS_USERNAME", "TS_PASSWORD",
            "TS_CONNECTION_NAME",
            "SF_ACCOUNT", "SF_USER", "SF_PASSWORD",
            "SF_DATABASE", "SF_SCHEMA", "SF_WAREHOUSE", "SF_ROLE",
        ]
        for key in required:
            if not os.getenv(key):
                missing.append(key)
        if missing:
            raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")

        return cls(
            ts_host=os.environ["TS_HOST"].rstrip("/"),
            ts_username=os.environ["TS_USERNAME"],
            ts_password=os.environ["TS_PASSWORD"],
            ts_org_id=int(os.getenv("TS_ORG_ID", "0")),
            ts_connection_name=os.environ["TS_CONNECTION_NAME"],
            sf_account=os.environ["SF_ACCOUNT"],
            sf_user=os.environ["SF_USER"],
            sf_password=os.environ["SF_PASSWORD"],
            sf_database=os.environ["SF_DATABASE"],
            sf_schema=os.environ["SF_SCHEMA"],
            sf_warehouse=os.environ["SF_WAREHOUSE"],
            sf_role=os.environ["SF_ROLE"],
        )
