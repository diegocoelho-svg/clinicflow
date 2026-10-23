"""One membership lookup for every clinic-scoped HTTP view."""

from functools import cached_property

from django.shortcuts import get_object_or_404
from rest_framework.request import Request
from rest_framework.viewsets import GenericViewSet

from apps.clinics.models import Clinic, ClinicMembership


class ClinicScopedViewSet(GenericViewSet):
    @cached_property
    def clinic_membership(self) -> ClinicMembership:
        # Authentication runs first. Superuser/staff flags never bypass membership.
        return get_object_or_404(
            ClinicMembership.objects.select_related("clinic"),
            clinic_id=self.kwargs["clinic_id"],
            user=self.request.user,
        )

    @property
    def clinic(self) -> Clinic:
        return self.clinic_membership.clinic

    def initial(self, request: Request, *args, **kwargs) -> None:
        super().initial(request, *args, **kwargs)
        _ = self.clinic_membership
