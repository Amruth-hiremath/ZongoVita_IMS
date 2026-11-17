"""Signed snapshot bundle envelope (LD-78, AD-25).

The Platform Service periodically writes every customer's licence snapshot and the login
directory hashes to object storage, signed with an Ed25519 key. A product process that starts
while the Registry is unreachable loads the bundle as its last known-good state, after
verifying the signature. The bundle is useless to anyone who can only write to the bucket:
without the signing key they cannot forge an entitlement.
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from ims_common.tokens import KeySet, b64decode, b64encode
from ims_contracts.platform_api import SnapshotBundle

BUNDLE_OBJECT_KEY = "platform/snapshot-bundle/latest.json"
BUNDLE_CONTENT_TYPE = "application/json"
_ALG = "Ed25519"


class BundleVerificationError(Exception):
    """The stored bundle is missing a valid signature or cannot be parsed. Never use it."""


def seal(bundle: SnapshotBundle, keys: KeySet) -> bytes:
    payload = bundle.model_dump_json().encode("utf-8")
    kid, signature = keys.sign(payload)
    envelope = {"alg": _ALG, "kid": kid, "payload": b64encode(payload), "signature": b64encode(signature)}
    return json.dumps(envelope).encode("utf-8")


def unseal(data: bytes, keys: KeySet) -> SnapshotBundle:
    try:
        envelope = json.loads(data)
        if envelope["alg"] != _ALG:
            raise BundleVerificationError("unexpected signature algorithm")
        payload = b64decode(envelope["payload"])
        signature = b64decode(envelope["signature"])
        kid = envelope["kid"]
    except BundleVerificationError:
        raise
    except Exception as exc:
        raise BundleVerificationError("malformed bundle envelope") from exc
    if not isinstance(kid, str) or not keys.verify(kid, payload, signature):
        raise BundleVerificationError("bundle signature does not verify")
    try:
        return SnapshotBundle.model_validate_json(payload)
    except ValidationError as exc:
        raise BundleVerificationError("bundle payload does not match the contract") from exc
