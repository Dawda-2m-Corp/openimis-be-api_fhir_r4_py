import core

from contract.models import ContractDetails, Contract as ContractModel
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
from rest_framework.exceptions import PermissionDenied
from core.models import User


class PolicyHolderContractConverter(BaseFHIRConverter, ReferenceConverterMixin):
    @classmethod
    def to_fhir_obj(cls, imis_organization: PolicyHolder, reference_type=ReferenceConverterMixin.UUID_REFERENCE_TYPE):
        fhir_contract = Contract.construct()

        cls.build_contract_identifier(fhir_contract, imis_organization)
        cls.build_contract_author(
            fhir_contract, imis_organization, reference_type)
        cls.build_contract_subject(
            fhir_contract, imis_organization, reference_type)
        contract_term = ContractTerm.construct()
        cls.build_contract_term_offer(
            contract_term, imis_organization, reference_type)
        fhir_contract.term = [contract_term]
        return fhir_contract

    @classmethod
    def to_imis_obj(cls, fhir_contract, policy_holder_user_id):
        errors = []
        policy_holder = PolicyHolder()
        fhir_contract = Contract(**fhir_contract)
        cls.build_imis_author(fhir_contract, policy_holder, errors)
        cls.build_imis_subject(fhir_contract, policy_holder, errors)
        cls.build_imis_policy_holder_insurees(
            fhir_contract, policy_holder, errors)

        if errors:
            raise FHIRException(errors)

    @classmethod
    def build_imis_policy_holder_insurees(cls, fhir_contract, imis_policy_holder, errors):
        if not fhir_contract.term:
            cls.valid_condition(True, _('Missing `term` attribute'), errors)
            return

        policy_holder_insurees = []

        for term in fhir_contract.term:
            if not term.asset:
                cls.valid_condition(
                    True, _('Missing `asset` attribute'), errors)
                continue

            for asset in term.asset:
                if not asset.typRefrence:
                    cls.valid_condition(
                        True, _('Missing `typRefrence` attribute'), errors)
                    continue

                for item in asset.typRefrence:
                    if item.reference is None:
                        continue

                    reference = item.reference.split("Patient/", 2)
                    try:
                        obj = PolicyHolderInsuree.objects.get(
                            uuid=reference[0])
                    except PolicyHolderInsuree.DoesNotExist:
                        cls.valid_condition(
                            True, _('Invalid `PolicyHolderInsuree` reference'), errors)
                        continue

                    if obj.policy_holder_id == imis_policy_holder.id:
                        policy_holder_insurees.append(obj.uuid)
                    else:
                        cls.valid_condition(
                            True, _('Invalid Context reference'), errors)

        imis_policy_holder.insuree = policy_holder_insurees if policy_holder_insurees else None

    @classmethod
    def build_imis_subject(cls, fhir_contract, imis_policy_holder, errors):
        from api_fhir_r4.converters.policyHolderOrganisationConverter import PolicyHolderOrganisationConverter
        if cls.valid_condition(not bool(fhir_contract.subject), _("Missing 'subject' attribute"), errors):
            return

        ref = fhir_contract.subject[0]
        reference_type = cls.get_resource_type_from_reference(ref)
        if reference_type == 'Group':
            policy_holder = PolicyHolderOrganisationConverter.get_imis_obj_by_fhir_reference(
                ref)
            if policy_holder is None:
                raise FHIRException(
                    F"Invalid group refrence '{ref}', no policy holder matching"
                    F"provided resource_id"
                )
            elif reference_type == 'Patient':
                patient = PatientConverter.get_imis_obj_by_fhir_reference(ref)
                policy_holder = cls._get_or_build_insuree_policy_holder(
                    patient)
            else:
                raise FHIRException(
                    "Contract subject reference is neither `Group` nor `Patient`")
        imis_policy_holder.policy_holder = policy_holder

    @classmethod
    def _get_or_build_insuree_policy_holder(cls, insuree: PolicyHolderInsuree):
        pass

    @classmethod
    def build_imis_author(cls, fhir_contract, imis_policy_holder, errors):
        if fhir_contract.author:
            reference = fhir_contract.author.reference.split(
                "Practitioner/", 2)
            imis_policy_holder.policy_holder_user = PolicyHolderUser.get(
                uuid=reference[1])
        else:
            cls.valid_condition(not fhir_contract.author, _(
                "Missing 'subject' attribute"), errors)

    @classmethod
    def build_contract_term_offer(cls, contract_term, imis_organization, reference_type):
        offer = ContractTermOffer.construct()
        insurees = []

        policy_holder_id = imis_organization.policy_holder_id
        try:
            contract_pk = ContractModel.objects.get(
                policy_holder=policy_holder_id)
        except ContractModel.DoesNotExist:
            raise ValueError(
                "Contract not found for the given policy holder ID")

        contract_details = ContractDetails.objects.filter(contract=contract_pk)
        if contract_details.exists():
            for contract_detail in contract_details:
                offer_reference = cls.build_fhir_insuree_resource_refrence(
                    contract_detail.insuree, "Patient", reference_type=reference_type
                )
                insurees.append(offer_reference)

            offer_party = ContractTermOfferParty.construct()
            offer_party.role = cls.build_codeable_concept(
                code="beneficiary", system=reference_type)
            offer_party.reference = insurees

            offer.party = [offer_party]
            contract_term.offer = offer
        else:
            raise ValueError(
                "No contract details found for the given contract")

    @classmethod
    def build_contract_subject(cls, fhir_contract, imis_organization, reference_type):
        policy_holder = imis_organization.policy_holder_id
        policy_holder_user = PolicyHolderUser.objects.filter(
            policy_holder=policy_holder, is_deleted=False).first()

        if not policy_holder_user:
            raise ValueError(
                "No active PolicyHolderUser found for the given PolicyHolder")

        policy_holder_instance = PolicyHolder.objects.get(
            policyholderuser=policy_holder_user)

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
        user_author = imis_organization.user_created
        user = User.objects.filter(
            pk=user_author.pk)

        if not user:
            raise ValueError(
                "No active PolicyHolderUser found for the given PolicyHolder")

        # Build the FHIR resource reference for the author
        author_ref = cls.build_fhir_author_resource_reference(
            user, "Practitioner", reference_type=reference_type)

        fhir_contract.author = author_ref

    @classmethod
    def build_fhir_author_resource_reference(cls, resource, resource_type, reference_type=None):
        return {
            "reference": f"{resource_type}/{resource.i_user.pk}",
            "display": resource.username,
            "type": reference_type,
            "identifier": {
                "system": cls.get_fhir_code_identifier_type(),
                "value": str(resource.i_user.uuid)
            }
        }

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
            "display": str(resource.last_name),
            "type": reference_type,
            "identifier": {
                "system": cls.get_fhir_code_identifier_type(),
                "value": str(resource.chf_id),
            }
        }

    @classmethod
    def get_fhir_code_identifier_type(cls):
        return f"{GeneralConfiguration.get_system_base_url()}CodeSystem/"
