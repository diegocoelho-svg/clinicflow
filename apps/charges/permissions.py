from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from apps.clinics.models import ClinicMembership


class CanAccessCharges(BasePermission):
    message = "Only clinic owners can cancel charges."

    def has_permission(self, request: Request, view) -> bool:
        membership = view.clinic_membership
        return view.action != "cancel" or membership.role == ClinicMembership.Role.OWNER
