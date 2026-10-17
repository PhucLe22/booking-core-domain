from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from core.constant import STAFF_ROLE_CODES, RoleCode


class RoleRequiredMiddleware(BasePermission):
    """Allows only users that have one of role_codes."""

    role_codes = []
    message = "You do not have permission to perform this action!"

    def has_permission(self, request: Request, view):
        user = request.user
        if user and user.is_authenticated and user.has_role(*self.role_codes):
            return True
        raise PermissionDenied(self.message)


class StaffMiddleware(RoleRequiredMiddleware):
    role_codes = STAFF_ROLE_CODES
    message = "Only staff can perform this action!"


class AdminMiddleware(RoleRequiredMiddleware):
    role_codes = [RoleCode.ADMIN]
    message = "Only admin can perform this action!"
