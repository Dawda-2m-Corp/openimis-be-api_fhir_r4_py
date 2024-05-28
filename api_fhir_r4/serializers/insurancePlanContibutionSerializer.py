import copy

from product.models import Product
from api_fhir_r4.converters import InsurancePlanContributionPlanBundleConverter
from api_fhir_r4.exceptions import FHIRException
from api_fhir_r4.serializers import BaseFHIRSerializer


class InsurancePlanContributionSerializer(BaseFHIRSerializer):
    fhirConverter = InsurancePlanContributionPlanBundleConverter()