from rest_framework import status
from api_fhir_r4.mixins import MultiIdentifierRetrieverMixin, MultiIdentifierUpdateMixin
from api_fhir_r4.model_retrievers import UUIDIdentifierModelRetriever, CHFIdentifierModelRetriever
from api_fhir_r4.permissions import FHIRApiInsureePermissions, FHIRApiOrganizationPermissions
from api_fhir_r4.serializers import PatientSerializer
from api_fhir_r4.views.fhir.base import BaseFHIRView
from api_fhir_r4.views.filters import DateUpdatedRequestParameterFilter
from policyholder.models import PolicyHolderUser, PolicyHolderInsuree
from insuree.models import Insuree
from api_fhir_r4.serializers.Patient_PolicyHolderInsuree_Serializer import PatientPolicyHolderInsureeSerializer
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied


class PolicyHolderInsureePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class PolicyHolderInsureeViewSet(BaseFHIRView, MultiIdentifierRetrieverMixin,
                                 MultiIdentifierUpdateMixin, viewsets.ModelViewSet):
    retrievers = [UUIDIdentifierModelRetriever, CHFIdentifierModelRetriever]
    serializer_class = PatientPolicyHolderInsureeSerializer
    permission_classes = (FHIRApiOrganizationPermissions,)
    pagination_class = PolicyHolderInsureePagination

    def get_queryset(self):
        policy_holder_user = PolicyHolderUser.objects.filter(
            user=self.request.user, is_deleted=False).first()
        if not policy_holder_user:
            raise PermissionDenied(
                "User does not have permission to access this resource.")

        policy_holder_insurees = PolicyHolderInsuree.objects.filter(
            policy_holder=policy_holder_user.policy_holder, is_deleted=False)

        insuree_pks = policy_holder_insurees.values_list(
            'insuree__pk', flat=True)

        insuree_queryset = Insuree.objects.filter(pk__in=insuree_pks).select_related("gender")\
            .select_related("family")

        return DateUpdatedRequestParameterFilter(self.request).filter_queryset(insuree_queryset)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        identifier = request.GET.get("identifier")

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        if identifier:
            return self.retrieve(request, *args, **{**kwargs, 'identifier': identifier})
        else:
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
