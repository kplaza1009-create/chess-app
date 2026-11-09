import asyncio

import pytest
from anyio import CancelScope, sleep

from app.api.games import _cancel_tasks


async def test_cancellation_during_mixed_task_cleanup_keeps_scope_identity() -> None:
    """Reproduce the TestClient exit race with deterministic event-loop ordering."""
    with CancelScope() as scope:
        receiver = asyncio.create_task(asyncio.sleep(60))
        wakeup = asyncio.create_task(asyncio.sleep(60))
        await asyncio.sleep(0)
        wakeup.cancel()
        await asyncio.sleep(0)
        assert wakeup.cancelled() and not receiver.done()
        # Match TestClient: cancel the handler while it drains a pending receiver
        # and an already-cancelled wakeup. No timing sleeps or retries are needed.
        asyncio.get_running_loop().call_soon(scope.cancel)
        await _cancel_tasks(receiver, wakeup)
        assert receiver.done() and wakeup.done()
        await sleep(0)
        pytest.fail("The caller's cancellation must still be delivered")
    assert scope.cancelled_caught


async def test_cleanup_completes_inside_already_cancelled_scope() -> None:
    cleaned = asyncio.Event()

    async def receiver() -> None:
        try:
            await asyncio.sleep(60)
        finally:
            await asyncio.sleep(0)
            cleaned.set()

    task = asyncio.create_task(receiver())
    await asyncio.sleep(0)
    with CancelScope() as scope:
        scope.cancel()
        try:
            await sleep(0)
        finally:
            await _cancel_tasks(task)
            assert cleaned.is_set()
    assert scope.cancelled_caught and task.cancelled()


async def test_plain_asyncio_handler_cancellation_is_not_swallowed() -> None:
    ready = asyncio.Event()
    cleaned = asyncio.Event()
    children: list[asyncio.Task[None]] = []

    async def handler() -> None:
        children.append(asyncio.create_task(asyncio.sleep(60)))
        try:
            ready.set()
            await asyncio.sleep(60)
        finally:
            await _cancel_tasks(*children)
            cleaned.set()

    task = asyncio.create_task(handler())
    await ready.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned.is_set() and all(child.done() for child in children)
