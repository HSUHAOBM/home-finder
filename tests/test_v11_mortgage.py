from __future__ import annotations

from pathlib import Path

from home_finder import web_app_v11


def test_v11_page_loads_mortgage_assets():
    with web_app_v11.app.test_request_context("/"):
        page = web_app_v11.index_v11()

    assert "/static/dashboard_v11.css" in page
    assert "/static/dashboard_v11.js" in page


def test_v11_script_exposes_required_mortgage_scenarios_and_formula():
    script = (
        Path(web_app_v11.__file__).with_name("static") / "dashboard_v11.js"
    ).read_text(encoding="utf-8")

    assert "MORTGAGE_DEFAULT_RATE_V11 = 2.30" in script
    assert "{ downPaymentRate: 20, years: 30 }" in script
    assert "{ downPaymentRate: 20, years: 40 }" in script
    assert "{ downPaymentRate: 30, years: 30 }" in script
    assert "{ downPaymentRate: 30, years: 40 }" in script
    assert "principal * monthlyRate * factor / (factor - 1)" in script
    assert "annualRate === 0" in script
    assert "window.calculateMortgageV11" in script


def test_launcher_and_readme_use_v11():
    root = Path(web_app_v11.__file__).parents[2]

    assert "home_finder.web_app_v11" in (
        root / "開啟找房介面.cmd"
    ).read_text(encoding="utf-8")
    assert "home_finder.web_app_v11" in (
        root / "README.md"
    ).read_text(encoding="utf-8")
