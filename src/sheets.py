from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .icp_config import ICPConfig
from .models import Account, ScoredAccount

log = logging.getLogger(__name__)

HEADERS: tuple[str, ...] = (
    "domain",
    "status",
    "name",
    "industry",
    "headcount",
    "tech_signals",
    "icp_total",
    "verdict",
    "support_volume",
    "ai_maturity",
    "stage_fit",
    "channel_breadth",
    "justification",
    "contact_1_role",
    "contact_1_rationale",
    "hook_1",
    "hook_1_citations",
    "contact_2_role",
    "contact_2_rationale",
    "hook_2",
    "hook_2_citations",
    "contact_3_role",
    "contact_3_rationale",
    "hook_3",
    "hook_3_citations",
    "eval_groundedness",
    "eval_icp_relevance",
    "eval_personalization",
    "error",
)

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@dataclass(frozen=True)
class SheetWriteResult:
    spreadsheet_id: str
    url: str
    sheet_title: str


def build_rows(scored: list[ScoredAccount]) -> list[list[str]]:
    rows: list[list[str]] = [list(HEADERS)]
    for sa in scored:
        rows.append(_build_row(sa))
    return rows


def _build_row(sa: ScoredAccount) -> list[str]:
    f = sa.enrichment.firmographics
    bd = sa.score.breakdown if sa.score is not None else None
    contacts = list(sa.contacts) + [None, None, None]
    hooks = list(sa.hooks) + [None, None, None]
    ev = sa.eval_score
    justifications_by_index = {j.index: j for j in sa.enrichment.justifications}

    score_justification = (
        _format_score_justification(sa.score, justifications_by_index) if sa.score else ""
    )

    row: list[str] = [
        sa.account.domain,
        sa.status,
        f.name if f else "",
        (f.industry or "") if f else "",
        (f.headcount_range or "") if f else "",
        ", ".join(f.tech_signals) if f else "",
        _fmt(sa.score.total) if sa.score else "",
        sa.score.verdict if sa.score else "",
        _fmt(bd.support_volume) if bd else "",
        _fmt(bd.ai_maturity) if bd else "",
        _fmt(bd.stage_fit) if bd else "",
        _fmt(bd.channel_breadth) if bd else "",
        score_justification,
    ]
    for i in range(3):
        c = contacts[i]
        h = hooks[i]
        row.append(c.role_title if c else "")
        row.append(c.rationale if c else "")
        row.append(h.paragraph if h else "")
        row.append(_format_hook_citations(h, justifications_by_index) if h else "")
    row.extend(
        [
            _fmt(ev.groundedness) if ev else "",
            _fmt(ev.icp_relevance) if ev else "",
            _fmt(ev.personalization) if ev else "",
            sa.error or "",
        ]
    )
    return row


def _format_score_justification(score: Any, by_index: dict[int, Any]) -> str:
    """Compose the score's justification cell with supporting evidence inline."""
    parts = [score.justification.strip() if score.justification else ""]
    supports = [
        f"[{i}] {by_index[i].summary} ({by_index[i].citation.url})"
        for i in score.supporting_indices
        if i in by_index
    ]
    if supports:
        parts.append("Supporting: " + "; ".join(supports))
    return " ".join(p for p in parts if p)


def _format_hook_citations(hook: Any, by_index: dict[int, Any]) -> str:
    """Render the hook's cited justifications as '[1] summary (url); [3] summary (url)'."""
    if not hook.cited_indices:
        return ""
    return "; ".join(
        f"[{i}] {by_index[i].summary} ({by_index[i].citation.url})"
        for i in hook.cited_indices
        if i in by_index
    )


def _fmt(v: float) -> str:
    return f"{v:.1f}"


RUBRIC_TAB_TITLE = "Rubric"
INPUTS_TAB_TITLE = "Inputs"


def build_rubric_rows(config: ICPConfig) -> list[list[str]]:
    """Render configs/icp.yaml into a human-readable Rubric tab.

    Anyone scrolling the sheet should be able to understand how a verdict
    was reached without reading code. Edit configs/icp.yaml; this rebuilds.
    """
    rows: list[list[str]] = []
    rows.append(["Account-research POC: ICP rubric and grading instructions"])
    rows.append([])
    rows.append(["Buyer description"])
    rows.append([config.buyer_description.strip()])
    rows.append([])
    rows.append(["Axes (each scored 1-5 by the writer LLM, weighted into a 1-5 total)"])
    rows.append(["axis", "weight", "description", "1", "2", "3", "4", "5"])
    for name, axis in config.axes.items():
        rows.append(
            [
                name,
                f"{axis.weight:.2f}",
                axis.description.strip(),
                axis.anchors.get("1", ""),
                axis.anchors.get("2", ""),
                axis.anchors.get("3", ""),
                axis.anchors.get("4", ""),
                axis.anchors.get("5", ""),
            ]
        )
    rows.append([])
    rows.append(["Verdict thresholds (computed from the weighted total)"])
    rows.append(["verdict", "min_total", "description"])
    for verdict in sorted(config.verdicts.values(), key=lambda v: -v.min_total):
        rows.append([verdict.label, f"{verdict.min_total:.1f}", verdict.description.strip()])
    rows.append([])
    rows.append(["Judge rubric (LLM-as-judge, 1-5 scale per NeMo guidance)"])
    rows.append(["axis", "description"])
    rows.append(
        [
            "groundedness",
            "Every factual claim about the account is supported by one of the cited URLs.",
        ]
    )
    rows.append(
        [
            "icp_relevance",
            "The outreach message reflects the buyer description above.",
        ]
    )
    rows.append(
        [
            "personalization",
            "The message references something specific to this account, not generic boilerplate.",
        ]
    )
    rows.append([])
    rows.append(
        [
            f"Groundedness below {config.eval.groundedness_flag_threshold:.1f} flags the "
            "Results row red.",
        ]
    )
    rows.append([])
    rows.append(
        [
            "Edit configs/icp.yaml to retarget. Both the writer prompt and the judge "
            "prompt read from this file."
        ]
    )
    return rows


def build_inputs_rows(
    accounts: list[Account],
    *,
    loaded_at: datetime | None = None,
    source_path: str | None = None,
) -> list[list[str]]:
    """Render the input list as a tab so the demo viewer sees what we're researching."""
    when = (loaded_at or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M:%S UTC")
    rows: list[list[str]] = []
    rows.append(["Inputs: domains queued for this run"])
    rows.append([])
    if source_path:
        rows.append(["source", source_path])
    rows.append(["loaded_at", when])
    rows.append(["count", str(len(accounts))])
    rows.append([])
    rows.append(["domain"])
    for a in accounts:
        rows.append([a.domain])
    return rows


VERDICT_COLORS: dict[str, dict[str, float]] = {
    "strong": {"red": 0.82, "green": 0.95, "blue": 0.82},
    "borderline": {"red": 1.0, "green": 0.97, "blue": 0.80},
}

FLAG_TEXT_COLOR: dict[str, float] = {"red": 0.8, "green": 0.0, "blue": 0.0}


def verdict_row_colors(scored: list[ScoredAccount]) -> dict[int, dict[str, float]]:
    """Map of row index (1-based, header is row 0) to verdict background color.

    Strong verdict gets green, borderline gets yellow, weak gets no color.
    Eval-flagged rows are signaled separately by red text on the
    eval_groundedness cell (see `flagged_eval_rows`), so the row's verdict
    color is never overridden.
    """
    out: dict[int, dict[str, float]] = {}
    for i, sa in enumerate(scored):
        idx = i + 1
        if sa.score and sa.score.verdict in VERDICT_COLORS:
            out[idx] = VERDICT_COLORS[sa.score.verdict]
    return out


def flagged_eval_rows(scored: list[ScoredAccount]) -> list[int]:
    """Row indices (1-based, header is row 0) where groundedness < flag threshold."""
    return [i + 1 for i, sa in enumerate(scored) if sa.eval_score and sa.eval_score.is_flagged]


class SheetsWriter:
    def __init__(
        self,
        credentials_path: str | Path,
        spreadsheet_id: str | None = None,
        service: Any = None,
    ) -> None:
        self._credentials_path = Path(credentials_path)
        self._spreadsheet_id = spreadsheet_id or None
        self._service = service

    def _build_service(self) -> Any:
        if self._service is not None:
            return self._service
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        if not self._credentials_path.exists():
            raise FileNotFoundError(
                f"service account credentials not found at {self._credentials_path}"
            )
        creds = Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
            str(self._credentials_path), scopes=SHEETS_SCOPES
        )
        return build("sheets", "v4", credentials=creds, cache_discovery=False)

    def write(
        self,
        scored: list[ScoredAccount],
        *,
        accounts: list[Account] | None = None,
        config: ICPConfig | None = None,
    ) -> SheetWriteResult:
        service = self._build_service()
        run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        results_title = f"run-{run_id}"

        if self._spreadsheet_id:
            spreadsheet_id = self._spreadsheet_id
        else:
            spreadsheet_id = self._create_empty_spreadsheet(service, results_title)

        existing_tabs = self._list_tabs(service, spreadsheet_id)

        if config is not None:
            self._refresh_named_tab(
                service, spreadsheet_id, RUBRIC_TAB_TITLE, build_rubric_rows(config), existing_tabs
            )
        if accounts is not None:
            self._refresh_named_tab(
                service,
                spreadsheet_id,
                INPUTS_TAB_TITLE,
                build_inputs_rows(accounts, source_path="inputs/accounts.csv"),
                existing_tabs,
            )

        self._add_tab(service, spreadsheet_id, results_title, existing_tabs)
        results_rows = build_rows(scored)
        self._write_values(service, spreadsheet_id, results_title, results_rows)
        self._apply_row_colors(service, spreadsheet_id, results_title, scored)
        self._apply_eval_flag_text(service, spreadsheet_id, results_title, scored)

        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        log.info("wrote %d rows to %s tab %s", len(results_rows) - 1, url, results_title)
        return SheetWriteResult(spreadsheet_id=spreadsheet_id, url=url, sheet_title=results_title)

    def _create_empty_spreadsheet(self, service: Any, results_title: str) -> str:
        body = {
            "properties": {"title": f"poc_scraper {results_title}"},
            "sheets": [{"properties": {"title": results_title}}],
        }
        created = service.spreadsheets().create(body=body, fields="spreadsheetId").execute()
        return str(created["spreadsheetId"])

    def _list_tabs(self, service: Any, spreadsheet_id: str) -> set[str]:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        return {
            s.get("properties", {}).get("title", "")
            for s in meta.get("sheets", [])
            if s.get("properties", {}).get("title")
        }

    def _add_tab(self, service: Any, spreadsheet_id: str, title: str, existing: set[str]) -> None:
        if title in existing:
            return
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        ).execute()
        existing.add(title)

    def _refresh_named_tab(
        self,
        service: Any,
        spreadsheet_id: str,
        title: str,
        rows: list[list[str]],
        existing: set[str],
    ) -> None:
        self._add_tab(service, spreadsheet_id, title, existing)
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"{title}!A1:ZZ",
        ).execute()
        self._write_values(service, spreadsheet_id, title, rows)

    def _write_values(
        self, service: Any, spreadsheet_id: str, sheet_title: str, rows: list[list[str]]
    ) -> None:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_title}!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

    def _apply_row_colors(
        self,
        service: Any,
        spreadsheet_id: str,
        sheet_title: str,
        scored: list[ScoredAccount],
    ) -> None:
        colors = verdict_row_colors(scored)
        if not colors:
            return
        sheet_id = self._lookup_sheet_id(service, spreadsheet_id, sheet_title)
        if sheet_id is None:
            return
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": idx,
                        "endRowIndex": idx + 1,
                    },
                    "cell": {"userEnteredFormat": {"backgroundColor": color}},
                    "fields": "userEnteredFormat.backgroundColor",
                }
            }
            for idx, color in sorted(colors.items())
        ]
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()

    def _apply_eval_flag_text(
        self,
        service: Any,
        spreadsheet_id: str,
        sheet_title: str,
        scored: list[ScoredAccount],
    ) -> None:
        flagged = flagged_eval_rows(scored)
        if not flagged:
            return
        sheet_id = self._lookup_sheet_id(service, spreadsheet_id, sheet_title)
        if sheet_id is None:
            return
        col = HEADERS.index("eval_groundedness")
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": idx,
                        "endRowIndex": idx + 1,
                        "startColumnIndex": col,
                        "endColumnIndex": col + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "bold": True,
                                "foregroundColor": FLAG_TEXT_COLOR,
                            }
                        }
                    },
                    "fields": "userEnteredFormat.textFormat.bold,"
                    "userEnteredFormat.textFormat.foregroundColor",
                }
            }
            for idx in flagged
        ]
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()

    def _lookup_sheet_id(self, service: Any, spreadsheet_id: str, sheet_title: str) -> int | None:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        for s in meta.get("sheets", []):
            props = s.get("properties", {})
            if props.get("title") == sheet_title:
                sid = props.get("sheetId")
                return int(sid) if sid is not None else None
        return None
