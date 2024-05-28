from rest_framework import status
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from api_fhir_r4.mixins import MultiIdentifierRetrieverMixin, MultiIdentifierUpdateMixin
from api_fhir_r4.model_retrievers import UUIDIdentifierModelRetriever, CHFIdentifierModelRetriever,CodeIdentifierModelRetriever
from api_fhir_r4.serializers import InsurancePlanContributionSerializer
from api_fhir_r4.views.fhir.base import BaseFHIRView
from api_fhir_r4.views.filters import ValidityFromRequestParameterFilter
from policyholder.models import PolicyHolderUser, PolicyHolderContributionPlan
from contribution_plan.models import ContributionPlanBundle
from api_fhir_r4.permissions import FHIRApiContributionPlanBundlePermissions


class PolicyHolderContributionBundleViewSet(BaseFHIRView, MultiIdentifierRetrieverMixin, viewsets.ReadOnlyModelViewSet):
    
    retrievers = [UUIDIdentifierModelRetriever, CodeIdentifierModelRetriever]
    serializer_class = InsurancePlanContributionSerializer
    permission_classes = (FHIRApiContributionPlanBundlePermissions,)

    def get_queryset(self):
        policy_holder_user = self._get_policy_holder_user()
        contribution_plan_bundle_ids = self._get_policy_holder_contribution_plan_bundle_ids(policy_holder_user)
        queryset = ContributionPlanBundle.objects.filter(pk__in=contribution_plan_bundle_ids)
        return self._filter_queryset(queryset)

    def _get_policy_holder_user(self):
        user = self.request.user
        policy_holder_user = PolicyHolderUser.objects.filter(user=user, is_deleted=False).first()
        if not policy_holder_user:
            raise PermissionDenied("User does not have permission to access this resource.")
        return policy_holder_user

    def _get_policy_holder_contribution_plan_bundle_ids(self, policy_holder_user):
        policy_holder_insurees = PolicyHolderContributionPlan.objects.filter(
            policy_holder=policy_holder_user.policy_holder,
            is_deleted=False
        )
        return policy_holder_insurees.values('contribution_plan_bundle__id')

    def _filter_queryset(self, queryset):
        # Apply additional filtering based on request parameters
        return ValidityFromRequestParameterFilter(self.request).filter_queryset(queryset)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        identifier = request.GET.get("identifier")
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
