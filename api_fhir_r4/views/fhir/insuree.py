from rest_framework import status
import datetime
import uuid
from django.db.models import OuterRef, Exists
from rest_framework import viewsets, status
from rest_framework.response import Response

from api_fhir_r4.converters import OperationOutcomeConverter
from api_fhir_r4.mixins import MultiIdentifierRetrieverMixin, MultiIdentifierUpdateMixin
from api_fhir_r4.model_retrievers import UUIDIdentifierModelRetriever, CHFIdentifierModelRetriever
from api_fhir_r4.permissions import FHIRApiInsureePermissions
from api_fhir_r4.serializers import PatientSerializer
from api_fhir_r4.views.fhir.base import BaseFHIRView
from api_fhir_r4.views.filters import ValidityFromRequestParameterFilter
from claim.models import Claim
from insuree.models import Insuree
from rest_framework.exceptions import ValidationError


class InsureeViewSet(BaseFHIRView, MultiIdentifierRetrieverMixin,
                     MultiIdentifierUpdateMixin, viewsets.ModelViewSet):
    retrievers = [UUIDIdentifierModelRetriever, CHFIdentifierModelRetriever]
    serializer_class = PatientSerializer
    permission_classes = (FHIRApiInsureePermissions,)

    def list(self, request, *args, **kwargs):
        # Retrieve parameters from the request
        ref_date_str = request.GET.get('refDate')
        claim_date = request.GET.get('claimDateFrom')
        identifier = request.GET.get("identifier")

        # If an identifier is provided, retrieve the corresponding insuree
        if identifier:
            return self.retrieve(request, *args, **{**kwargs, 'identifier': identifier})
        else:
            # Filter queryset based on validity and order by validity_from
            queryset = self.get_queryset().filter(validity_to__isnull=True).order_by('validity_from')

            # Filter queryset based on refDate parameter
            if ref_date_str is not None:
                try:
                    ref_date = datetime.datetime.strptime(ref_date_str, "%Y-%m-%d").date()
                    queryset = queryset.filter(validity_from__gte=ref_date)
                except ValueError:
                    pass

            # Filter queryset based on claimDateFrom parameter
            if claim_date is not None:
                try:
                    claim_parse_date = datetime.datetime.strptime(claim_date, "%Y-%m-%d").date()
                except ValueError:
                    result = OperationOutcomeConverter.build_for_400_bad_request(
                        "claimDateFrom should be in dd-mm-yyyy format")
                    return Response(result.dict(), status.HTTP_400_BAD_REQUEST)
                # Filter insurees with claims in the specified range
                has_claim_in_range = Claim.objects.filter(date_claimed__gte=claim_parse_date).filter(
                    insuree_id=OuterRef("id")).values("id")
                queryset = queryset.annotate(has_claim_in_range=Exists(
                    has_claim_in_range)).filter(has_claim_in_range=True)

        # Serialize the queryset and return paginated response
        serializer = PatientSerializer(self.paginate_queryset(queryset), many=True)
        return self.get_paginated_response(serializer.data)

    def get_queryset(self):
        # Retrieve base queryset for Insuree model and apply related select queries
        queryset = Insuree.get_queryset(None, self.request.user).select_related(
            'gender').select_related('photo').select_related('family__location')

        # Apply additional filtering based on request parameters
        queryset = ValidityFromRequestParameterFilter(self.request).filter_queryset(queryset)

        # Filter queryset based on organization parameter
        organization_id = self.request.GET.get('organization_id')
        if organization_id:
            queryset = queryset.filter(uuid=organization_id)

        return queryset




class InsureeFilterView(BaseFHIRView, viewsets.ModelViewSet):
    queryset = Insuree.objects.all()
    serializer_class = PatientSerializer

    def list(self, request, *args, **kwargs):
        identifier = request.GET.get("identifier")

        if not identifier:
            return Response({'error': 'Identifier parameter is missing'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            instance = self.queryset.get(identifier=identifier)
        except Insuree.DoesNotExist:
            return Response({'error': 'Insuree not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)
