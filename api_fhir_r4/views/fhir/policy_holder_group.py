from rest_framework import viewsets

from api_fhir_r4.mixins import MultiIdentifierRetrieverMixin, MultiIdentifierUpdateMixin
from api_fhir_r4.model_retrievers import UUIDIdentifierModelRetriever, GroupIdentifierModelRetriever
from api_fhir_r4.permissions import FHIRApiGroupPermissions, IsPolicyHolderUser
from policyholder.models import PolicyHolder
from api_fhir_r4.serializers import PolicyHolderGroupSerializer
from api_fhir_r4.views.fhir.base import BaseFHIRView
from api_fhir_r4.views.filters import ValidityFromRequestParameterFilter, DateUpdatedRequestParameterFilter


class GroupViewSet2(BaseFHIRView, MultiIdentifierRetrieverMixin,
                    MultiIdentifierUpdateMixin, viewsets.ModelViewSet):
    retrievers = [UUIDIdentifierModelRetriever, GroupIdentifierModelRetriever]
    serializer_class = PolicyHolderGroupSerializer
    permission_classes = (IsPolicyHolderUser, FHIRApiGroupPermissions)

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
        identifier = request.GET.get("identifier")
        queryset = queryset.filter(is_deleted=False)

        if identifier:
            return self.retrieve(request, *args, **{**kwargs, 'identifier': identifier})

        serializer = PolicyHolderGroupSerializer(self.paginate_queryset(queryset), many=True)
        return self.get_paginated_response(serializer.data)

    def retrieve(self, *args, **kwargs):
        response = super().retrieve(self, *args, **kwargs)
        return response

    def get_queryset(self):
        queryset = PolicyHolder.objects.filter(is_deleted=False).order_by('date_created')
        return DateUpdatedRequestParameterFilter(self.request).filter_queryset(queryset)
