import core

from django.db.models import Q
from django.utils.translation import gettext as _
from api_fhir_r4.configurations import GeneralConfiguration, R4CoverageConfig
from api_fhir_r4.converters import BaseFHIRConverter, ReferenceConverterMixin
from api_fhir_r4.converters.patientConverter import PatientConverter
from api_fhir_r4.exceptions import FHIRException
from api_fhir_r4.mapping.contractMapping import PayTypeMapping, ContractStatus, \
    ContractState
from fhir.resources.R4B.contract import Contract, ContractTermAssetValuedItem, \
    ContractTerm, ContractTermAsset, ContractTermOffer, ContractTermOfferParty
from fhir.resources.R4B.extension import Extension
from fhir.resources.R4B.money import Money
from fhir.resources.R4B.period import Period

from product.models import Product
from insuree.models import Insuree, InsureePolicy
from insuree.models import Family
from contribution.models import Premium
from api_fhir_r4.utils import DbManagerUtils, TimeUtils
from policyholder.models import PolicyHolder, PolicyHolderUser, PolicyHolderInsuree


class PolicyHolderContractConverter(BaseFHIRConverter, ReferenceConverterMixin):
    @classmethod
    def to_fhir_obj(cls, imis_organization: PolicyHolder, reference_type=ReferenceConverterMixin.UUID_REFERENCE_TYPE):
        fhir_contract = Contract.construct()

        cls.build_contract_identifier(fhir_contract, imis_organization)
        cls.build_contract_author(fhir_contract, imis_organization, reference_type)
        cls.build_contract_subject(fhir_contract, imis_organization, reference_type)
        contract_term = ContractTerm.construct()
        cls.build_contract_term_offer(contract_term, imis_organization, reference_type)
        fhir_contract.term = [contract_term]
        return fhir_contract

    @classmethod
    def to_imis_obj(cls, fhir_contract, policy_holder_user_id):
        errors = []
        fhir_contract = Contract(**fhir_contract)
        imis_policy_holder = PolicyHolder()
        imis_policy_holder = policy_holder_user_id
        cls.build_imis_author(fhir_contract, imis_policy_holder, errors)
        cls.build_imis_subject(fhir_contract, imis_policy_holder, errors)
        cls.build_imis_policy_holder_insurees(fhir_contract, imis_policy_holder, errors)

    @classmethod
    def build_imis_policy_holder_insurees(cls, fhir_contract, imis_policy_holder, errors):
        if fhir_contract.term:
            policy_holder_insuree = []
            for term in fhir_contract.term:
                if term.asset:
                    for asset in term.asset:
                        if asset.typRefrence:
                            for item in asset.typRefrence:
                                if item.reference is not None:
                                    reference = item.reference.split("Patient/", 2)
                                    obj = PolicyHolderInsuree.objects.get(uuid=reference[0])
                                    if imis_policy_holder.policy_holder_id is not None:
                                        pass

    @classmethod
    def build_imis_subject(cls, fhir_contract, imis_policy_holder, errors):
        from api_fhir_r4.converters.policyHolderOrganisationConverter import PolicyHolderOrganisationConverter
        if cls.valid_condition(not bool(fhir_contract.subject), _("Missing 'subject' attribute"), errors):
            return

        ref = fhir_contract.subject[0]
        reference_type = cls.get_resource_type_from_reference(ref)
        if reference_type == 'Group':
            policy_holder = PolicyHolderOrganisationConverter.get_imis_obj_by_fhir_reference(ref)
            if policy_holder is None:
                raise FHIRException(
                    F"Invalid group refrence '{ref}', no policy holder matching"
                    F"provided resource_id"
                )
            elif reference_type == 'Patient':
                patient = PatientConverter.get_imis_obj_by_fhir_reference(ref)
                policy_holder = cls._get_or_build_insuree_policy_holder(patient)
            else:
                raise FHIRException("Contract subject reference is neither `Group` nor `Patient`")
        imis_policy_holder.policy_holder = policy_holder


    @classmethod
    def _get_or_build_insuree_policy_holder(cls, insuree: PolicyHolderInsuree):
        pass



    @classmethod
    def build_imis_author(cls, fhir_contract, imis_policy_holder, errors):
        if fhir_contract.author:
            reference = fhir_contract.author.reference.split("Practitioner/", 2)
            imis_policy_holder.policy_holder_user = PolicyHolderUser.get(uuid=reference[1])
        else:
            cls.valid_condition(not fhir_contract.author, _("Missing 'subject' attribute"), errors)


    @classmethod
    def build_contract_term_offer(cls, contract_term, imis_organization, reference_type):
        offer = ContractTermOffer.construct()
        insurees = []

        policy_holder_id = imis_organization.policy_holder_id

        policy_holder_user = PolicyHolderUser.objects.filter(policy_holder=policy_holder_id, is_deleted=False).first()

        if not policy_holder_user:
            raise ValueError("No active PolicyHolderUser found for the given PolicyHolder")

        policy_holder_insurees = PolicyHolderInsuree.objects.filter(policy_holder=policy_holder_id)

        if not policy_holder_insurees.exists():
            raise ValueError("No insurees found for the given PolicyHolder")

        for policy_holder_insuree in policy_holder_insurees:

            offer_reference = cls.build_fhir_insuree_resource_refrence(
                policy_holder_insuree.insuree, "Patient", reference_type=reference_type
            )
            insurees.append(offer_reference)

        offer_party = ContractTermOfferParty.construct()
        offer_party.role = cls.build_codeable_concept(code="beneficiary", system=reference_type)
        offer_party.reference = insurees

        offer.party = [offer_party]


        contract_term.offer = offer




    @classmethod
    def build_contract_subject(cls, fhir_contract, imis_organization, reference_type):
        policy_holder = imis_organization.policy_holder_id
        policy_holder_user = PolicyHolderUser.objects.filter(policy_holder=policy_holder, is_deleted=False).first()

        if not policy_holder_user:
            raise ValueError("No active PolicyHolderUser found for the given PolicyHolder")

        policy_holder_instance = PolicyHolder.objects.get(policyholderuser=policy_holder_user)



        subject = cls.build_fhir_subject_resource_reference(
            policy_holder_instance, "Group", reference_type=reference_type
        )

        fhir_contract.subject = [subject]



    @classmethod
    def build_contract_identifier(cls, fhir_contract, imis_organization):
        identifiers = []
        cls.build_all_identifiers(identifiers, imis_organization)
        fhir_contract.identifier = identifiers
        return fhir_contract

    @classmethod
    def build_contract_author(cls, fhir_contract, imis_organization, reference_type):
        policy_holder = imis_organization.policy_holder_id
        policy_holder_user = PolicyHolderUser.objects.filter(policy_holder=policy_holder, is_deleted=False).first()

        if not policy_holder_user:
            raise ValueError("No active PolicyHolderUser found for the given PolicyHolder")

        # Build the FHIR resource reference for the author
        author_ref = cls.build_fhir_resource_reference(
            policy_holder_user.user, "Practitioner", reference_type=reference_type)

        fhir_contract.author = author_ref

    @classmethod
    def build_fhir_resource_reference(cls, resource, resource_type, reference_type=None):
        return {
            "reference": f"{resource_type}/{resource.pk}",
            "display": resource.username if hasattr(resource, 'username') else str(resource),
            "type": reference_type,
            "identifier": {
                "system": cls.get_fhir_code_identifier_type(),
                "value": str(resource.uuid)
            }
        }

    @classmethod
    def build_fhir_subject_resource_reference(cls, resource, resource_type, reference_type=None):
        return {
            "reference": f"{resource_type}/{resource.pk}",
            "display": resource.trade_name,
            "type": reference_type,
            "identifier": {
                "system": cls.get_fhir_code_identifier_type(),
                "value": str(resource.uuid)
            }
        }

    @classmethod
    def build_fhir_insuree_resource_refrence(cls, resource, resource_type, reference_type=None):
        return {
            "reference": f"{resource_type}/{resource.uuid}",
            "display": resource.username if hasattr(resource, 'username') else str(resource),
            "type": reference_type,
            "identifier": {
                "system": cls.get_fhir_code_identifier_type(),
                "value": str(resource.uuid)
            }
        }

    @classmethod
    def get_fhir_code_identifier_type(cls):
        return f"{GeneralConfiguration.get_system_base_url()}CodeSystem/"
