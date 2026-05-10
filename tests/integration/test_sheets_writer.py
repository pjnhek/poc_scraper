from __future__ import annotations

from typing import Any

from src.models import (
    Account,
    Citation,
    Contact,
    Enrichment,
    EvalScore,
    Firmographics,
    ICPScore,
    NewsItem,
    OutreachHook,
    RubricBreakdown,
    ScoredAccount,
)
from src.sheets import SheetsWriter


class FakeRequest:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self._response = response or {}

    def execute(self) -> dict[str, Any]:
        return self._response


class FakeValues:
    def __init__(self) -> None:
        self.update_calls: list[dict[str, Any]] = []
        self.clear_calls: list[dict[str, Any]] = []

    def update(self, **kwargs: Any) -> FakeRequest:
        self.update_calls.append(kwargs)
        return FakeRequest({"updatedRows": len(kwargs.get("body", {}).get("values", []))})

    def clear(self, **kwargs: Any) -> FakeRequest:
        self.clear_calls.append(kwargs)
        return FakeRequest({})


class FakeSpreadsheets:
    def __init__(self) -> None:
        self._values = FakeValues()
        self.create_calls: list[dict[str, Any]] = []
        self.batch_calls: list[dict[str, Any]] = []
        self.get_calls: list[str] = []

    def values(self) -> FakeValues:
        return self._values

    def create(self, **kwargs: Any) -> FakeRequest:
        self.create_calls.append(kwargs)
        return FakeRequest({"spreadsheetId": "fake-sid"})

    def batchUpdate(self, **kwargs: Any) -> FakeRequest:
        self.batch_calls.append(kwargs)
        return FakeRequest({"replies": []})

    def get(self, spreadsheetId: str) -> FakeRequest:
        self.get_calls.append(spreadsheetId)
        return FakeRequest({"sheets": [self._sheet_meta(t) for t in self._all_tab_titles()]})

    def _all_tab_titles(self) -> list[str]:
        titles: list[str] = []
        for call in self.create_calls:
            for s in call.get("body", {}).get("sheets", []):
                t = s.get("properties", {}).get("title")
                if t:
                    titles.append(t)
        for call in self.batch_calls:
            for req in call.get("body", {}).get("requests", []):
                add = req.get("addSheet")
                if add:
                    t = add["properties"]["title"]
                    if t and t not in titles:
                        titles.append(t)
        return titles

    @staticmethod
    def _sheet_meta(title: str) -> dict[str, Any]:
        return {"properties": {"title": title, "sheetId": abs(hash(title)) % 100000}}


class FakeService:
    def __init__(self) -> None:
        self._sheets = FakeSpreadsheets()

    def spreadsheets(self) -> FakeSpreadsheets:
        return self._sheets


def _scored(domain: str, flag: bool) -> ScoredAccount:
    from src.models import Justification

    acc = Account(domain=domain)
    cit = Citation.make(url="https://example.com/x", source="exa", snippet="snippet")
    enr = Enrichment(
        account=acc,
        firmographics=Firmographics(name=domain, industry="fintech"),
        news=(NewsItem(headline="h", summary="s", citation=cit),),
        justifications=(Justification(index=1, summary="h: s", citation=cit),),
    )
    bd = RubricBreakdown(
        support_volume=4,
        ai_maturity=3,
        stage_fit=4,
        channel_breadth=3,
        support_volume_reason="r",
        ai_maturity_reason="r",
        stage_fit_reason="r",
        channel_breadth_reason="r",
    )
    score = ICPScore(total=3.7, breakdown=bd, justification="ok", verdict="borderline")
    c1 = Contact(role_title="r1", rationale="r")
    h1 = OutreachHook(contact=c1, paragraph="p [1]", cited_indices=(1,))
    ev = EvalScore(groundedness=2.0 if flag else 4.0, icp_relevance=4, personalization=4)
    return ScoredAccount(
        account=acc,
        status="scored",
        enrichment=enr,
        score=score,
        contacts=(c1, c1, c1),
        hooks=(h1, h1, h1),
        eval_score=ev,
    )


def test_creates_new_spreadsheet_when_no_id() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    result = writer.write([_scored("chime.com", flag=False)])

    assert result.spreadsheet_id == "fake-sid"
    assert result.url.endswith("fake-sid")
    sheets = fake.spreadsheets()
    assert len(sheets.create_calls) == 1
    body = sheets.create_calls[0]["body"]
    assert body["properties"]["title"].startswith("poc_scraper run-")
    update = sheets._values.update_calls[0]
    assert update["spreadsheetId"] == "fake-sid"
    rows = update["body"]["values"]
    assert rows[0][0] == "domain"
    assert rows[1][0] == "chime.com"


def test_appends_tab_when_spreadsheet_id_provided() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", spreadsheet_id="existing-sid", service=fake)
    result = writer.write([_scored("chime.com", flag=False)])
    assert result.spreadsheet_id == "existing-sid"
    sheets = fake.spreadsheets()
    assert sheets.create_calls == []
    add_calls = [
        c for c in sheets.batch_calls if any("addSheet" in r for r in c["body"]["requests"])
    ]
    assert len(add_calls) == 1


def test_flagged_row_keeps_verdict_color_with_red_text_on_eval_cell() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    writer.write([_scored("good.com", flag=False), _scored("bad.com", flag=True)])
    sheets = fake.spreadsheets()
    repeat_calls = [
        r for c in sheets.batch_calls for r in c["body"]["requests"] if "repeatCell" in r
    ]

    # Both rows get a verdict-color background (borderline yellow).
    bg_calls = [
        r for r in repeat_calls if r["repeatCell"]["fields"] == "userEnteredFormat.backgroundColor"
    ]
    assert len(bg_calls) == 2

    # Flagged row gets a red foreground on the eval_groundedness cell only.
    text_calls = [r for r in repeat_calls if "textFormat" in r["repeatCell"]["fields"]]
    assert len(text_calls) == 1
    flagged = text_calls[0]
    assert flagged["repeatCell"]["range"]["startRowIndex"] == 2
    fg = flagged["repeatCell"]["cell"]["userEnteredFormat"]["textFormat"]["foregroundColor"]
    assert fg["red"] >= 0.6
    assert fg["green"] < 0.5


def test_writes_rubric_and_inputs_tabs_when_provided() -> None:
    from src.icp_config import get_config
    from src.models import Account

    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    writer.write(
        [_scored("good.com", flag=False)],
        accounts=[Account(domain="good.com")],
        config=get_config(),
    )
    sheets = fake.spreadsheets()
    written_titles = {call["range"].split("!")[0] for call in sheets._values.update_calls}
    assert "Rubric" in written_titles
    assert "Inputs" in written_titles
    assert any(t.startswith("run-") for t in written_titles)


def test_omits_rubric_and_inputs_when_kwargs_missing() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    writer.write([_scored("good.com", flag=False)])
    sheets = fake.spreadsheets()
    written_titles = {call["range"].split("!")[0] for call in sheets._values.update_calls}
    assert "Rubric" not in written_titles
    assert "Inputs" not in written_titles


def test_rubric_tab_is_cleared_before_rewriting() -> None:
    from src.icp_config import get_config
    from src.models import Account

    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", spreadsheet_id="existing-sid", service=fake)
    writer.write(
        [_scored("good.com", flag=False)],
        accounts=[Account(domain="good.com")],
        config=get_config(),
    )
    sheets = fake.spreadsheets()
    cleared_titles = {call["range"].split("!")[0] for call in sheets._values.clear_calls}
    assert "Rubric" in cleared_titles
    assert "Inputs" in cleared_titles


def test_unscoreable_row_has_no_color() -> None:
    from src.models import Account, Enrichment, ScoredAccount

    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    sa = ScoredAccount.unscoreable(
        Account(domain="dead.com"), Enrichment(account=Account(domain="dead.com")), "no data"
    )
    writer.write([sa])
    sheets = fake.spreadsheets()
    repeat_calls = [
        r for c in sheets.batch_calls for r in c["body"]["requests"] if "repeatCell" in r
    ]
    assert repeat_calls == []
