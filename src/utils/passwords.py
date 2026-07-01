"""通用密码/口令候选尝试工具（异步版本）"""

import asyncio
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from itertools import product

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


async def _try_password_worker(
    password_queue: asyncio.Queue,
    stop_event: asyncio.Event,
    try_password: Callable,
) -> tuple[str, str] | None:
    """从密码队列消费候选并尝试解密"""
    while True:
        item = await password_queue.get()
        if item is SENTINEL:
            return None

        if stop_event.is_set():
            continue

        password = str(item)
        try:
            result = try_password(password)
            # 如果 try_password 是协程，需要 await
            if asyncio.iscoroutine(result):
                result = await result
            stop_event.set()
            return password, result
        except FatalPasswordAttemptError:
            stop_event.set()
            raise
        except Exception:
            continue


async def _drain_password_queue(password_queue: asyncio.Queue) -> None:
    """清空待消费密码，避免已找到结果后生产者阻塞在哨兵入队"""
    while not password_queue.empty():
        try:
            password_queue.get_nowait()
        except asyncio.QueueEmpty:
            return


async def _put_worker_sentinels(
    password_queue: asyncio.Queue,
    workers: int,
) -> None:
    """给每个 worker 发送退出哨兵"""
    for _ in range(workers):
        await password_queue.put(SENTINEL)


async def brute_force_password(
    max_workers: int,
    *,
    password_strategy: (
        CharsetPasswordStrategy | DictionaryPasswordStrategy | None
    ) = None,
    try_password: Callable,
) -> PasswordAttemptResult:
    """按候选策略并发尝试口令，返回第一个成功结果。"""
    strategy = password_strategy or CharsetPasswordStrategy()
    workers = max(1, max_workers)
    password_queue: asyncio.Queue = asyncio.Queue(
        maxsize=workers * PASSWORD_QUEUE_FACTOR
    )
    stop_event = asyncio.Event()

    found: tuple[str, str] | None = None
    fatal_error: FatalPasswordAttemptError | None = None

    async def worker_wrapper() -> tuple[str, str] | None:
        nonlocal fatal_error
        try:
            return await _try_password_worker(
                password_queue, stop_event, try_password
            )
        except FatalPasswordAttemptError as e:
            fatal_error = e
            return None

    async with asyncio.TaskGroup() as tg:
        worker_tasks = [
            tg.create_task(worker_wrapper()) for _ in range(workers)
        ]

        # Producer
        async def produce() -> None:
            for password in strategy.iter_passwords():
                if stop_event.is_set():
                    break
                await password_queue.put(password)
            if stop_event.is_set():
                await _drain_password_queue(password_queue)
            await _put_worker_sentinels(password_queue, workers)

        producer_task = tg.create_task(produce())

        # Wait for workers, checking for results and errors
        pending = set(worker_tasks)

        while pending and not stop_event.is_set():
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                result = task.result()
                if result is not None:
                    password, content = result
                    found = (password, content)
                    stop_event.set()

                if fatal_error is not None:
                    stop_event.set()

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
        if not producer_task.done():
            producer_task.cancel()

        # Allow cancellation to propagate
        try:
            await asyncio.gather(*pending, return_exceptions=True)
        except Exception:
            pass

    if fatal_error is not None:
        raise fatal_error

    if found:
        return PasswordAttemptResult(password=found[0], content=found[1])

    raise ParseError("Failed to brute-force password")
