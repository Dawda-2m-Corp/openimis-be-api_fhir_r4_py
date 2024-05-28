import core
from django.utils.translation import gettext as _
from location.models import Location
from product.models import Product
from fhir.resources.R4B.identifier import Identifier
from contribution_plan.models import ContributionPlanBundle, ContributionPlan, ContributionPlanBundleDetails
from api_fhir_r4.configurations import GeneralConfiguration, R4IdentifierConfig
from api_fhir_r4.converters import BaseFHIRConverter, ReferenceConverterMixin
from fhir.resources.R4B.extension import Extension
from api_fhir_r4.exceptions import FHIRException
from fhir.resources.R4B.money import Money
from fhir.resources.R4B.insuranceplan import InsurancePlan, InsurancePlanCoverage, InsurancePlanCoverageBenefit, InsurancePlanCoverageBenefitLimit, InsurancePlanPlan
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.quantity import Quantity
from api_fhir_r4.utils import DbManagerUtils, TimeUtils

class InsurancePlanContributionPlanBundleConverter(BaseFHIRConverter, ReferenceConverterMixin):

    @classmethod
    def to_fhir_obj(cls, imis_contribution_plan_bundle, reference_type=ReferenceConverterMixin.UUID_REFERENCE_TYPE):
        errors = []
        fhir_contribution_plan_bundle = InsurancePlan.construct()
        cls.build_fhir_identifiers(fhir_contribution_plan_bundle, imis_contribution_plan_bundle)
        cls.build_fhir_pk(fhir_contribution_plan_bundle, imis_contribution_plan_bundle.uuid)
        cls.build_fhir_name(fhir_contribution_plan_bundle, imis_contribution_plan_bundle)
        cls.build_fhir_type(fhir_contribution_plan_bundle, imis_contribution_plan_bundle)
        cls.build_fhir_status(fhir_contribution_plan_bundle, imis_contribution_plan_bundle)
        cls.build_fhir_period(fhir_contribution_plan_bundle, imis_contribution_plan_bundle)
        cls.build_fhir_plan(fhir_contribution_plan_bundle, imis_contribution_plan_bundle, reference_type)
        cls.build_fhir_extensions(fhir_contribution_plan_bundle, imis_contribution_plan_bundle)
        cls.check_errors(errors)
        return fhir_contribution_plan_bundle
    
    def to_imis_obj(cls, fhir_insurance_plan, audit_user_id):
        errors = []

        fhir_insurance_plan = InsurancePlan(**fhir_insurance_plan)
        imis_contibution_plan_bundle = ContributionPlanBundle()
        imis_contibution_plan_bundle.uuid =  None
        cls.build_imis_name(imis_contibution_plan_bundle, fhir_insurance_plan)
        cls.build_imis_identifiers(imis_contibution_plan_bundle, fhir_insurance_plan)
        cls.build_imis_period(imis_contibution_plan_bundle, fhir_insurance_plan)
        cls.check_errors(errors)
        return imis_contibution_plan_bundle



    @classmethod
    def get_reference_obj_id(cls, imis_contribution_plan_bundle ):
        return imis_contribution_plan_bundle.uuid

    @classmethod
    def get_fhir_resource_type(cls):
        return InsurancePlan

    @classmethod
    def get_imis_obj_by_fhir_reference(cls, reference, errors=None):
        return DbManagerUtils.get_object_or_none(
            ContributionPlanBundle,
            **cls.get_database_query_id_parameteres_from_reference(reference)
        )
    @classmethod
    def get_fhir_code_identifier_type(cls):
        return R4IdentifierConfig.get_fhir_generic_type_code()

    @classmethod
    def build_fhir_identifiers(cls, fhir_contribution_plan_bundle, imis_contribution_plan_bundle):
        identifiers = []
        cls.build_fhir_uuid_identifier(identifiers, imis_contribution_plan_bundle)
        cls.build_fhir_code_identifier(identifiers, imis_contribution_plan_bundle)
        fhir_contribution_plan_bundle.identifier = identifiers

    @classmethod
    def build_fhir_name(cls, fhir_contribution_plan_bundle, imis_contribution_plan_bundle):
        if imis_contribution_plan_bundle.name and imis_contribution_plan_bundle.name != '' or None:
            fhir_contribution_plan_bundle.name = imis_contribution_plan_bundle.name

    @classmethod
    def build_fhir_type(cls, fhir_contribution_plan_bundle, imis_contribution_plan_bundle):
        fhir_contribution_plan_bundle.type = [cls.__build_contribution_plan_type()]

    @classmethod
    def __build_contribution_plan_type(cls):
        type = cls.build_codeable_concept(
            code="medical",
            system="http://terminology.hl7.org/CodeSystem/insuranceplan-type|contribution-plan_bundle_type"
        )
        if len(type.coding) == 1:
            type.coding[0].display = _("Medical")
        return type

    @classmethod
    def build_fhir_status(cls, fhir_contribution_plan_bundle, imis_contribution_plan_bundle):
        from core import datetime
        now = datetime.datetime.now()
        status = "unknown"
        
        # Check if date_valid_from and date_valid_to are not None before comparison
        if imis_contribution_plan_bundle.date_valid_from and imis_contribution_plan_bundle.date_valid_to:
            if now >= imis_contribution_plan_bundle.date_valid_from and now <= imis_contribution_plan_bundle.date_valid_to:
                status = "active"
            elif now > imis_contribution_plan_bundle.date_valid_to:
                status = "inactive"
        elif imis_contribution_plan_bundle.date_valid_from:
            if now >= imis_contribution_plan_bundle.date_valid_from:
                status = "active"
        elif imis_contribution_plan_bundle.date_valid_to:
            if now <= imis_contribution_plan_bundle.date_valid_to:
                status = "active"
            else:
                status = "inactive"

        fhir_contribution_plan_bundle.status = status

    @classmethod
    def build_fhir_period(cls, fhir_contribution_plan_bundle, imis_contribution_plan_bundle):
        from core import datetime
        period = Period.construct()
        if imis_contribution_plan_bundle.date_valid_from:
            if isinstance(imis_contribution_plan_bundle.date_valid_from, datetime.datetime):
                period.start = imis_contribution_plan_bundle.date_valid_from.date().isoformat()
            else:
                period.start = imis_contribution_plan_bundle.date_valid_from.isoformat()
        if imis_contribution_plan_bundle.date_valid_to:
            if isinstance(imis_contribution_plan_bundle.date_valid_to, datetime.datetime):
                period.end = imis_contribution_plan_bundle.date_valid_to.date().isoformat()
            else:
                period.end = imis_contribution_plan_bundle.date_valid_to.isoformat()
        fhir_contribution_plan_bundle.period = period

    @classmethod
    def build_fhir_plan(cls, fhir_contribution_plan_bundle, imis_contribution_plan_bundle_detail, reference_type):
        pass
        fhir_contribution_plan_bundle.plan = cls.build_fhir_details(imis_contribution_plan_bundle_detail)

    @classmethod
    def build_fhir_details(cls, imis_contribution_plan_bundle_detail):
        pass
        contribution_plan_bundle_details = ContributionPlanBundleDetails.objects.filter(contribution_plan_bundle=imis_contribution_plan_bundle_detail, is_deleted=False)
        contribution_plan_bundles = [cls.create_contributional_plan(detail) for detail in contribution_plan_bundle_details]
        return contribution_plan_bundles

    @classmethod
    def create_contributional_plan(cls, contribution_plan_bundle_detail):
        plan = InsurancePlanPlan.construct()
    
        # Create the identifier with the UUID and code
        identifiers = cls.build_fhir_contributional_plan_identifier(contribution_plan_bundle_detail)
        plan.identifier = identifiers
        return plan
    
    @classmethod
    def build_fhir_contributional_plan_identifier(cls, imis_contribution_plan_bundle_detail):
        identifiers = []
        cls.build_fhir_uuid_identifier(identifiers, imis_contribution_plan_bundle_detail.contribution_plan)
        cls.build_fhir_code_identifier(identifiers, imis_contribution_plan_bundle_detail.contribution_plan)
        cls.add_name_extension_to_identifiers(identifiers, imis_contribution_plan_bundle_detail.contribution_plan)
        return identifiers
    
    @classmethod
    def add_name_extension_to_identifiers(cls, identifiers, contribution_plan):
        if hasattr(contribution_plan, 'name') and contribution_plan.name:
            name_extension = Extension.construct()
            name_extension.url = "http://example.org/fhir/StructureDefinition/contribution-plan-name"
            name_extension.valueString = contribution_plan.name
            for identifier in identifiers:
                if not cls.has_name_extension(identifier):
                    if not hasattr(identifier, 'extension') or identifier.extension is None:
                        identifier.extension = []
                    identifier.extension.append(name_extension)

    @classmethod
    def has_name_extension(cls, identifier):
        if hasattr(identifier, 'extension') and identifier.extension:
            return any(extension.url == "http://example.org/fhir/StructureDefinition/contribution-plan-name" for extension in identifier.extension)
        return False


    @classmethod
    def build_fhir_extensions(cls, fhir_contribution_plan_bundle, imis_contribution_plan_bundle):
        # Implement extensions if needed
        pass

    @classmethod
    def build_imis_name(cls, imis_contribution_plan_bundle, fhir_contribution_plan_bundle):
        if fhir_contribution_plan_bundle.name and fhir_contribution_plan_bundle.name != "":
            imis_contribution_plan_bundle.name = fhir_contribution_plan_bundle.name
    
    @classmethod
    def build_imis_identifiers(cls, imis_contribution_plan_bundle, fhir_contribution_plan_bundle):

        vlaue = cls.get_fhir_identifier_by_code(fhir_contribution_plan_bundle.identifier,
                                                R4IdentifierConfig.get_fhir_generic_type_code())
        cls._validate_fhir_contributional_plan_identifier_code(vlaue)
        imis_contribution_plan_bundle.code = vlaue

    @classmethod
    def _validate_fhir_contributional_plan_identifier_code(cls, fhir_insurance_plan_identifier_code):
        if not fhir_insurance_plan_identifier_code:
            raise FHIRException(
                _('InsurancePlan FHIR without code - this field is obligatory')
            )
    @classmethod
    def build_imis_period(cls, imis_contribution_plan_bundle, fhir_contribution_plan_bundle):
        if fhir_contribution_plan_bundle.period:
            period = fhir_contribution_plan_bundle.period
            if period.start:
                imis_contribution_plan_bundle.date_valid_from = TimeUtils.str_to_date(period.start)
            if period.end:
                imis_contribution_plan_bundle.date_valid_to = TimeUtils.str_to_date(period.end)
    