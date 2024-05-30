import uuid
from rest_framework import viewsets
from api_fhir_r4.pagination.policy_holder_organization import CustomPropertyPagination
import logging
from rest_framework.exceptions import PermissionDenied
from api_fhir_r4.mixins import MultiIdentifierRetrieverMixin, MultiIdentifierUpdateMixin
from api_fhir_r4.model_retrievers import UUIDIdentifierModelRetriever, GroupIdentifierModelRetriever
from api_fhir_r4.permissions import FHIRApiOrganizationPermissions
from policyholder.models import PolicyHolder, PolicyHolderUser
from api_fhir_r4.serializers import PolicyHolderGroupSerializer
from api_fhir_r4.views.fhir.base import BaseFHIRView
from api_fhir_r4.views.filters import DateUpdatedRequestParameterFilter
logger = logging.getLogger(__name__)


class GroupViewSet2(BaseFHIRView, MultiIdentifierRetrieverMixin,
                    MultiIdentifierUpdateMixin, viewsets.ModelViewSet):
    retrievers = [UUIDIdentifierModelRetriever, GroupIdentifierModelRetriever]
    serializer_class = PolicyHolderGroupSerializer

    permission_classes = (FHIRApiOrganizationPermissions,)
    pagination_class = CustomPropertyPagination

    def get_queryset(self):
        try:
            policy_holder_user = PolicyHolderUser.objects.filter(
                user=self.request.user, is_deleted=False).first()
        except PolicyHolderUser.DoesNotExist:
            raise PermissionDenied(
                "User does not have permission to access this resource.")

        queryset = PolicyHolder.objects.filter(
            pk=policy_holder_user.policy_holder.pk, is_deleted=False)
        return DateUpdatedRequestParameterFilter(self.request).filter_queryset(queryset)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if request.GET.get("identifier"):
            return self.retrieve(request, *args, **kwargs)
        else:
            serializer = self.get_serializer(
                self.paginate_queryset(queryset), many=True)
            return self.get_paginated_response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
