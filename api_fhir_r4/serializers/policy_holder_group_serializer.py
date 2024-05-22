from policyholder.models import PolicyHolder
from api_fhir_r4.converters import GroupConverterPolicyHolder
from api_fhir_r4.exceptions import FHIRException
from api_fhir_r4.serializers import BaseFHIRSerializer


class PolicyHolderGroupSerializer(BaseFHIRSerializer):

    fhirConverter = GroupConverterPolicyHolder()
