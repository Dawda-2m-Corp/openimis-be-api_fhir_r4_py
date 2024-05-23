from rest_framework import viewsets

from api_fhir_r4.mixins import MultiIdentifierRetrieverMixin
from api_fhir_r4.model_retrievers import UUIDIdentifierModelRetriever, CodeIdentifierModelRetriever
from api_fhir_r4.permissions import FHIRApiContributionPlanBundlePermissions
from api_fhir_r4.serializers import InsurancePlanContributionSerializer
from api_fhir_r4.views.fhir.base import BaseFHIRView
from api_fhir_r4.views.filters import ValidityFromRequestParameterFilter
from contribution_plan.models import ContributionPlanBundle


class InsurancePlanContributionViewSet(BaseFHIRView, MultiIdentifierRetrieverMixin, viewsets.ReadOnlyModelViewSet):
    retrievers = [UUIDIdentifierModelRetriever, CodeIdentifierModelRetriever]
    serializer_class = InsurancePlanContributionSerializer
    permission_classes = (FHIRApiContributionPlanBundlePermissions,)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        identifier = request.GET.get("identifier")
        if identifier:
            return self.retrieve(request, *args, **{**kwargs, 'identifier': identifier})
        else:
            queryset = queryset.filter(is_deleted=False)
        serializer = InsurancePlanContributionSerializer(self.paginate_queryset(queryset), many=True)
        return self.get_paginated_response(serializer.data)

    def retrieve(self, *args, **kwargs):
        response = super().retrieve(self, *args, **kwargs)
        return response

    def get_queryset(self):
        queryset = ContributionPlanBundle.objects.all().filter(is_deleted=False).order_by('date_created')
        return ValidityFromRequestParameterFilter(self.request).filter_queryset(queryset)