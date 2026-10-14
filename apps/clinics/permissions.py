from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.clinics.models import Clinic, ClinicMembership


class IsClinicOwnerOrReadOnly(BasePermission):
    message = "Only clinic owners can edit the clinic."

    def has_object_permission(
        self, request: Request, view: APIView, obj: Clinic
    ) -> bool:
        memberships = ClinicMembership.objects.filter(clinic=obj, user=request.user)
        if request.method in SAFE_METHODS:
            return memberships.exists()
        return memberships.filter(role=ClinicMembership.Role.OWNER).exists()
