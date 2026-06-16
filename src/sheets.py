from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .icp_config import ICPConfig
from .models import Account, AccountStatus, ScoredAccount

log = logging.getLogger(__name__)

# D-03 precedence string: consumed verbatim by the Phase 6 legend renderer.
STATUS_LEGEND = "judge_failed > hook_suppressed > low_groundedness > clean"

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
    "contact_2_role",
    "contact_2_rationale",
    "hook_2",
    "contact_3_role",
    "contact_3_rationale",
    "hook_3",
    "eval_groundedness",
    "eval_icp_relevance",
    "eval_personalization",
    "eval_specificity",
    "eval_recency",
    "error",
)

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@dataclass(frozen=True)
class SheetWriteResult:
    spreadsheet_id: str
    url: str
    sheet_title: str


def build_rows(
    scored: list[ScoredAccount],
    *,
    sources_sheet_id: int | None = None,
    sources_lookup: dict[tuple[str, int], int] | None = None,
    config: ICPConfig | None = None,
) -> list[list[str]]:
    labels = axis_display_labels(config) if config is not None else {}
    rows: list[list[str]] = [[labels.get(header, header) for header in HEADERS]]
    for sa in scored:
        sources_row_for_account = None
        first_index = _first_justification_index(sa)
        if sources_lookup is not None and first_index is not None:
            sources_row_for_account = sources_lookup.get((sa.account.domain, first_index))
        rows.append(
            _build_row(
                sa,
                sources_sheet_id=sources_sheet_id,
                sources_row_for_account=sources_row_for_account,
            )
        )
    return rows


def _build_row(
    sa: ScoredAccount,
    *,
    sources_sheet_id: int | None = None,
    sources_row_for_account: int | None = None,
) -> list[str]:
    f = sa.enrichment.firmographics
    bd = sa.score.breakdown if sa.score is not None else None
    contacts = list(sa.contacts) + [None, None, None]
    # Pair each contact with its own hook by identity, not by list position:
    # a failed outreach call leaves sa.hooks shorter than sa.contacts, so a
    # positional zip would shift later personas' hooks up one slot and show a
    # persona an outreach paragraph written for a different persona.
    hook_by_contact = {h.contact: h for h in sa.hooks}
    ev = sa.eval_score
    justifications_by_index = {j.index: j for j in sa.enrichment.justifications}

    score_justification = (
        _format_score_justification(sa.score, justifications_by_index) if sa.score else ""
    )
    if sources_sheet_id is not None and sources_row_for_account is not None:
        score_justification = _hyperlink_formula(
            sources_sheet_id, sources_row_for_account, score_justification
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
        h = hook_by_contact.get(c) if c else None
        row.append(c.role_title if c else "")
        row.append(c.rationale if c else "")
        hook_cell = h.paragraph if h else ""
        if sources_sheet_id is not None and sources_row_for_account is not None:
            hook_cell = _hyperlink_formula(sources_sheet_id, sources_row_for_account, hook_cell)
        row.append(hook_cell)
    row.extend(
        [
            _fmt(ev.groundedness) if ev else "",
            _fmt(ev.icp_relevance) if ev else "",
            _fmt(ev.personalization) if ev else "",
            _fmt(ev.specificity) if ev else "",
            _fmt(ev.recency) if ev else "",
            sa.error or "",
        ]
    )
    return row


def _first_justification_index(sa: ScoredAccount) -> int | None:
    if not sa.enrichment.justifications:
        return None
    return min(j.index for j in sa.enrichment.justifications)


def _format_score_justification(score: Any, by_index: dict[int, Any]) -> str:
    """Compose the score's justification cell with supporting evidence markers.

    If the writer omits supporting_indices entirely (which it shouldn't,
    per the prompt) we still surface the gap to the reader as
    'Supporting: (writer returned no indices)' rather than silently
    rendering an unsupported justification. Makes the writer mistake
    visible instead of indistinguishable from a "no evidence" verdict.
    """
    parts = [score.justification.strip() if score.justification else ""]
    supports = [f"[{i}]" for i in score.supporting_indices if i in by_index]
    if supports:
        parts.append("Supporting: " + " ".join(supports))
    elif by_index:
        parts.append("Supporting: (writer returned no supporting indices)")
    return " ".join(p for p in parts if p)


def _hyperlink_formula(target_sheet_id: int, target_row: int, display_text: str) -> str:
    if not display_text:
        return ""
    escaped = display_text.replace('"', '""')
    return f'=HYPERLINK("#gid={target_sheet_id}&range=A{target_row}", "{escaped}")'


def build_sources_rows(scored: list[ScoredAccount]) -> list[list[str]]:
    rows = [["domain", "index", "summary", "url", "source"]]
    for sa in scored:
        for justification in sorted(sa.enrichment.justifications, key=lambda j: j.index):
            rows.append(
                [
                    sa.account.domain,
                    str(justification.index),
                    justification.summary,
                    str(justification.citation.url),
                    justification.citation.source,
                ]
            )
    return rows


def _sources_row_lookup(scored: list[ScoredAccount]) -> dict[tuple[str, int], int]:
    lookup: dict[tuple[str, int], int] = {}
    next_row = 2
    for sa in scored:
        for justification in sorted(sa.enrichment.justifications, key=lambda j: j.index):
            lookup[(sa.account.domain, justification.index)] = next_row
            next_row += 1
    return lookup


def _fmt(v: float) -> str:
    return f"{v:.1f}"


RUBRIC_TAB_TITLE = "Rubric"
INPUTS_TAB_TITLE = "Inputs"
LEGEND_TAB_TITLE = "Legend"


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
    rows.append(["Judge rubric (LLM-as-judge, claim-decomposition for groundedness)"])
    rows.append(["axis", "description"])
    rows.append(
        [
            "groundedness",
            "Judge breaks the outreach paragraph into atomic factual claims, then "
            "marks each claim as supported by a numbered justification or "
            "'uncited'. Score is (cited / max(total, 3)) * 5. The min-3 floor "
            "penalizes very short hooks.",
        ]
    )
    rows.append(
        [
            "icp_relevance",
            "1-5 categorical: how well the message reflects the buyer description above.",
        ]
    )
    rows.append(
        [
            "personalization",
            "1-5 categorical: how specific the message is to this account.",
        ]
    )
    rows.append([])
    rows.append(
        [
            f"When groundedness drops below {config.eval.groundedness_flag_threshold:.1f}, "
            "the eval_groundedness cell turns red text. Whole-row background comes from "
            "AccountStatus; see the Legend tab for status colors and precedence.",
        ]
    )
    rows.append([])
    rows.append(
        [
            "Justifications are numbered Exa retrievals (about page + last-90-day "
            "news), shown to the writer as [1]..[N]. The writer's hook references "
            "these by index; the judge checks each claim against the same list."
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


def axis_display_labels(config: ICPConfig) -> dict[str, str]:
    labels: dict[str, str] = {}
    for name, axis in config.axes.items():
        title = " ".join("AI" if part == "ai" else part.capitalize() for part in name.split("_"))
        labels[name] = f"{title} ({round(axis.weight * 100)}%)"
    return labels


ACCOUNT_STATUS_COLORS: dict[AccountStatus, dict[str, float]] = {
    AccountStatus.clean: {"red": 1.0, "green": 1.0, "blue": 1.0},
    AccountStatus.low_groundedness: {"red": 1.0, "green": 0.97, "blue": 0.80},
    AccountStatus.hook_suppressed: {"red": 1.0, "green": 0.90, "blue": 0.78},
    AccountStatus.judge_failed: {"red": 0.88, "green": 0.88, "blue": 0.88},
}

FLAG_TEXT_COLOR: dict[str, float] = {"red": 0.8, "green": 0.0, "blue": 0.0}

# D-13 width classes. Pixel values picked inside the documented ranges so
# narrow numeric columns stay scannable and hook paragraphs (the "wide"
# class) read as multi-sentence prose without horizontal scroll.
WIDTH_CLASS_PX: dict[str, int] = {
    "narrow": 110,
    "medium": 180,
    "wide": 400,
    "extra": 250,
}

# D-13 per-column class. Every HEADERS entry MUST appear exactly once so the
# results tab never falls back to the Sheets default width on first open.
# The covers-every-header invariant is asserted in test_sheets_rows.py.
COLUMN_WIDTHS: dict[str, str] = {
    "domain": "narrow",
    "status": "narrow",
    "name": "medium",
    "industry": "medium",
    "headcount": "medium",
    "tech_signals": "medium",
    "icp_total": "narrow",
    "verdict": "narrow",
    "support_volume": "narrow",
    "ai_maturity": "narrow",
    "stage_fit": "narrow",
    "channel_breadth": "narrow",
    "justification": "wide",
    "contact_1_role": "medium",
    "contact_1_rationale": "medium",
    "hook_1": "wide",
    "contact_2_role": "medium",
    "contact_2_rationale": "medium",
    "hook_2": "wide",
    "contact_3_role": "medium",
    "contact_3_rationale": "medium",
    "hook_3": "wide",
    "eval_groundedness": "narrow",
    "eval_icp_relevance": "narrow",
    "eval_personalization": "narrow",
    "eval_specificity": "narrow",
    "eval_recency": "narrow",
    "error": "extra",
}

# D-14 wrap columns: hook paragraphs and the score justification render as
# multi-sentence prose, so they need wrap to grow vertically rather than
# spill horizontally.
WRAP_COLUMN_NAMES: tuple[str, ...] = ("hook_1", "hook_2", "hook_3", "justification")

ACCOUNT_STATUS_MEANINGS: dict[AccountStatus, str] = {
    AccountStatus.clean: "All claims grounded; no eval flags.",
    AccountStatus.low_groundedness: "Hook content shipped but eval groundedness fell below threshold.",
    AccountStatus.hook_suppressed: (
        "No outreach content shipped: the account could not be enriched, scored, "
        "or given personas, or every hook was dropped for failing citation coverage."
    ),
    AccountStatus.judge_failed: (
        "Judge call did not return a parseable score; eval is out-of-band, NOT a content failure."
    ),
}


def _legend_color_label(status: AccountStatus) -> str:
    color = ACCOUNT_STATUS_COLORS[status]
    if color["red"] == color["green"] == color["blue"]:
        return "white" if color["red"] >= 0.99 else "gray"
    if color["green"] >= 0.95:
        return "yellow"
    return "orange"


def build_legend_rows() -> list[list[str]]:
    rows = [["status", "color", "meaning", "precedence"]]
    for status in AccountStatus:
        rows.append(
            [
                status.value,
                _legend_color_label(status),
                ACCOUNT_STATUS_MEANINGS[status],
                STATUS_LEGEND,
            ]
        )
    return rows


def account_status_row_colors(scored: list[ScoredAccount]) -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    for i, sa in enumerate(scored):
        idx = i + 1
        if sa.status != AccountStatus.clean:
            out[idx] = ACCOUNT_STATUS_COLORS[sa.status]
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
        sources_title = f"{results_title}-sources"

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

        self._refresh_named_tab(
            service, spreadsheet_id, LEGEND_TAB_TITLE, build_legend_rows(), existing_tabs
        )
        self._apply_legend_tab_colors(service, spreadsheet_id)

        self._add_tab(service, spreadsheet_id, results_title, existing_tabs)
        self._add_tab(service, spreadsheet_id, sources_title, existing_tabs)
        sources_rows = build_sources_rows(scored)
        self._write_values(service, spreadsheet_id, sources_title, sources_rows)
        sources_sheet_id = self._lookup_sheet_id(service, spreadsheet_id, sources_title)
        sources_lookup = _sources_row_lookup(scored)
        results_rows = build_rows(
            scored,
            sources_sheet_id=sources_sheet_id,
            sources_lookup=sources_lookup,
            config=config,
        )
        self._write_values(service, spreadsheet_id, results_title, results_rows)

        # One sheet_id lookup powers every formatting pass (colors, eval flags,
        # freeze, widths, wrap) so the writer stays gentle on the discovery API.
        results_sheet_id = self._lookup_sheet_id(service, spreadsheet_id, results_title)
        if results_sheet_id is not None:
            self._apply_row_colors(service, spreadsheet_id, results_sheet_id, scored)
            self._apply_eval_flag_text(service, spreadsheet_id, results_sheet_id, scored)
            self._apply_freeze_panes(service, spreadsheet_id, results_sheet_id)
            self._apply_column_widths(service, spreadsheet_id, results_sheet_id)
            self._apply_wrap_strategy(
                service, spreadsheet_id, results_sheet_id, num_data_rows=len(scored)
            )

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
        # USER_ENTERED so =HYPERLINK formulas in hook and score-justification
        # cells (Phase 6) are parsed and rendered as clickable links rather
        # than stored as literal text.
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_title}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": rows},
        ).execute()

    def _apply_row_colors(
        self,
        service: Any,
        spreadsheet_id: str,
        sheet_id: int,
        scored: list[ScoredAccount],
    ) -> None:
        colors = account_status_row_colors(scored)
        if not colors:
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

    def _apply_legend_tab_colors(self, service: Any, spreadsheet_id: str) -> None:
        sheet_id = self._lookup_sheet_id(service, spreadsheet_id, LEGEND_TAB_TITLE)
        if sheet_id is None:
            return
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row_idx,
                        "endRowIndex": row_idx + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {"backgroundColor": ACCOUNT_STATUS_COLORS[status]}
                    },
                    "fields": "userEnteredFormat.backgroundColor",
                }
            }
            for row_idx, status in enumerate(AccountStatus, start=1)
        ]
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()

    def _apply_eval_flag_text(
        self,
        service: Any,
        spreadsheet_id: str,
        sheet_id: int,
        scored: list[ScoredAccount],
    ) -> None:
        flagged = flagged_eval_rows(scored)
        if not flagged:
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

    def _apply_freeze_panes(self, service: Any, spreadsheet_id: str, sheet_id: int) -> None:
        """D-12: pin row 1 (header) and columns A-B (domain, status).

        Vertical scroll keeps weight-baked headers visible; horizontal scroll
        keeps the AccountStatus column pinned so the viewer never loses row
        identity. Two-column freeze is hard-coded because D-12 locks the count.
        """
        request = {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 2},
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": [request]}
        ).execute()

    def _apply_column_widths(self, service: Any, spreadsheet_id: str, sheet_id: int) -> None:
        """D-13: size each column by its width class in a single batchUpdate.

        One request per HEADERS entry keeps the mapping obvious in API
        traffic; the per-class collapsing optimization is intentionally
        deferred since 28 requests sit far under the Sheets per-batchUpdate
        limit.
        """
        requests = [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": col_index,
                        "endIndex": col_index + 1,
                    },
                    "properties": {"pixelSize": WIDTH_CLASS_PX[COLUMN_WIDTHS[name]]},
                    "fields": "pixelSize",
                }
            }
            for col_index, name in enumerate(HEADERS)
        ]
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()

    def _apply_wrap_strategy(
        self,
        service: Any,
        spreadsheet_id: str,
        sheet_id: int,
        num_data_rows: int,
    ) -> None:
        """D-14: WRAP hook + justification columns so prose grows vertically.

        Range is row 1 (first data row) through num_data_rows + 1 (exclusive
        end). An empty data range still issues the request as a no-op so
        future-added rows inherit the format on subsequent runs.
        """
        end_row = num_data_rows + 1
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": end_row,
                        "startColumnIndex": HEADERS.index(name),
                        "endColumnIndex": HEADERS.index(name) + 1,
                    },
                    "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                    "fields": "userEnteredFormat.wrapStrategy",
                }
            }
            for name in WRAP_COLUMN_NAMES
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
