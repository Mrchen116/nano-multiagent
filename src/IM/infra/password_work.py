"""Bound password CPU work without queuing requests or releasing cancelled work early."""

import asyncio
from functools import partial

from IM.infra.auth_limits import RateLimited
from IM.infra.company_gate import await_outside_gate


class PasswordWork:
    """Keep at most two actual worker computations alive for this IM process."""

    def __init__(self):
        self._active = 0

    async def run(self, function, *args):
        """Run pure password work, rejecting saturation immediately."""
        if self._active >= 2:
            raise RateLimited(1)
        self._active += 1
        future = asyncio.get_running_loop().run_in_executor(
            None, partial(function, *args)
        )

        def finished(completed):
            self._active -= 1
            completed.exception()

        future.add_done_callback(finished)
        return await await_outside_gate(asyncio.shield(future))
