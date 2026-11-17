"""Snapshot bundle publisher (LD-78, AD-25).

Every five minutes the Platform Service writes one signed object holding every licensed
customer's snapshot and the resolvable login-directory hashes. Products honour it as last
known-good when they start during a Registry outage.
"""

from __future__ import annotations

import asyncio
import logging

from ims_common.clock import Clock, SystemClock
from ims_common.objectstore import ObjectStore
from ims_common.snapshot_bundle import BUNDLE_CONTENT_TYPE, BUNDLE_OBJECT_KEY, seal
from ims_common.tokens import KeySet
from ims_contracts.platform_api import SnapshotBundle
from ims_platform.registry import RegistryService

log = logging.getLogger("ims.platform.bundle")


class BundlePublisher:
    def __init__(
        self,
        registry: RegistryService,
        store: ObjectStore,
        signing_keys: KeySet,
        clock: Clock | None = None,
    ) -> None:
        self._registry = registry
        self._store = store
        self._keys = signing_keys
        self._clock = clock or SystemClock()

    async def publish_once(self) -> SnapshotBundle:
        snapshots = await self._registry.list_snapshots()
        directory = await self._registry.list_directory()
        bundle = SnapshotBundle(
            generated_at=self._clock.now(),
            # Snapshots are read one statement before the directory; the bundle is consistent
            # with the lowest feed position any of its snapshots saw.
            feed_seq=min((s.feed_seq for s in snapshots), default=0),
            snapshots=snapshots,
            directory=directory,
        )
        await self._store.put(BUNDLE_OBJECT_KEY, seal(bundle, self._keys), content_type=BUNDLE_CONTENT_TYPE)
        log.info("snapshot bundle published", extra={"count": len(snapshots), "feed_seq": bundle.feed_seq})
        return bundle

    async def run(self, interval_seconds: float) -> None:
        """Publish now and then on every interval until cancelled. A failed round is logged and
        retried on the next interval; the previous bundle stays in place."""
        while True:
            try:
                await self.publish_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("snapshot bundle publication failed", extra={"alarm": "bundle_publish_failed"})
            await asyncio.sleep(interval_seconds)
