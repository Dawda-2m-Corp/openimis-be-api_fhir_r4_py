from rest_framework import status
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from api_fhir_r4.mixins import MultiIdentifierRetrieverMixin, MultiIdentifierUpdateMixin
from api_fhir_r4.model_retrievers import UUIDIdentifierModelRetriever, CHFIdentifierModelRetriever
from api_fhir_r4.permissions import FHIRApiInsureePermissions
from api_fhir_r4.serializers import PatientSerializer
from api_fhir_r4.views.fhir.base import BaseFHIRView
from api_fhir_r4.views.filters import ValidityFromRequestParameterFilter
from policyholder.models import PolicyHolderUser, PolicyHolderInsuree
from insuree.models import Insuree


class PolicyHolderInsureeViewSet(viewsets.ModelViewSet):
    serializer_class = PatientSerializer
    permission_classes = (FHIRApiInsureePermissions,)

    def get_queryset(self):
        policy_holder_user = self._get_policy_holder_user()
        insuree_ids = self._get_policy_holder_insuree_ids(policy_holder_user)
        queryset = Insuree.objects.filter(pk__in=insuree_ids)
        return self._filter_queryset(queryset)

    def _get_policy_holder_user(self):
        user = self.request.user
        policy_holder_user = PolicyHolderUser.objects.filter(user=user, is_deleted=False).first()
        if not policy_holder_user:
            raise PermissionDenied("User does not have permission to access this resource.")
        return policy_holder_user

    def _get_policy_holder_insuree_ids(self, policy_holder_user):
        policy_holder_insurees = PolicyHolderInsuree.objects.filter(
            policy_holder=policy_holder_user.policy_holder,
            is_deleted=False
        )
        return policy_holder_insurees.values('insuree_id')

    def _filter_queryset(self, queryset):
        # Apply additional filtering based on request parameters
        return ValidityFromRequestParameterFilter(self.request).filter_queryset(queryset)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        identifier = request.query_params.get("identifier")
        if identifier:
            return self.retrieve(request, *args, **kwargs)
        else:
            page = self.paginate_queryset(queryset)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
