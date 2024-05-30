import uuid
from rest_framework.decorators import api_view
from rest_framework import status
from rest_framework.response import Response
from api_fhir_r4.serializers import ContractSerializer
from contract.models import Contract
from rest_framework import viewsets
import logging
from rest_framework.exceptions import PermissionDenied
from api_fhir_r4.permissions import FHIRApiGroupPermissions
from policyholder.models import PolicyHolder, PolicyHolderUser
from api_fhir_r4.views.fhir.base import BaseFHIRView
from api_fhir_r4.views.filters import DateUpdatedRequestParameterFilter
from api_fhir_r4.serializers.policyHolderGroupContractSerializer import PolicyHolderGroupContractSerializer, ContractSerializer
logger = logging.getLogger(__name__)


class GroupContractsViewset(BaseFHIRView, viewsets.ReadOnlyModelViewSet):
    serializer_class = PolicyHolderGroupContractSerializer
    permission_classes = (FHIRApiGroupPermissions,)

    def get_queryset(self):
        try:
            # Get the first PolicyHolderUser instance
            policy_holder_user = PolicyHolderUser.objects.filter(
                user=self.request.user, is_deleted=False).first()
            if not policy_holder_user:
                raise PermissionDenied(
                    "User does not have permission to access this resource.")

            # Get the corresponding PolicyHolder instance
            policy_holder = PolicyHolder.objects.get(
                pk=policy_holder_user.policy_holder.pk, is_deleted=False)

        except PolicyHolder.DoesNotExist:
            raise PermissionDenied(
                "PolicyHolder does not exist or has been deleted.")

        # Filter contracts by the retrieved policy_holder's ID
        queryset = Contract.objects.filter(policy_holder_id=policy_holder.pk)
        return DateUpdatedRequestParameterFilter(self.request).filter_queryset(queryset)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


@api_view(['POST'])
def AddContractToOrganization(request):
    user = request.user

    if request.method == "POST":
        try:
            policy_holder_user = PolicyHolderUser.objects.filter(
                user=user, is_deleted=False).first()
            if not policy_holder_user:
                raise PermissionDenied(
                    "User does not have permission to access this resource.")

        except PolicyHolderUser.DoesNotExist:
            raise PermissionDenied("User does not exist or has been deleted.")

        requested_code = request.data.get("code")

        request_data = {
            "code": requested_code,
            "user_created": policy_holder_user.user.pk,
            "policy_holder": policy_holder_user.policy_holder.uuid,
            "user_updated": policy_holder_user.user.pk,
            "username": policy_holder_user.user.username
        }

        serializer = ContractSerializer(data=request_data)
        if serializer.is_valid():
            print(request_data)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.debug(serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
