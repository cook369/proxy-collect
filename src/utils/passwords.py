"""通用密码/口令候选尝试工具"""

from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from itertools import product
from queue import Empty, Full, Queue
import threading

from core.exceptions import ParseError

DEFAULT_PASSWORD_CHARSET = "0123456789"
DEFAULT_PASSWORD_LENGTH = 4
PASSWORD_QUEUE_FACTOR = 20
SENTINEL = object()


@dataclass(frozen=True)
class PasswordAttemptResult:
    """口令尝试结果"""

    password: str
    content: str


class FatalPasswordAttemptError(Exception):
    """不可当作候选口令错误继续尝试的失败。"""


@dataclass(frozen=True)
class CharsetPasswordStrategy:
    """按字符集和长度生成候选密码"""

    length: int = DEFAULT_PASSWORD_LENGTH
    charset: str = DEFAULT_PASSWORD_CHARSET

    def __post_init__(self) -> None:
        if self.length < 1:
            raise ParseError("Password length must be greater than 0")
        if not self.charset:
            raise ParseError("Password charset must not be empty")

    def iter_passwords(self) -> Iterator[str]:
        """按组合空间顺序流式生成密码"""
        for chars in product(self.charset, repeat=self.length):
            yield "".join(chars)


@dataclass(frozen=True)
class DictionaryPasswordStrategy:
    """按字典顺序生成候选密码"""

    passwords: Iterable[str]

    def iter_passwords(self) -> Iterator[str]:
        """按给定顺序流式生成密码"""
        return iter(self.passwords)


def _try_password_queue(
    password_queue: Queue,
    stop_event: threading.Event,
    try_password: Callable[[str], str],
) -> tuple[str, str] | None:
    """从密码队列消费候选并尝试解密"""
    while True:
        item = password_queue.get()
        if item is SENTINEL:
            return None

        if stop_event.is_set():
            continue

        password = str(item)
        try:
            result = try_password(password)
            stop_event.set()
            return password, result
        except FatalPasswordAttemptError:
            stop_event.set()
            raise
        except Exception:
            continue


def _drain_password_queue(password_queue: Queue) -> None:
    """清空待消费密码，避免已找到结果后生产者阻塞在哨兵入队"""
    while True:
        try:
            password_queue.get_nowait()
        except Empty:
            return


def _put_worker_sentinels(
    password_queue: Queue,
    workers: int,
) -> None:
    """给每个 worker 发送退出哨兵"""
    for _ in range(workers):
        while True:
            try:
                password_queue.put(SENTINEL, timeout=0.1)
                break
            except Full:
                _drain_password_queue(password_queue)


def brute_force_password(
    max_workers: int,
    *,
    password_strategy: (
        CharsetPasswordStrategy | DictionaryPasswordStrategy | None
    ) = None,
    try_password: Callable[[str], str],
) -> PasswordAttemptResult:
    """按候选策略并发尝试口令，返回第一个成功结果。"""
    strategy = password_strategy or CharsetPasswordStrategy()
    workers = max(1, max_workers)
    password_queue: Queue[str] = Queue(maxsize=workers * PASSWORD_QUEUE_FACTOR)
    stop_event = threading.Event()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _try_password_queue,
                password_queue,
                stop_event,
                try_password,
            )
            for _ in range(workers)
        ]

        for password in strategy.iter_passwords():
            while not stop_event.is_set():
                try:
                    password_queue.put(password, timeout=0.1)
                    break
                except Full:
                    continue
            if stop_event.is_set():
                break

        if stop_event.is_set():
            _drain_password_queue(password_queue)
        _put_worker_sentinels(password_queue, workers)

        for future in as_completed(futures):
            try:
                found = future.result()
            except FatalPasswordAttemptError:
                stop_event.set()
                for pending in futures:
                    if pending != future:
                        pending.cancel()
                raise
            except Exception:
                continue

            if not found:
                continue

            password, result = found
            stop_event.set()
            for pending in futures:
                if pending != future:
                    pending.cancel()
            return PasswordAttemptResult(password=password, content=result)

    raise ParseError("Failed to brute-force password")
