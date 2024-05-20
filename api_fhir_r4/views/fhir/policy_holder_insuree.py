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
import datetime

class PolicyHolderInsureeViewSet(BaseFHIRView, MultiIdentifierRetrieverMixin,
                     MultiIdentifierUpdateMixin, viewsets.ModelViewSet):
    retrievers = [UUIDIdentifierModelRetriever, CHFIdentifierModelRetriever]
    serializer_class = PatientSerializer
    permission_classes = (FHIRApiInsureePermissions,)

    def get_queryset(self):
        try:
            # Get the PolicyHolderUser associated with the request user
            policy_holder_user = PolicyHolderUser.objects.filter(user=self.request.user, is_deleted=False).first()
            if not policy_holder_user:
                raise PermissionDenied("User does not have permission to access this resource.")
            
            # Get all insurees associated with the policy holder user's organization
            queryset = Insuree.objects.filter(
                id__in=PolicyHolderInsuree.objects.filter(
                    policy_holder=policy_holder_user.policy_holder, is_deleted=False
                ).values_list('insuree_id', flat=True)
            )

            # Apply additional filtering based on request parameters
            queryset = ValidityFromRequestParameterFilter(self.request).filter_queryset(queryset)
            return queryset
        
        except PolicyHolderUser.DoesNotExist:
            raise PermissionDenied("User does not have permission to access this resource.")

    def list(self, request, *args, **kwargs):
        """
        Retrieves a list of insurees associated with the policy holder user's organization.

        If an identifier is provided in the request parameters, it calls the `retrieve` method to retrieve a specific insuree.
        Otherwise, it filters the queryset, paginates the results, and returns the serialized data.

        :param request: The HTTP request object containing the request parameters.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: The paginated response containing the serialized data of the insurees.
        """
        queryset = self.get_queryset()
        identifier = request.GET.get("identifier")
        if identifier:
            return self.retrieve(request, *args, **{**kwargs, 'identifier': identifier})
        else:
            serializer = self.get_serializer(self.paginate_queryset(queryset), many=True)
            return self.get_paginated_response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieves a specific insuree by identifier.

        :param request: The HTTP request object containing the request parameters.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: The response containing the serialized data of the specific insuree.
        """
        return super().retrieve(request, *args, **kwargs)
