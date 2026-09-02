"""CHAT02 Evidence/Payment/Entitlement authority package."""

from .engine import EvidencePaymentError
from .secure_engine import EvidencePaymentEngine

# Importing ``evidence_payment.engine`` still executes this package initializer.
# Patch the legacy module attribute so direct runtime imports cannot bypass the
# canonical path-containment guard.
from . import engine as _engine_module
_engine_module.EvidencePaymentEngine = EvidencePaymentEngine

__all__ = ["EvidencePaymentEngine", "EvidencePaymentError"]
