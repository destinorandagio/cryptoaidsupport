"""CHAT02 Evidence/Payment/Entitlement authority package."""

from .engine import EvidencePaymentError
from .authorization_engine import EvidencePaymentEngine
from .rpc_adapter import RPC_PROVENANCE_VERSION, TrustedPolygonRPCAdapter
from .runtime_facade import (
    CORE_ACTIVATION_CLAIM_VERSION,
    RUNTIME_FACADE_VERSION,
    RuntimeAuthorityConfig,
    TrustedEvidencePaymentRuntimeFacade,
)

# Importing legacy implementation modules still executes this package initializer.
# Patch their exported class attributes so runtime imports cannot bypass private
# Evidence containment, payload-bound idempotency, or explicit authorization.
from . import engine as _engine_module
from . import mvp_engine as _mvp_engine_module
from . import secure_engine as _secure_engine_module
from . import idempotency_engine as _idempotency_engine_module

_engine_module.EvidencePaymentEngine = EvidencePaymentEngine
_mvp_engine_module.EvidencePaymentEngine = EvidencePaymentEngine
_secure_engine_module.EvidencePaymentEngine = EvidencePaymentEngine
_idempotency_engine_module.EvidencePaymentEngine = EvidencePaymentEngine

__all__ = [
    "EvidencePaymentEngine",
    "EvidencePaymentError",
    "TrustedPolygonRPCAdapter",
    "RPC_PROVENANCE_VERSION",
    "TrustedEvidencePaymentRuntimeFacade",
    "RuntimeAuthorityConfig",
    "RUNTIME_FACADE_VERSION",
    "CORE_ACTIVATION_CLAIM_VERSION",
]
