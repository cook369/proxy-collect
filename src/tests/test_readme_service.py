"""README service tests."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from core.models import SiteManifest
from services import readme_service
from services.manifest_service import ManifestService
from services.readme_service import ReadmeService


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 7, 2, tzinfo=tz)


def make_readme_service() -> ReadmeService:
    manifest = cast(ManifestService, SimpleNamespace(last_run=None, sites={}))
    return ReadmeService(
        manifest=manifest,
        readme_file=Path("README.md"),
        github_prefix="https://ghproxy.net",
        output_dir=Path("dist"),
    )


def test_get_data_from_title_normalizes_existing_supported_formats():
    service = make_readme_service()

    assert service.get_data_from_title("节点更新 2026-07-02") == "2026-07-02"
    assert service.get_data_from_title("节点更新 2026/7/2") == "2026-07-02"
    assert service.get_data_from_title("节点更新 2026年7月2日") == "2026-07-02"
    assert service.get_data_from_title("节点更新 2/7/2026") == "2026-07-02"


def test_get_data_from_title_uses_current_year_for_yearless_chinese_date(
    monkeypatch,
):
    monkeypatch.setattr(readme_service, "datetime", FixedDatetime)
    service = make_readme_service()

    assert service.get_data_from_title("节点更新 7月2日") == "2026-07-02"


def test_get_data_from_title_uses_current_year_for_zero_padded_month(
    monkeypatch,
):
    monkeypatch.setattr(readme_service, "datetime", FixedDatetime)
    service = make_readme_service()

    assert service.get_data_from_title("节点更新 07月2日") == "2026-07-02"


def test_get_data_from_title_returns_none_when_no_supported_date():
    service = make_readme_service()

    assert service.get_data_from_title("节点今日更新") is None


def test_build_status_section_displays_timestamps_in_china_timezone():
    manifest = cast(
        ManifestService,
        SimpleNamespace(
            last_run="2026-07-02 16:35:00",
            sites={
                "site": SiteManifest(
                    today_page=None,
                    status="failed",
                    updated_at=None,
                    files={},
                    collected_at="2026-07-02 16:30:00",
                )
            },
        ),
    )
    service = ReadmeService(
        manifest=manifest,
        readme_file=Path("README.md"),
        github_prefix="https://ghproxy.net",
        output_dir=Path("dist"),
    )

    lines = service._build_status_section("owner/repo", "main")

    assert any("2026-07-03 00:30" in line for line in lines)
    assert any("**最后运行**: 2026-07-03 00:35:00" in line for line in lines)


def test_build_status_section_links_site_name_to_collector_home_page():
    manifest = cast(
        ManifestService,
        SimpleNamespace(
            last_run=None,
            sites={
                "jichangx": SiteManifest(
                    today_page=None,
                    status="failed",
                    updated_at=None,
                    files={},
                )
            },
        ),
    )
    service = ReadmeService(
        manifest=manifest,
        readme_file=Path("README.md"),
        github_prefix="https://ghproxy.net",
        output_dir=Path("dist"),
    )

    lines = service._build_status_section("owner/repo", "main")

    assert any("| [jichangx](https://jichangx.com) |" in line for line in lines)
