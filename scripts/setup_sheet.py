"""Create a fresh Google Sheet, share it with the operator, and persist its ID to .env.

Usage: `make setup-sheet` (one-shot). After this, `make run` appends a new tab
to the same workbook each run, so all results live in one place.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from src.config import get_settings

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
DEFAULT_TITLE = "poc_scraper runs"
DEFAULT_OPERATOR_EMAIL = "nhekvirakyuth@gmail.com"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _load_service_account_email(credentials_path: Path) -> str:
    data = json.loads(credentials_path.read_text(encoding="utf-8"))
    email = data.get("client_email")
    if not isinstance(email, str) or not email:
        raise RuntimeError(f"client_email missing from {credentials_path}")
    return email


def _create_sheet(creds: Credentials, title: str) -> str:
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    created = (
        sheets.spreadsheets()
        .create(body={"properties": {"title": title}}, fields="spreadsheetId")
        .execute()
    )
    return str(created["spreadsheetId"])


def _share_with_operator(creds: Credentials, spreadsheet_id: str, email: str) -> None:
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    drive.permissions().create(
        fileId=spreadsheet_id,
        body={"type": "user", "role": "writer", "emailAddress": email},
        sendNotificationEmail=False,
        fields="id",
    ).execute()


def _write_sheet_id_to_env(env_path: Path, spreadsheet_id: str) -> None:
    if not env_path.exists():
        env_path.write_text(f"GOOGLE_SHEET_ID={spreadsheet_id}\n", encoding="utf-8")
        return

    text = env_path.read_text(encoding="utf-8")
    if re.search(r"^GOOGLE_SHEET_ID=.*$", text, flags=re.MULTILINE):
        text = re.sub(
            r"^GOOGLE_SHEET_ID=.*$",
            f"GOOGLE_SHEET_ID={spreadsheet_id}",
            text,
            flags=re.MULTILINE,
        )
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += f"GOOGLE_SHEET_ID={spreadsheet_id}\n"
    env_path.write_text(text, encoding="utf-8")


def main(operator_email: str = DEFAULT_OPERATOR_EMAIL, title: str = DEFAULT_TITLE) -> int:
    settings = get_settings()
    creds_path = Path(settings.google_application_credentials)
    if not creds_path.exists():
        log.error("credentials file not found at %s", creds_path)
        return 1

    sa_email = _load_service_account_email(creds_path)
    log.info("service account: %s", sa_email)

    creds = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)

    spreadsheet_id = _create_sheet(creds, title)
    log.info("created spreadsheet %s", spreadsheet_id)

    _share_with_operator(creds, spreadsheet_id, operator_email)
    log.info("shared with %s", operator_email)

    _write_sheet_id_to_env(ENV_PATH, spreadsheet_id)
    log.info("wrote GOOGLE_SHEET_ID=%s to %s", spreadsheet_id, ENV_PATH)

    print()
    print(f"Sheet ready: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
    print(f"Shared as Editor with: {operator_email}")
    print(f"GOOGLE_SHEET_ID written to {ENV_PATH}")
    print()
    print("You can now run `make run` and each run will append a new tab.")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = sys.argv[1:]
    op = args[0] if args else DEFAULT_OPERATOR_EMAIL
    raise SystemExit(main(operator_email=op))
