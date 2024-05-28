from api_fhir_r4.converters.policy_holder_group_contractConverter import PolicyHolderContractConverter
from api_fhir_r4.serializers import BaseFHIRSerializer


class PolicyHolderGroupContractSerializer(BaseFHIRSerializer):
    fhirConverter = PolicyHolderContractConverter()
