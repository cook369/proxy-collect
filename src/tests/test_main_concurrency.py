import asyncio

import pytest

import main
from core.models import CollectorResult


@pytest.mark.asyncio
async def test_run_collectors_concurrently_respects_max_workers(monkeypatch, tmp_path):
    active = 0
    peak_active = 0

    async def fake_run_collector(collector_name, proxy_list, output_dir):
        nonlocal active, peak_active
        active += 1
        peak_active = max(peak_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return CollectorResult(
            site=collector_name,
            today_page=None,
            files={},
            status="success",
        )

    monkeypatch.setattr(main, "run_collector", fake_run_collector)

    results = await main.run_collectors_concurrently(
        ["a", "b", "c", "d"],
        proxy_list=[],
        output_dir=tmp_path,
        max_workers=2,
    )

    assert [result.site for result in results] == ["a", "b", "c", "d"]
    assert peak_active == 2
