from django.db.models.query import Q
from django.utils.translation import gettext as _
from fhir.resources.R4B.humanname import HumanName
from django.db.models import Model
from insuree.models import Insuree, InsureePolicy, Family, FamilyType, ConfirmationType
from policyholder.models import PolicyHolderInsuree, PolicyHolder,PolicyHolderUser
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
    def to_fhir_obj(cls, imis_policy_holder:PolicyHolder, reference_type=ReferenceConverterMixin.UUID_REFERENCE_TYPE):

        fhir_policy_holder = {}
        cls.build_fhir_actual(fhir_policy_holder,imis_policy_holder)
        cls.build_fhir_type(fhir_policy_holder, imis_policy_holder)
        fhir_policy_holder = Group(**fhir_policy_holder)
        # cls.build_fhir_extensions(fhir_policy_holder, imis_policy_holder, reference_type)
        cls.build_fhir_identifiers(fhir_policy_holder, imis_policy_holder)
        # cls.build_fhir_pk(fhir_policy_holder, imis_policy_holder, reference_type=reference_type)
        cls.build_fhir_quantity(fhir_policy_holder, imis_policy_holder)
        cls.build_fhir_name(fhir_policy_holder, imis_policy_holder)
        cls.build_fhir_member(fhir_policy_holder, imis_policy_holder, reference_type)
        return fhir_policy_holder

   
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
        cls.build_all_identifiers( identifiers, imis_policy_holder)
        fhir_policy_holder.identifier = identifiers
    
    
    @classmethod
    def get_reference_obj_id(cls, imis_policy_holder:PolicyHolder):
        return imis_policy_holder.id

    @classmethod
    def get_reference_obj_uuid(cls, imis_policy_holder:PolicyHolder):
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
                _('Policy %(imis_policy_code)s without code') % {'family_uuid': imis_policy_holder.uuid}
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

    # @classmethod
    # def build_fhir_pk(cls, fhir_obj, resource, reference_type: str = None):
    #     if reference_type == ReferenceConverterMixin.CODE_REFERENCE_TYPE:
    #       fhir_obj.id = resource.code
    #     else:
    #       return super().build_fhir_pk(fhir_obj, resource, reference_type)
    
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
    def build_fhir_quantity(cls,fhir_policy_holder, imis_policy_holder):
        quantity = PolicyHolderInsuree.objects.filter(policy_holder__uuid=imis_policy_holder.uuid, is_deleted=True).count()
        fhir_policy_holder.quantity = quantity

    @classmethod
    def build_fhir_member(cls, fhir_policy_holder, imis_policy_holder, reference_type):
        fhir_policy_holder.member = cls.build_fhir_members(imis_policy_holder) 

    @classmethod
    def build_fhir_members(cls,imis_policy_holder:PolicyHolder):
        policy_holder_insuree = PolicyHolderInsuree.objects.filter(policy_holder=imis_policy_holder, is_deleted=False)
        insures = [cls.create_group_members(insure_relation) for insure_relation in policy_holder_insuree ]
        return insures


    @classmethod
    def create_group_members(cls,insure_relation):
        from api_fhir_r4.converters import PatientConverter
        reference = PatientConverter.build_fhir_resource_reference(
            insure_relation,
            type= 'Patient',
            display=str({
                "name":str(insure_relation.insuree), 
                'chf_id':str(insure_relation.insuree.chf_id),  
                'address':insure_relation.insuree.current_address,  
                'email':str(insure_relation.insuree.email)})
        )
        return GroupMember(entity=reference)

