from policyholder.models import PolicyHolder
from api_fhir_r4.converters import GroupConverterPolicyHolder
from api_fhir_r4.exceptions import FHIRException
from api_fhir_r4.serializers import BaseFHIRSerializer


class PolicyHolderGroupSerializer(BaseFHIRSerializer):

    fhirConverter = GroupConverterPolicyHolder()


    def to_internal_value(self, data):
        """
        Convert FHIR `Group` representation to a `PolicyHolder` instance.
        """
        audit_user_id = self.context['request'].user.id if 'request' in self.context else None
        policy_holder = self.fhirConverter.to_imis_obj(data, audit_user_id)
        return policy_holder

    def create(self, validated_data):
        """
        Create and return a new `PolicyHolder` instance, given the validated data.
        """
        policy_holder = self.to_internal_value(validated_data)
        policy_holder.save()
        return policy_holder

    def update(self, instance, validated_data):
        """
        Update and return an existing `PolicyHolder` instance, given the validated data.
        """
        policy_holder = self.to_internal_value(validated_data)
        # Update the instance with new values
        for attr, value in policy_holder.__dict__.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
