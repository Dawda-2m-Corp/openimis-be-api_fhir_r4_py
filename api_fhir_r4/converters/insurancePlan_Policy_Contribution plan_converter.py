import core

from django.utils.translation import gettext as _
from location.models import Location
from product.models import Product
from contribution_plan.models import ContributionPlanBundle, ContributionPlan
from api_fhir_r4.configurations import GeneralConfiguration, R4IdentifierConfig
from api_fhir_r4.converters import BaseFHIRConverter, ReferenceConverterMixin
from api_fhir_r4.converters.locationConverter import LocationConverter
from fhir.resources.R4B.extension import Extension
from fhir.resources.R4B.money import Money
from fhir.resources.R4B.insuranceplan import InsurancePlan, InsurancePlanCoverage, \
    InsurancePlanCoverageBenefit, InsurancePlanCoverageBenefitLimit, \
    InsurancePlanPlan, InsurancePlanPlanGeneralCost
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.quantity import Quantity
from api_fhir_r4.exceptions import FHIRException
from api_fhir_r4.utils import DbManagerUtils, TimeUtils


class InsurancePlanConverter(BaseFHIRConverter, ReferenceConverterMixin):

    @classmethod
    def to_fhir_obj(cls, imis_contribution_plan_bundle, reference_type=ReferenceConverterMixin.UUID_REFERENCE_TYPE):
        fhir_insurance_plan = InsurancePlan.construct()
        imis_contribution_plan = ContributionPlan
        # then create fhir object as usual
        cls.build_fhir_identifiers(fhir_insurance_plan, imis_contribution_plan_bundle)
        cls.build_fhir_pk(fhir_insurance_plan, imis_contribution_plan_bundle.uuid)
        cls.build_fhir_name(fhir_insurance_plan, imis_contribution_plan_bundle)
        cls.build_fhir_type(fhir_insurance_plan, imis_contribution_plan_bundle)
        cls.build_fhir_status(fhir_insurance_plan, imis_contribution_plan_bundle)
        cls.build_fhir_period(fhir_insurance_plan, imis_contribution_plan_bundle)
        cls.build_fhir_plan(fhir_insurance_plan, imis_contribution_plan)
        cls.build_fhir_extentions(fhir_insurance_plan, imis_contribution_plan_bundle)
        return fhir_insurance_plan