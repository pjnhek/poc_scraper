from __future__ import annotations

from typing import Any

from src.models import (
    Account,
    AccountStatus,
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
from src.sheets import (
    ACCOUNT_STATUS_COLORS,
    LEGEND_TAB_TITLE,
    STATUS_LEGEND,
    SheetsWriter,
    _sources_row_lookup,
    build_legend_rows,
    build_sources_rows,
)


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


def _sheet_id(title: str) -> int:
    return int(FakeSpreadsheets._sheet_meta(title)["properties"]["sheetId"])


def _repeat_cell_requests(fake: FakeService) -> list[dict[str, Any]]:
    return [
        request
        for call in fake.spreadsheets().batch_calls
        for request in call["body"]["requests"]
        if "repeatCell" in request
    ]


def _background_requests(fake: FakeService, sheet_id: int) -> list[dict[str, Any]]:
    return [
        request
        for request in _repeat_cell_requests(fake)
        if request["repeatCell"]["fields"] == "userEnteredFormat.backgroundColor"
        and request["repeatCell"]["range"]["sheetId"] == sheet_id
    ]


def _color_tuple(color: dict[str, float]) -> tuple[float, float, float]:
    return color["red"], color["green"], color["blue"]


def _update_for_title(fake: FakeService, title: str) -> dict[str, Any]:
    return next(
        call
        for call in fake.spreadsheets()._values.update_calls
        if call["range"].startswith(f"{title}!")
    )


def _scored(
    domain: str,
    flag: bool,
    *,
    status: AccountStatus = AccountStatus.clean,
) -> ScoredAccount:
    from src.models import Justification

    acc = Account(domain=domain)
    cit = Citation.make(url="https://example.com/x", source="exa", snippet="snippet")
    enr = Enrichment(
        account=acc,
        firmographics=Firmographics(name=domain, industry="software"),
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
    ev = EvalScore(
        groundedness=2.0 if flag else 4.0,
        icp_relevance=4,
        personalization=4,
        specificity=3,
        recency=3,
    )
    return ScoredAccount(
        account=acc,
        status=status,
        enrichment=enr,
        score=score,
        contacts=(c1, c1, c1),
        hooks=(h1, h1, h1),
        eval_score=ev,
    )


def test_creates_new_spreadsheet_when_no_id() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    result = writer.write([_scored("examplefintech.com", flag=False)])

    assert result.spreadsheet_id == "fake-sid"
    assert result.url.endswith("fake-sid")
    sheets = fake.spreadsheets()
    assert len(sheets.create_calls) == 1
    body = sheets.create_calls[0]["body"]
    assert body["properties"]["title"].startswith("poc_scraper run-")
    update = next(
        call for call in sheets._values.update_calls if call["range"].startswith(result.sheet_title)
    )
    assert update["spreadsheetId"] == "fake-sid"
    rows = update["body"]["values"]
    assert rows[0][0] == "domain"
    assert rows[1][0] == "examplefintech.com"


def test_appends_tab_when_spreadsheet_id_provided() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", spreadsheet_id="existing-sid", service=fake)
    result = writer.write([_scored("examplefintech.com", flag=False)])
    assert result.spreadsheet_id == "existing-sid"
    sheets = fake.spreadsheets()
    assert sheets.create_calls == []
    add_calls = [
        c for c in sheets.batch_calls if any("addSheet" in r for r in c["body"]["requests"])
    ]
    added_titles = {
        request["addSheet"]["properties"]["title"]
        for call in add_calls
        for request in call["body"]["requests"]
        if "addSheet" in request
    }
    assert added_titles == {LEGEND_TAB_TITLE, result.sheet_title, f"{result.sheet_title}-sources"}


def test_account_status_drives_row_tint_red_text_persists_on_eval_cell() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    result = writer.write(
        [
            _scored("good.com", flag=False, status=AccountStatus.clean),
            _scored("bad.com", flag=True, status=AccountStatus.low_groundedness),
        ]
    )
    repeat_calls = _repeat_cell_requests(fake)

    bg_calls = _background_requests(fake, _sheet_id(result.sheet_title))
    assert len(bg_calls) == 1
    bg = bg_calls[0]["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"]
    assert bg == ACCOUNT_STATUS_COLORS[AccountStatus.low_groundedness]

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
    assert LEGEND_TAB_TITLE in written_titles
    assert any(t.startswith("run-") for t in written_titles)


def test_omits_rubric_and_inputs_when_kwargs_missing() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    writer.write([_scored("good.com", flag=False)])
    sheets = fake.spreadsheets()
    written_titles = {call["range"].split("!")[0] for call in sheets._values.update_calls}
    assert "Rubric" not in written_titles
    assert "Inputs" not in written_titles
    assert LEGEND_TAB_TITLE in written_titles


def test_legend_tab_is_written_on_every_run() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    writer.write([_scored("good.com", flag=False)])
    sheets = fake.spreadsheets()
    updated_ranges = [call["range"] for call in sheets._values.update_calls]
    cleared_ranges = [call["range"] for call in sheets._values.clear_calls]
    assert any(range_name.startswith(f"{LEGEND_TAB_TITLE}!") for range_name in updated_ranges)
    assert any(range_name.startswith(f"{LEGEND_TAB_TITLE}!") for range_name in cleared_ranges)


def test_legend_tab_rows_match_account_status_palette() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    writer.write([_scored("good.com", flag=False)])
    sheets = fake.spreadsheets()
    legend_update = next(
        call
        for call in sheets._values.update_calls
        if call["range"].startswith(f"{LEGEND_TAB_TITLE}!")
    )
    rows = legend_update["body"]["values"]
    rendered = "\n".join(cell for row in rows for cell in row)
    assert rows == build_legend_rows()
    for status in AccountStatus:
        assert status.value in rendered
    assert STATUS_LEGEND in rendered


def test_legend_tab_rows_get_palette_tinting() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    writer.write([_scored("good.com", flag=False)])
    bg_calls = _background_requests(fake, _sheet_id(LEGEND_TAB_TITLE))
    assert len(bg_calls) == 4
    actual = {
        _color_tuple(call["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"])
        for call in bg_calls
    }
    expected = {_color_tuple(ACCOUNT_STATUS_COLORS[status]) for status in AccountStatus}
    assert actual == expected


def test_sources_tab_created_per_run() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    result = writer.write([_scored("good.com", flag=False)])

    sources_title = f"{result.sheet_title}-sources"
    written_titles = {
        call["range"].split("!")[0] for call in fake.spreadsheets()._values.update_calls
    }

    assert sources_title in written_titles


def test_sources_tab_rows_match_justifications() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    sa = _scored("good.com", flag=False)
    result = writer.write([sa])

    sources_update = _update_for_title(fake, f"{result.sheet_title}-sources")
    rows = sources_update["body"]["values"]

    assert rows == build_sources_rows([sa])
    assert rows[0] == ["domain", "index", "summary", "url", "source"]
    assert rows[1] == ["good.com", "1", "h: s", "https://example.com/x", "exa"]


def test_hook_cells_render_as_hyperlinks_pointing_at_sources_tab() -> None:
    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    sa = _scored("good.com", flag=False)
    result = writer.write([sa])

    sources_title = f"{result.sheet_title}-sources"
    results_update = _update_for_title(fake, result.sheet_title)
    rows = results_update["body"]["values"]
    headers = rows[0]
    hook_cell = rows[1][headers.index("hook_1")]
    gid = int(hook_cell.split("#gid=", 1)[1].split("&", 1)[0])
    lookup = _sources_row_lookup([sa])

    assert hook_cell.startswith('=HYPERLINK("#gid=')
    assert gid == _sheet_id(sources_title)
    assert f"&range=A{lookup[(sa.account.domain, 1)]}" in hook_cell


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


def test_unscoreable_row_gets_hook_suppressed_tint() -> None:
    from src.models import Account, Enrichment, ScoredAccount

    fake = FakeService()
    writer = SheetsWriter(credentials_path="/dev/null", service=fake)
    sa = ScoredAccount.unscoreable(
        Account(domain="dead.com"), Enrichment(account=Account(domain="dead.com")), "no data"
    )
    result = writer.write([sa])
    bg_calls = _background_requests(fake, _sheet_id(result.sheet_title))
    assert len(bg_calls) == 1
    bg = bg_calls[0]["repeatCell"]["cell"]["userEnteredFormat"]["backgroundColor"]
    assert bg == ACCOUNT_STATUS_COLORS[AccountStatus.hook_suppressed]
