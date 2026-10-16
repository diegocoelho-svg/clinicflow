from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from apps.clinics.models import ClinicMembership


class CanManageProcedureCatalog(BasePermission):
    message = "Only clinic owners can manage procedures."

    def has_permission(self, request: Request, view) -> bool:
        membership = view.clinic_membership
        if request.method in ("POST", "PATCH"):
            return membership.role == ClinicMembership.Role.OWNER
        return True
