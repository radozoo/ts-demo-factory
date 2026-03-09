"""ThoughtSpot REST API v2 TML import/export helpers."""
from __future__ import annotations

import requests
from typing import Literal

from ts_client.auth import ThoughtSpotAuth
from config.settings import Settings


ImportPolicy = Literal["VALIDATE_ONLY", "PARTIAL", "ALL_OR_NONE"]


class TMLClient:
    """Wraps /api/rest/2.0/metadata/tml/import and /export."""

    def __init__(self, settings: Settings, auth: ThoughtSpotAuth):
        self._settings = settings
        self._auth = auth

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def import_tml(
        self,
        tml_strings: list[str],
        policy: ImportPolicy = "VALIDATE_ONLY",
        create_new: bool = False,
    ) -> list[dict]:
        """
        Import one or more TML strings.

        Returns a list of response objects, one per TML string:
            {"guid": str | None, "name": str, "type": str, "status": {...}}
        """
        payload = {
            "metadata_tmls": tml_strings,
            "import_policy": policy,
            "create_new_on_import": create_new,
        }
        data = self._post("/api/rest/2.0/metadata/tml/import", payload)
        return data  # list of response dicts

    def delete_by_name(self, names: list[str], metadata_type: str) -> None:
        """
        Delete all TS objects matching *names* and *metadata_type*.
        Silently skips if none found.
        """
        data = self._post("/api/rest/2.0/metadata/search", {
            "metadata": [{"type": metadata_type}],
            "record_size": 200,
        })
        guids = [
            item["metadata_header"]["id"]
            for item in data
            if item.get("metadata_header", {}).get("name") in names
        ]
        if guids:
            url = f"{self._settings.ts_host}/api/rest/2.0/metadata/delete"
            headers = {"Authorization": f"Bearer {self._auth.get_token()}"}
            requests.post(url, json={"metadata": [{"identifier": g} for g in guids]}, headers=headers, timeout=60)

    def export_tml(self, guids: list[str], export_associated: bool = False) -> list[str]:
        """
        Export TML strings for the given GUIDs.

        Returns a list of raw TML YAML strings.
        """
        payload = {
            "metadata": [{"identifier": g} for g in guids],
            "export_associated_objects": "NONE" if not export_associated else "ALL",
            "export_fqn": True,
        }
        data = self._post("/api/rest/2.0/metadata/tml/export", payload)
        return [item["edoc"] for item in data]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: dict) -> list | dict:
        url = f"{self._settings.ts_host}{path}"
        headers = {"Authorization": f"Bearer {self._auth.get_token()}"}
        resp = requests.post(url, json=payload, headers=headers, timeout=60)

        if resp.status_code == 401:
            # Re-auth once and retry
            self._auth.invalidate()
            headers["Authorization"] = f"Bearer {self._auth.get_token()}"
            resp = requests.post(url, json=payload, headers=headers, timeout=60)

        if not resp.ok:
            raise RuntimeError(
                f"TML API error [{resp.status_code}] {path}: {resp.text[:600]}"
            )
        return resp.json()
