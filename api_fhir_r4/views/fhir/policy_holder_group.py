from rest_framework import viewsets
import logging
from rest_framework.exceptions import PermissionDenied
from api_fhir_r4.mixins import MultiIdentifierRetrieverMixin, MultiIdentifierUpdateMixin
from api_fhir_r4.model_retrievers import UUIDIdentifierModelRetriever, GroupIdentifierModelRetriever
from api_fhir_r4.permissions import FHIRApiGroupPermissions, IsPolicyHolderUser
from policyholder.models import PolicyHolder, PolicyHolderUser
from api_fhir_r4.serializers import PolicyHolderGroupSerializer
from api_fhir_r4.views.fhir.base import BaseFHIRView
from api_fhir_r4.views.filters import ValidityFromRequestParameterFilter,DateUpdatedRequestParameterFilter
from insuree.models import Family
logger = logging.getLogger(__name__)



class GroupViewSet2(BaseFHIRView, MultiIdentifierRetrieverMixin,
                    MultiIdentifierUpdateMixin, viewsets.ModelViewSet):
    retrievers = [UUIDIdentifierModelRetriever, GroupIdentifierModelRetriever]
    serializer_class = PolicyHolderGroupSerializer
    permission_classes = (FHIRApiGroupPermissions,)

    def get_queryset(self):
        try:
            policy_holder_user = PolicyHolderUser.objects.filter(user=self.request.user, is_deleted=False).first()
        except PolicyHolderUser.DoesNotExist:
            raise PermissionDenied("User does not have permission to access this resource.")
        
        queryset = PolicyHolder.objects.filter(pk=policy_holder_user.policy_holder.pk, is_deleted=False)
        identifier = self.request.GET.get("identifier")
        if identifier:
            queryset = queryset.filter(identifier=identifier)
        
        return DateUpdatedRequestParameterFilter(self.request).filter_queryset(queryset)
                          
    def list(self, request, *args, **kwargs):
        """
        Retrieves a list of policy holder groups.

        If an identifier is provided in the request parameters, it calls the `retrieve` method to retrieve a specific group.
        Otherwise, it filters the queryset to exclude deleted groups, paginates the results, and returns the serialized data.

        :param request: The HTTP request object containing the request parameters.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: The paginated response containing the serialized data of the policy holder groups.
        """
        queryset = self.get_queryset()
        if request.GET.get("identifier"):
            return self.retrieve(request, *args, **kwargs)
        else:
            serializer = self.get_serializer(self.paginate_queryset(queryset), many=True)
            return self.get_paginated_response(serializer.data)
          
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
