from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "frontend" / "src" / "main.tsx"
STYLES = (
    ROOT / "frontend" / "src" / "profiles"
    / "BusinessCabinetDashboardParity.css"
)


def test_active_business_stylesheet_is_loaded_once_by_frontend_bootstrap():
    source = MAIN.read_text(encoding="utf-8")
    assert 'import "./profiles/BusinessCabinetDashboardParity.css";' in source
    assert 'import "./profiles/BusinessProfileV2.css";' not in source


def test_active_business_stylesheet_covers_rendered_dashboard_contract():
    css = STYLES.read_text(encoding="utf-8")
    for selector in (
        ".business-cabinet__panel",
        ".business-cabinet__identity",
        ".business-cabinet__stats",
        ".business-cabinet__stat",
        ".business-cabinet__content",
        ".business-cabinet__group-heading",
        ".business-cabinet__menu-grid",
        ".business-cabinet__activity",
        ".business-cabinet__activity-row",
    ):
        assert selector in css

    assert "@media (max-width: 680px)" in css
    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in css
