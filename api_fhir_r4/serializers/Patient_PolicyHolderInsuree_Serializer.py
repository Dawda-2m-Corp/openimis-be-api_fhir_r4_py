import copy

from insuree.apps import InsureeConfig
from insuree.models import Insuree, Family

# from core.models import resolve_id_reference

from api_fhir_r4.converters.Patient_PolicyHolderInsuree_Converter import PatientPolicyHolderInsureeConverter
from api_fhir_r4.exceptions import FHIRException
from api_fhir_r4.serializers import BaseFHIRSerializer
from insuree.services import InsureeService


class PatientPolicyHolderInsureeSerializer(BaseFHIRSerializer):
    fhirConverter = PatientPolicyHolderInsureeConverter()
