"""CryptoAID canonical Core/User/Case package (CHAT01)."""

from .case_engine import CaseEngine, CoreError

# Public compatibility contract: consumers historically import CaseError.
# Keep CoreError as the implementation type and expose CaseError as a stable alias.
CaseError = CoreError

__all__ = ["CaseEngine", "CaseError", "CoreError"]
