"""ManifestService 单元测试"""

import json
import tempfile
from pathlib import Path

from services.manifest_service import ManifestService
from core.models import CollectorResult, FileManifest, SiteManifest


class TestManifestServiceInit:
    """ManifestService 初始化测试"""

    def test_init_with_nonexistent_file(self):
        """测试文件不存在时的初始化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"
            service = ManifestService(manifest_file)

            assert service.last_run is None
            assert service.sites == {}

    def test_init_with_existing_file(self):
        """测试文件存在时的初始化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"

            # 创建测试数据
            data = {
                "last_run": "2026-01-30 10:00:00",
                "sites": {
                    "test_site": {
                        "today_page": "http://example.com/today",
                        "status": "success",
                        "updated_at": "2026-01-30 10:00:00",
                        "files": {
                            "clash.yaml": {
                                "url": "http://example.com/clash.yaml",
                                "success": True,
                            }
                        },
                    }
                },
            }
            manifest_file.write_text(json.dumps(data), encoding="utf-8")

            service = ManifestService(manifest_file)

            assert service.last_run == "2026-01-30 10:00:00"
            assert "test_site" in service.sites
            assert service.sites["test_site"].status == "success"

    def test_init_with_invalid_json(self):
        """测试无效 JSON 文件的处理"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"
            manifest_file.write_text("invalid json", encoding="utf-8")

            # 应该不抛出异常，只是记录警告
            service = ManifestService(manifest_file)
            assert service.sites == {}


class TestManifestServiceShouldDownload:
    """should_download 方法测试"""

    def test_should_download_new_site(self):
        """测试新站点应该下载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"
            service = ManifestService(manifest_file)

            assert (
                service.should_download("new_site", "http://example.com/file") is True
            )

    def test_should_download_existing_url_success(self):
        """测试已成功下载的 URL 不需要重新下载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"
            service = ManifestService(manifest_file)

            # 添加已下载的记录
            service.sites["test_site"] = SiteManifest(
                today_page="http://example.com/today",
                status="success",
                updated_at="2026-01-30",
                files={
                    "clash.yaml": FileManifest(
                        url="http://example.com/clash.yaml", success=True
                    )
                },
            )

            result = service.should_download(
                "test_site", "http://example.com/clash.yaml"
            )
            assert result is False

    def test_should_download_existing_url_failed(self):
        """测试下载失败的 URL 需要重新下载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"
            service = ManifestService(manifest_file)

            service.sites["test_site"] = SiteManifest(
                today_page="http://example.com/today",
                status="partial",
                updated_at="2026-01-30",
                files={
                    "clash.yaml": FileManifest(
                        url="http://example.com/clash.yaml",
                        success=False,
                        error="Download failed",
                    )
                },
            )

            result = service.should_download(
                "test_site", "http://example.com/clash.yaml"
            )
            assert result is True


class TestManifestServiceUpdateFromResult:
    """update_from_result 方法测试"""

    def test_update_from_success_result(self):
        """测试从成功结果更新"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"
            service = ManifestService(manifest_file)

            result = CollectorResult(
                site="test_site",
                today_page="http://example.com/today",
                files={
                    "clash.yaml": FileManifest(
                        url="http://example.com/clash.yaml", success=True
                    )
                },
                status="success",
            )

            service.update_from_result(result)

            assert "test_site" in service.sites
            assert service.sites["test_site"].status == "success"
            assert service.sites["test_site"].updated_at is not None

    def test_update_from_failed_result(self):
        """测试从失败结果更新"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"
            service = ManifestService(manifest_file)

            result = CollectorResult(
                site="test_site",
                today_page=None,
                files={},
                status="failed",
                error="Connection error",
            )

            service.update_from_result(result)

            assert service.sites["test_site"].status == "failed"
            assert service.sites["test_site"].updated_at is None
            assert service.sites["test_site"].error == "Connection error"


class TestManifestServiceSave:
    """save 方法测试"""

    def test_save_creates_file(self):
        """测试保存创建文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "subdir" / "manifest.json"
            service = ManifestService(manifest_file)

            service.sites["test_site"] = SiteManifest(
                today_page="http://example.com/today",
                status="success",
                updated_at="2026-01-30",
                files={
                    "clash.yaml": FileManifest(
                        url="http://example.com/clash.yaml", success=True
                    )
                },
            )

            service.save()

            assert manifest_file.exists()
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            assert "last_run" in data
            assert "test_site" in data["sites"]

    def test_save_preserves_error_info(self):
        """测试保存保留错误信息"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"
            service = ManifestService(manifest_file)

            service.sites["test_site"] = SiteManifest(
                today_page=None,
                status="failed",
                updated_at=None,
                files={
                    "clash.yaml": FileManifest(
                        url="http://example.com/clash.yaml",
                        success=False,
                        error="Download failed",
                    )
                },
                error="Site error",
            )

            service.save()

            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            site_data = data["sites"]["test_site"]
            assert site_data["error"] == "Site error"
            assert site_data["files"]["clash.yaml"]["error"] == "Download failed"


class TestManifestServiceGetSite:
    """get_site 方法测试"""

    def test_get_existing_site(self):
        """测试获取存在的站点"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"
            service = ManifestService(manifest_file)

            service.sites["test_site"] = SiteManifest(
                today_page="http://example.com",
                status="success",
                updated_at="2026-01-30",
                files={},
            )

            site = service.get_site("test_site")
            assert site is not None
            assert site.status == "success"

    def test_get_nonexistent_site(self):
        """测试获取不存在的站点"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "manifest.json"
            service = ManifestService(manifest_file)

            site = service.get_site("nonexistent")
            assert site is None
