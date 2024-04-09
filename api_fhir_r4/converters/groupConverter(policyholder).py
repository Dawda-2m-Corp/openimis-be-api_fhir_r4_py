# from django.db.models.query import Q
# from django.utils.translation import gettext as _
# from fhir.resources.R4B.humanname import HumanName
# from django.db.models import Model
# from insuree.models import Insuree, InsureePolicy, Family, FamilyType, ConfirmationType
# from policyholder.models import PolicyHolderInsuree, PolicyHolder,PolicyHolderUser
# from policy.models import Policy
# from location.models import Location
# from api_fhir_r4.configurations import R4IdentifierConfig, GeneralConfiguration
# from api_fhir_r4.converters import BaseFHIRConverter, ReferenceConverterMixin
# from api_fhir_r4.converters.locationConverter import LocationConverter

# from api_fhir_r4.mapping.groupMapping import GroupTypeMapping, ConfirmationTypeMapping
# from fhir.resources.R4B.extension import Extension
# from fhir.resources.R4B.group import Group, GroupMember
# from api_fhir_r4.utils import DbManagerUtils
# from api_fhir_r4.exceptions import FHIRException


# class GroupConverter(BaseFHIRConverter, ReferenceConverterMixin):
    
#     @classmethod
#     def to_fhir_obj(cls, imis_policy_holder, reference_type=ReferenceConverterMixin.UUID_REFERENCE_TYPE):

#         fhir_policy_holder = {}

#         cls.build_fhir_actual(fhir_policy_holder,imis_policy_holder)
#         cls.build_fhir_type(fhir_policy_holder, imis_policy_holder)
#         fhir_policy_holder = Group(**fhir_policy_holder)
#         cls.build_fhir_extensions(fhir_policy_holder, imis_policy_holder, reference_type)
#         cls.build_fhir_identifiers(fhir_policy_holder, imis_policy_holder)
#         cls.build_fhir_pk(fhir_policy_holder, imis_policy_holder, reference_type=reference_type)
#         cls.build_fhir_active(fhir_policy_holder,imis_policy_holder)
#         cls.build_fhir_quantity(fhir_policy_holder, imis_policy_holder)
#         cls.build_fhir_name(fhir_policy_holder, imis_policy_holder)
#         cls.build_fhir_member(fhir_policy_holder, imis_policy_holder, reference_type)
#         return fhir_policy_holder

#     @classmethod
#     def to_imis_obj(cls, fhir_policy_holder):
        
#         errors = []
#         fhir_policy_holder = Group(**fhir_policy_holder)
#         imis_policy_holder = PolicyHolderInsuree()
#         imis_policy_holder.uuid  = None
#         cls.build_policy_holder_memebers(imis_policy_holder, fhir_policy_holder, errors)
#         cls.build_imis_extenstions(imis_policy_holder, fhir_policy_holder)
#         cls.check_errors(errors)
#         return imis_policy_holder
    

#     @classmethod
#     def get_reference_obj_id(cls, imis_policy_holder):
#         return imis_policy_holder.id
    
#     @classmethod
#     def get_fhir_resource_type(cls):
#         return PolicyHolderInsuree
    

#     @classmethod
#     def build_fhir_pk(cls, fhir_obj, resource, reference_type: str = None):
#         if reference_type == ReferenceConverterMixin.CODE_REFERENCE_TYPE:
#           fhir_obj.id = resource.policy_holder.code

#         else:

#           return super().build_fhir_pk(fhir_obj, resource, reference_type)
    
#     @classmethod
#     def get_imis_obj_by_fhir_reference(cls, reference, errors=None):
#         return DbManagerUtils.get_object_or_none(
#             PolicyHolderInsuree,
#             **cls.get_database_query_id_parameteres_from_reference(reference))
    
#     @classmethod
#     def get_human_names(cls, fhir_policy_holder, imis_policy_holder):
#         name = cls.build_fhir_names_for_person()
#         if type(fhir_policy_holder.trade_name) is not list:
#             fhir_policy_holder.trade_name = name
#         else:
#             fhir_policy_holder.trade_name.append(name)

#     @classmethod
#     def build_family_members(cls, imis_policy_holder, fhir_policy_holder, errors):
#         members = fhir_policy_holder.member
#         imis_policy_holder.members_family = []
#         if cls.valid_condition(members is None, _('Missing `member` attribute'), errors) \
#                 or cls.valid_condition(members is None, _('Missing member should not be empty'), errors):
#             return
        
#         for member in members:
#             cls._add_member_to_family(imis_policy_holder, member.entity,imis_policy_holder.members_family)


