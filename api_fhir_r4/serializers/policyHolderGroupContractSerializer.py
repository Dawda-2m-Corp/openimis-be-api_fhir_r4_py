from api_fhir_r4.converters.policy_holder_group_contractConverter import PolicyHolderContractConverter
from api_fhir_r4.serializers import BaseFHIRSerializer
from policyholder.models import PolicyHolderUser, PolicyHolder
from contract.models import Contract
from rest_framework.exceptions import PermissionDenied
from rest_framework import serializers


class PolicyHolderGroupContractSerializer(BaseFHIRSerializer):
    fhirConverter = PolicyHolderContractConverter()


class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = '__all__'

    def create(self, validated_data):
        return super().create(validated_data)
