"""CHAT08 minimum admin/CRM operational surface for CryptoAID MVP."""

from .api import ADMIN_API_FACADE_VERSION, AdminAPI, AdminSessionResolver
from .ops import ADMIN_ROLE, ADMIN_VERSION, AdminError, AdminOps

__all__ = [
    "ADMIN_API_FACADE_VERSION",
    "ADMIN_ROLE",
    "ADMIN_VERSION",
    "AdminAPI",
    "AdminError",
    "AdminOps",
    "AdminSessionResolver",
]
