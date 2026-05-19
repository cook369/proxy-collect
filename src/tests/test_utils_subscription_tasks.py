"""订阅任务提取辅助函数测试"""

from core.models import DownloadTask
from utils.extractors import create_download_tasks_from_regex_rules


def test_create_download_tasks_from_regex_rules_builds_tasks_in_rule_order():
    content = """
    V2ray:
    https://example.com/v2ray.txt
    clash:
    https://example.com/clash.yaml
    """
    rules = {
        "v2ray.txt": r"V2ray.*?(https?://[^\s]+?\.txt)",
        "clash.yaml": r"clash.*?(https?://[^\s]+?\.yaml)",
    }

    assert create_download_tasks_from_regex_rules(content, rules) == [
        DownloadTask(filename="v2ray.txt", url="https://example.com/v2ray.txt"),
        DownloadTask(filename="clash.yaml", url="https://example.com/clash.yaml"),
    ]


def test_create_download_tasks_from_regex_rules_ignores_missing_matches():
    assert (
        create_download_tasks_from_regex_rules(
            "no subscription links",
            {"v2ray.txt": r"V2ray.*?(https?://[^\s]+?\.txt)"},
        )
        == []
    )
