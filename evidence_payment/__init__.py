"""CHAT02 Evidence/Payment/Entitlement authority package."""

from .engine import EvidencePaymentError
from .idempotency_engine import EvidencePaymentEngine

# Importing legacy implementation modules still executes this package initializer.
# Patch their exported class attributes so runtime imports cannot bypass either
# private-Evidence containment or payload-bound idempotency.
from . import engine as _engine_module
from . import mvp_engine as _mvp_engine_module
from . import secure_engine as _secure_engine_module

_engine_module.EvidencePaymentEngine = EvidencePaymentEngine
_mvp_engine_module.EvidencePaymentEngine = EvidencePaymentEngine
_secure_engine_module.EvidencePaymentEngine = EvidencePaymentEngine

__all__ = ["EvidencePaymentEngine", "EvidencePaymentError"]
