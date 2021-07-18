#
# This source file is part of the asyncio-foundationdb open source project
#
# Copyright 2021 Amirouche Boubekki <amirouche@hyper.dev>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from aiostream import pipe, stream
import asyncio


async def pool_for_each_par_map(loop, pool, f, p, iterator):
    zx = stream.iterate(iterator)
    zx = zx | pipe.map(lambda x: loop.run_in_executor(pool, p, x))
    async with zx.stream() as streamer:
        limit = pool._max_workers
        unfinished = []
        while True:
            tasks = []
            for i in range(limit):
                try:
                    task = await streamer.__anext__()
                except StopAsyncIteration:
                    limit = 0
                else:
                    tasks.append(task)
            tasks = tasks + list(unfinished)
            assert len(tasks) <= pool._max_workers
            if not tasks:
                break
            finished, unfinished = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for finish in finished:
                out = finish.result()
                f(out)
            limit = len(finished)
