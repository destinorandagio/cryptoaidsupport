"""CryptoAID canonical Core/User/Case package (CHAT01)."""

from .api import CORE_API_FACADE_VERSION, CoreAPI
from .case_engine import CoreError
from .case_engine_mvp import CORE_CASE_ENGINE_MVP_VERSION, CaseEngine
from .auth_session_guard import AUTH_SESSION_GUARD_VERSION
from .activation_claim import (
    ACCEPTED_ACTIVATION_CLAIM_VERSION,
    CORE_ACTIVATION_CLAIM_CONSUMER_VERSION,
    TrustedActivationClaimConsumer,
)
from .support_api import SUPPORT_API_FACADE_VERSION, TrustedSupportAPI

# Public compatibility contract: consumers historically import CaseError.
# Keep CoreError as the implementation type and expose CaseError as a stable alias.
CaseError = CoreError

__all__ = [
    "ACCEPTED_ACTIVATION_CLAIM_VERSION",
    "AUTH_SESSION_GUARD_VERSION",
    "CORE_ACTIVATION_CLAIM_CONSUMER_VERSION",
    "CORE_API_FACADE_VERSION",
    "CORE_CASE_ENGINE_MVP_VERSION",
    "SUPPORT_API_FACADE_VERSION",
    "CaseEngine",
    "CaseError",
    "CoreAPI",
    "CoreError",
    "TrustedActivationClaimConsumer",
    "TrustedSupportAPI",
]
