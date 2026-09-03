"""Shared pytest compatibility for legacy CHAT02 RPC fakes.

The production adapter now performs a post-transaction canonical block lookup.
Two older integration-test FakeRPC classes intentionally model only in-memory
rows and historically treated every eth_getBlockByNumber call as `finalized`.
Patch only those test doubles so they implement the standard block-number query
from their existing row data. Production code is never patched here.
"""
from __future__ import annotations


def _install_canonical_block_lookup(module) -> None:
    fake_cls = getattr(module, "FakeRPC", None)
    if fake_cls is None or getattr(fake_cls, "_caid_canonical_block_fixture", False):
        return
    original = fake_cls.__call__

    def canonical_aware_call(self, provider_id, method, params):
        if method == "eth_getBlockByNumber" and params and params != ["finalized", False]:
            raw_number = params[0]
            if isinstance(raw_number, str) and raw_number.startswith("0x"):
                try:
                    requested = int(raw_number, 16)
                except ValueError:
                    requested = None
                if requested is not None:
                    rows = [
                        row
                        for (provider, _tx_hash), row in getattr(self, "rows", {}).items()
                        if provider == provider_id and int(row.get("block", -1)) == requested
                    ]
                    if rows:
                        row = rows[-1]
                        return {"number": hex(requested), "hash": row["block_hash"]}
                    return None
        return original(self, provider_id, method, params)

    fake_cls.__call__ = canonical_aware_call
    fake_cls._caid_canonical_block_fixture = True


def pytest_collection_modifyitems(items):
    target_modules = {
        "tests.test_chat02_runtime_facade",
        "tests.test_chat02_http_transport",
    }
    for module in {item.module for item in items if item.module.__name__ in target_modules}:
        _install_canonical_block_lookup(module)
