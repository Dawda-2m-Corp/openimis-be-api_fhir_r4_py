import json
from django.db.models.query import Q
from django.utils.translation import gettext as _
from fhir.resources.R4B.humanname import HumanName
from django.db.models import Model
from insuree.models import Insuree, InsureePolicy, Family, FamilyType, ConfirmationType
from policyholder.models import PolicyHolderInsuree, PolicyHolder, PolicyHolderUser
from policy.models import Policy
from location.models import Location
from api_fhir_r4.configurations import R4IdentifierConfig, GeneralConfiguration
from api_fhir_r4.converters import BaseFHIRConverter, ReferenceConverterMixin
from api_fhir_r4.converters.locationConverter import LocationConverter

from api_fhir_r4.mapping.groupMapping import GroupTypeMapping, ConfirmationTypeMapping
from fhir.resources.R4B.extension import Extension
from fhir.resources.R4B.group import Group, GroupMember

from api_fhir_r4.utils import DbManagerUtils
from api_fhir_r4.exceptions import FHIRException


class GroupConverterPolicyHolder(BaseFHIRConverter, ReferenceConverterMixin):

    @classmethod
    def to_fhir_obj(cls, imis_policy_holder: PolicyHolder, reference_type=ReferenceConverterMixin.UUID_REFERENCE_TYPE):
        # Create an empty dictionary to store FHIR policy holder data
        fhir_policy_holder = {}

        # Build the actual FHIR object using the imis_policy_holder data
        cls.build_fhir_actual(fhir_policy_holder, imis_policy_holder)
        cls.build_fhir_type(fhir_policy_holder, imis_policy_holder)

        # Convert the dictionary to a Group object
        fhir_policy_holder = Group(**fhir_policy_holder)

        # Build additional FHIR components
        cls.build_fhir_identifiers(fhir_policy_holder, imis_policy_holder)
        cls.build_fhir_quantity(fhir_policy_holder, imis_policy_holder)
        cls.build_fhir_name(fhir_policy_holder, imis_policy_holder)
        cls.build_fhir_member(fhir_policy_holder, imis_policy_holder, reference_type)

        return fhir_policy_holder

    @classmethod
    def to_imis_obj(cls, fhir_policy_holder: PolicyHolder, audit_user_id):
        # Initialize an empty list to collect errors
        errors = []

        # Convert the FHIR policy holder dictionary to a Group object
        fhir_policy_holder = Group(**fhir_policy_holder)

        # Create a new PolicyHolder object
        imis_policy_holder = PolicyHolder()

        # Set UUID to None for proper usage in service
        imis_policy_holder.uuid = None
        imis_policy_holder.audit_user_id = audit_user_id

        # Build members and extensions from the FHIR policy holder
        cls.build_members(imis_policy_holder, fhir_policy_holder, errors)
        # cls.build_imis_extentions(imis_policy_holder, fhir_policy_holder)

        # Check for any errors collected during the conversion process
        cls.check_errors(errors)

        return imis_policy_holder

    @classmethod
    def build_members(cls, imis_policy_holder, fhir_policy_holder, errors):
        # Implement the logic to build members here
        pass

    @classmethod
    def to_imis_fhir(cls, fhir_policy_holder_insuree):
        errors = []
        fhir_policy_holder_insuree = Group(**fhir_policy_holder_insuree)
        imis_policy_holder_insuree = PolicyHolderInsuree()
        cls.build_policy_holder_members(imis_policy_holder_insuree, fhir_policy_holder_insuree)
        cls.check_errors(errors)
        return imis_policy_holder_insuree

    @classmethod
    def build_fhir_actual(cls, fhir_policy_holder, imis_policy_holder):
        fhir_policy_holder['actual'] = True

    @classmethod
    def build_fhir_type(cls, fhir_family, imis_policy_holder):
        # according to the IMIS profile - always 'Person' value
        fhir_family['type'] = "Person"

    @classmethod
    def build_fhir_identifiers(cls, fhir_policy_holder, imis_policy_holder):
        identifiers = []
        cls.build_all_identifiers(identifiers, imis_policy_holder)
        fhir_policy_holder.identifier = identifiers

    @classmethod
    def get_reference_obj_id(cls, imis_policy_holder: PolicyHolder):
        return imis_policy_holder.id

    @classmethod
    def get_reference_obj_uuid(cls, imis_policy_holder: PolicyHolder):
        return imis_policy_holder.uuid

    @classmethod
    def get_reference_obj_code(cls, obj):
        return obj.code

    @classmethod
    def _build_policy_holder_identifier(cls, identifiers, imis_policy_holder):
        cls._validate_imis_identifier_code(imis_policy_holder)
        code = cls.build_fhir_identifier(
            imis_policy_holder.code,
            R4IdentifierConfig.get_fhir_identifier_type_system(),
            R4IdentifierConfig.get_fhir_generic_type_code()
        )
        identifiers.append(code)

    @classmethod
    def _validate_imis_identifier_code(cls, imis_policy_holder):
        if not imis_policy_holder.code:
            raise FHIRException(
                _('Policy %(policy_uuid)s without code') % {'policy_uuid': imis_policy_holder.uuid}
            )

    @classmethod
    def get_fhir_code_identifier_type(cls):
        return R4IdentifierConfig.get_fhir_generic_type_code()

    @classmethod
    def get_reference_obj_id(cls, imis_policy_holder):
        return imis_policy_holder.id

    @classmethod
    def get_fhir_resource_type(cls):
        return Group

    @classmethod
    def build_fhir_pk(cls, fhir_obj, resource, reference_type: str = None):
        if reference_type == ReferenceConverterMixin.CODE_REFERENCE_TYPE:
            fhir_obj.id = resource.code
        else:
            return super().build_fhir_pk(fhir_obj, resource, reference_type)

    @classmethod
    def get_imis_obj_by_fhir_reference(cls, reference, errors=None):
        return DbManagerUtils.get_object_or_none(
            PolicyHolder,
            **cls.get_database_query_id_parameteres_from_reference(reference))

    @classmethod
    def build_fhir_name(cls, fhir_policy_holder, imis_policy_holder):
        if imis_policy_holder is not None:
            fhir_policy_holder.name = imis_policy_holder.trade_name

    @classmethod
    def build_fhir_quantity(cls, fhir_policy_holder, imis_policy_holder):
        quantity = PolicyHolderInsuree.objects.filter(
            policy_holder__uuid=imis_policy_holder.uuid, is_deleted=False).count()
        fhir_policy_holder.quantity = quantity

    @classmethod
    def build_fhir_member(cls, fhir_policy_holder, imis_policy_holder, reference_type):
        fhir_policy_holder.member = cls.build_fhir_members(imis_policy_holder)

    @classmethod
    def build_fhir_members(cls, imis_policy_holder: PolicyHolder):
        policy_holder_insuree = PolicyHolderInsuree.objects.filter(policy_holder=imis_policy_holder, is_deleted=False)
        insures = [cls.create_group_members(insure_relation) for insure_relation in policy_holder_insuree]
        return insures

    @classmethod
    def create_group_members(cls, insure_relation):
        bundle_details = []

        policy_holder_insurees = PolicyHolderInsuree.objects.filter(insuree=insure_relation.insuree, is_deleted=False)

        # Loop through each related PolicyHolderInsuree instance to gather contribution plan bundles and calculation rules
        for policy_holder_insuree in policy_holder_insurees:
            contribution_plan_bundle = policy_holder_insuree.contribution_plan_bundle.code
            calculation_rule = policy_holder_insuree.json_ext.get(
                'calculation_rule') if policy_holder_insuree.json_ext else None
            # Create a dictionary for each contribution plan bundle and calculation rule pair
            bundle_detail = {
                "contribution_plan_bundle": str(contribution_plan_bundle),
                "calculation_rule": calculation_rule
            }

            bundle_details.append(bundle_detail)

        insuree_details = {
            "chf_id": insure_relation.insuree.chf_id,
            'insuree_bundle_detail': bundle_details
        }

        # Create a GroupMember instance
        group_member = GroupMember(
            entity={
                "reference": f"Patient/{insure_relation.insuree.uuid}",
                "type": "Patient",
                "display": str(insure_relation.insuree.last_name)
            }
        )

        # Create extensions for other details
        extensions = []
        for key, value in insuree_details.items():
            if key != "name":  # Exclude the name field from extensions
                extension_url = f"http://example.com/{key}"  # Replace with appropriate extension URL
                extension = Extension(
                    url=extension_url,
                    valueString=str(value)  # Convert value to JSON string
                )
                extensions.append(extension)

        # Add extensions to the GroupMember
        group_member.extension = extensions

        return group_member

    @classmethod
    def build_policy_holder_members(cls, imis_policy_holder_insuree, fhir_policy_holder_insuree):
        # Assuming the fhir_policy_holder_insuree is a FHIR Group object
        if fhir_policy_holder_insuree.member:
            imis_policy_holder_insuree.insurees = []
            for member in fhir_policy_holder_insuree.member:
                # Extract the necessary information from the FHIR member
                # Assuming reference format is "Patient/{uuid}"
                insuree_reference = member.entity.reference.split('/')[-1]
                # Retrieve the corresponding insuree object using the reference
                insuree = Insuree.objects.get(uuid=insuree_reference)
                # Create and append a PolicyHolderInsuree instance
                policy_holder_insuree = PolicyHolderInsuree(
                    insuree=insuree, policy_holder=imis_policy_holder_insuree.policy_holder)
                imis_policy_holder_insuree.insurees.append(policy_holder_insuree)
