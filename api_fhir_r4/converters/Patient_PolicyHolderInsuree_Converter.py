import json
import urllib
from urllib.parse import urlparse

from django.utils.translation import gettext as _
from fhir.resources.R4B.address import Address

from insuree.models import Insuree, Gender, Education, Profession, Family, \
    InsureePhoto, Relation, IdentificationType
from location.models import Location, HealthFacility
from api_fhir_r4.configurations import R4IdentifierConfig, GeneralConfiguration, R4MaritalConfig
from api_fhir_r4.converters import BaseFHIRConverter, PersonConverterMixin, ReferenceConverterMixin
from api_fhir_r4.converters.groupConverter import GroupConverter
from api_fhir_r4.converters.locationConverter import LocationConverter
from api_fhir_r4.mapping.patientMapping import RelationshipMapping, EducationLevelMapping, \
    PatientProfessionMapping, MaritalStatusMapping, PatientCategoryMapping
from api_fhir_r4.models.imisModelEnums import ImisMaritalStatus
from fhir.resources.R4B.patient import Patient, PatientContact
from fhir.resources.R4B.extension import Extension
from fhir.resources.R4B.attachment import Attachment
from api_fhir_r4.exceptions import FHIRException
from api_fhir_r4.utils import TimeUtils, DbManagerUtils
from policyholder.models import PolicyHolder, PolicyHolderInsuree, PolicyHolderUser


class PatientPolicyHolderInsureeConverter(BaseFHIRConverter, PersonConverterMixin, ReferenceConverterMixin):

    @classmethod
    def to_fhir_obj(cls, imis_policy_holder_insuree, reference_type=ReferenceConverterMixin.UUID_REFERENCE_TYPE):
        fhir_patient = Patient.construct()
        cls.build_fhir_identifiers(fhir_patient, imis_policy_holder_insuree)
        cls.build_human_names(fhir_patient, imis_policy_holder_insuree)
        cls.build_fhir_pk(
            fhir_patient, imis_policy_holder_insuree, reference_type)
        cls.build_fhir_extensions(
            fhir_patient, imis_policy_holder_insuree, reference_type)
        cls.build_fhir_marital_status(fhir_patient, imis_policy_holder_insuree)
        cls.build_fhir_gender(fhir_patient, imis_policy_holder_insuree)
        cls.build_fhir_addresses(
            fhir_patient, imis_policy_holder_insuree, reference_type)
        cls.build_fhir_photo(fhir_patient, imis_policy_holder_insuree)
        return fhir_patient

    @classmethod
    def build_fhir_photo(cls, fhir_patient, imis_policy_holder_insuree):
        if imis_policy_holder_insuree.photo and imis_policy_holder_insuree.photo.folder and imis_policy_holder_insuree.photo.filename:
            # HOST is taken from global variable used in the docker initialization
            # If URL root is not explicitly given in the settings 'localhost' is used
            # (if value is empty validation exception is raised).
            abs_url = GeneralConfiguration.get_host_domain().split(
                'http://')[1] or 'localhost'
            domain = abs_url
            photo_uri = cls.__build_photo_uri(imis_policy_holder_insuree)
            photo = Attachment.construct()
            parsed = urllib.parse.urlunparse(
                ('http', domain, photo_uri, None, None, None))
            photo.url = parsed
            photo.creation = imis_policy_holder_insuree.photo.date.isoformat()
            photo.contentType = imis_policy_holder_insuree.photo.filename[imis_policy_holder_insuree.photo.filename.rfind(
                '.') + 1:]
            photo.title = imis_policy_holder_insuree.photo.filename
            if type(fhir_patient.photo) is not list:
                fhir_patient.photo = [photo]
            else:
                fhir_patient.photo.append(photo)

    @classmethod
    def __build_photo_uri(cls, imis_policy_holder_insuree):
        photo_folder = imis_policy_holder_insuree.photo.folder.replace(
            "\\", "/")
        photo_full_path = F"{photo_folder}/{imis_policy_holder_insuree.photo.filename}"
        path = f'/photo/{photo_full_path}'
        return path

    @classmethod
    def build_imis_photo(cls, imis_insuree, fhir_patient, errors):
        if fhir_patient.photo and len(fhir_patient.photo) > 0:
            cls._validate_fhir_photo(fhir_patient)
            if fhir_patient.photo[0].data:
                photo = fhir_patient.photo[0].data
                date = fhir_patient.photo[0].creation
                obj, created = \
                    InsureePhoto.objects.get_or_create(
                        chf_id=imis_insuree.chf_id,
                        defaults={
                            "photo": photo,
                            "date": date,
                            "audit_user_id": -1,
                            "officer_id": 3
                        }
                    )
                imis_insuree.photo_id = obj.id

    @classmethod
    def _validate_fhir_photo(cls, fhir_patient):
        if not fhir_patient.photo or len(fhir_patient.photo) == 0:
            raise FHIRException(
                _('FHIR Patient without photo data.')
            )
        else:
            photo = fhir_patient.photo[0]
            if not photo.title or not photo.creation or not photo.contentType:
                raise FHIRException(
                    _('FHIR Patient misses one of required fields:  contentType, title, creation')
                )

    @classmethod
    def build_fhir_addresses(cls, fhir_patient, imis_policy_holder_insuree, reference_type):
        addresses = []
        if imis_policy_holder_insuree.current_village:
            insuree_address = cls._build_insuree_address(
                imis_policy_holder_insuree, reference_type)
            addresses.append(insuree_address)
        elif imis_policy_holder_insuree.family and imis_policy_holder_insuree.family.location:
            family_address = cls._build_insuree_family_address(
                imis_policy_holder_insuree.family, reference_type)
            addresses.append(family_address)
        fhir_patient.address = addresses
        cls._validate_fhir_address_details(fhir_patient.address)

    @classmethod
    def _build_insuree_address(cls, imis_insuree, reference_type):
        return cls.__build_address_of_use(
            address_location=imis_insuree.current_village,
            use='temp',
            location_text=imis_insuree.current_address,
            reference_type=reference_type
        )

    @classmethod
    def _build_insuree_family_address(cls, imis_insuree_family: Family, reference_type):
        return cls.__build_address_of_use(
            address_location=imis_insuree_family.location,
            use='home',
            location_text=imis_insuree_family.address,
            reference_type=reference_type
        )

    @classmethod
    def __build_address_of_use(cls, address_location: Location, use: str, location_text: str, reference_type):
        if address_location is None:
            raise ValueError("Address location is None")
        base_address = cls.__build_base_physical_address(
            address_location, reference_type)
        base_address.use = use
        if location_text:
            base_address.text = location_text
        return base_address

    @classmethod
    def build_fhir_gender(cls, fhir_patient, imis_policy_holder_insuree):
        if imis_policy_holder_insuree.gender:
            code = imis_policy_holder_insuree.gender.code
            if code == GeneralConfiguration.get_male_gender_code():
                fhir_patient.gender = "male"
            elif code == GeneralConfiguration.get_female_gender_code():
                fhir_patient.gender = "female"
            elif code == GeneralConfiguration.get_other_gender_code():
                fhir_patient.gender = "other"
        else:
            fhir_patient.gender = "unknown"

    @classmethod
    def __build_base_physical_address(cls, imis_village_location, reference_type) -> Address:
        if imis_village_location is None:
            raise ValueError("Village location is None")
        return Address(**{
            "type": "physical",
            "state": cls.__state_name_from_physical_location(imis_village_location),
            "district": cls.__district_name_from_physical_location(imis_village_location),
            "city": cls.__village_name_from_physical_location(imis_village_location),
            "extension": [
                cls.__build_municipality_extension(imis_village_location),
                cls.__build_location_reference_extension(
                    imis_village_location, reference_type)
            ]
        })

    @classmethod
    def __build_location_reference_extension(cls, insuree_family_location, reference_type):
        if insuree_family_location is None:
            raise ValueError("Insuree family location is None")
        extension = Extension.construct()
        extension.url = f"{GeneralConfiguration.get_system_base_url()}StructureDefinition/address-location-reference"
        extension.valueReference = LocationConverter.build_fhir_resource_reference(
            insuree_family_location, 'Location', reference_type=reference_type)
        return extension

    @classmethod
    def __build_municipality_extension(cls, insuree_family_location):
        if insuree_family_location is None:
            raise ValueError("Insuree family location is None")
        extension = Extension.construct()
        extension.url = f"{GeneralConfiguration.get_system_base_url()}StructureDefinition/address-municipality"
        extension.valueString = cls.__municipality_from_family_location(
            insuree_family_location)
        return extension

    @classmethod
    def __state_name_from_physical_location(cls, insuree_family_location):
        if insuree_family_location and insuree_family_location.parent and insuree_family_location.parent.parent and insuree_family_location.parent.parent.parent:
            return insuree_family_location.parent.parent.parent.name or str(None)
        return str(None)

    @classmethod
    def __district_name_from_physical_location(cls, insuree_family_location):
        if insuree_family_location and insuree_family_location.parent and insuree_family_location.parent.parent:
            return insuree_family_location.parent.parent.name or str(None)
        return str(None)

    @classmethod
    def __municipality_from_family_location(cls, insuree_family_location):
        if insuree_family_location and insuree_family_location.parent:
            return insuree_family_location.parent.name or str(None)
        return str(None)

    @classmethod
    def __village_name_from_physical_location(cls, insuree_family_location):
        if insuree_family_location:
            return insuree_family_location.name or str(None)
        return str(None)

    @classmethod
    def build_human_names(cls, fhir_patient, imis_policy_holder_insuree):
        name = cls.build_fhir_names_for_person(imis_policy_holder_insuree)
        if fhir_patient.name:
            if type(fhir_patient.name) is not list:
                fhir_patient.name = [name] or str(None)
            else:
                fhir_patient.name.append(name)
        else:
            fhir_patient.name = [name]

    @classmethod
    def build_fhir_extensions(cls, fhir_patient, imis_policy_holder_insuree, reference_type):
        extensions = []

        # Build patient-group-reference extension
        group_extension = cls.__build_patient_group_reference_extension(
            imis_policy_holder_insuree, reference_type)
        if group_extension:
            extensions.append(group_extension)

        chf_id_extension = cls.__build_patient_chf_id_reference_extension(
            imis_policy_holder_insuree, reference_type)
        if chf_id_extension:
            extensions.append(chf_id_extension)

        marital_extension = cls.__build_patient_marital_reference_extension(
            imis_policy_holder_insuree, reference_type)
        if marital_extension:
            extensions.append(marital_extension)

        # Add other extensions as needed
        # For example, an extension for an attribute in imis_policy_holder_insuree
        # other_extension = cls.__build_other_extension(imis_policy_holder_insuree)
        # if other_extension:
        #     extensions.append(other_extension)

        fhir_patient.extension = extensions

    @classmethod
    def __build_patient_marital_reference_extension(cls, imis_policy_holder_insuree, reference_type):

        extension = Extension.construct()
        extension.url = f"{GeneralConfiguration.get_system_base_url()}StructureDefinition/chf-if-reference"
        extension.valueReference = cls.build_fhir_marital_resource_reference(
            imis_policy_holder_insuree, 'Marital Status', reference_type=reference_type)

        return extension

    @classmethod
    def build_fhir_marital_resource_reference(cls, resource, resource_type, reference_type=None):
        return {
            "reference": f"{resource_type}/{resource.marital}",
            "display": str(resource.marital),
            "type": "chf_id_reference",
            "identifier": {
                "system": cls.get_fhir_code_identifier_type(),
                "value": str(resource)
            }
        }

    @classmethod
    def __build_patient_chf_id_reference_extension(cls, imis_policy_holder_insuree, reference_type):

        extension = Extension.construct()
        extension.url = f"{GeneralConfiguration.get_system_base_url()}StructureDefinition/chf-if-reference"
        extension.valueReference = cls.build_fhir_chfid_resource_reference(
            imis_policy_holder_insuree, 'CHF_ID', reference_type=reference_type)

        return extension

    @classmethod
    def build_fhir_chfid_resource_reference(cls, resource, resource_type, reference_type=None):
        return {
            "reference": f"{resource_type}/{resource.chf_id}",
            "display": str(resource.chf_id),
            "type": "chf_id_reference",
            "identifier": {
                "system": cls.get_fhir_code_identifier_type(),
                "value": str(resource)
            }
        }

    @classmethod
    def __build_patient_group_reference_extension(cls, imis_policy_holder_insuree, reference_type):
        policy_holder_insuree = PolicyHolderInsuree.objects.filter(
            insuree=imis_policy_holder_insuree).first()
        if not policy_holder_insuree:
            return None

        policy_holder = PolicyHolder.objects.filter(
            policyholderinsuree=policy_holder_insuree).first()
        if not policy_holder:
            return None

        extension = Extension.construct()
        extension.url = f"{GeneralConfiguration.get_system_base_url()}StructureDefinition/patient-group-reference"
        extension.valueReference = cls.build_fhir_group_resource_reference(
            policy_holder, 'GroupOrganisation', reference_type=reference_type)

        return extension

    @classmethod
    def build_fhir_extentions(cls, fhir_patient, imis_policy_holder_insuree, reference_type):
        fhir_patient.extension = []

        def build_extension(fhir_patient, imis_policy_holder_insuree, value):
            extension = Extension.construct()
            if value == "head":
                extension.url = f"{GeneralConfiguration.get_system_base_url()}StructureDefinition/patient-is-head"
                extension.valueBoolean = imis_policy_holder_insuree.head

            elif value == "education.education":
                extension.url = f"{GeneralConfiguration.get_system_base_url()}StructureDefinition/patient-education-level"
                if hasattr(imis_policy_holder_insuree, "education") and imis_policy_holder_insuree.education is not None:
                    EducationLevelMapping.load()
                    display = EducationLevelMapping.education_level[str(
                        imis_policy_holder_insuree.education.id)]
                    system = "CodeSystem/patient-education-level"
                    extension.valueCodeableConcept = cls.build_codeable_concept(
                        code=str(imis_policy_holder_insuree.education.id), system=system)
                    if len(extension.valueCodeableConcept.coding) == 1:
                        extension.valueCodeableConcept.coding[0].display = display

            elif value == "patient.card.issue":
                extension.url = f"{GeneralConfiguration.get_system_base_url()}StructureDefinition/patient-card-issued"
                extension.valueBoolean = imis_policy_holder_insuree.card_issued

            elif value == "patient.group.reference":
                extension.url = f"{GeneralConfiguration.get_system_base_url()}StructureDefinition/patient-group-reference"
                policy_holder_insurees = PolicyHolderInsuree.objects.filter(
                    insuree=imis_policy_holder_insuree)

                if not policy_holder_insurees.exists():
                    FHIRException("No PolicyHolderInsuree matching query.")
                    raise PolicyHolderInsuree.DoesNotExist(
                        "No PolicyHolderInsuree matching query.")
                elif policy_holder_insurees.count() > 1:
                    FHIRException(
                        "Multiple PolicyHolderInsuree matching query.")
                    policy_holder_insuree = policy_holder_insurees.first()  # Or handle as needed
                else:
                    policy_holder_insuree = policy_holder_insurees.first()

                policy_holders = PolicyHolder.objects.filter(
                    policyholderinsuree=policy_holder_insuree)

                if not policy_holders.exists():
                    FHIRException("No PolicyHolder matching query.")
                    raise PolicyHolder.DoesNotExist(
                        "No PolicyHolder matching query.")
                elif policy_holders.count() > 1:
                    FHIRException("Multiple PolicyHolder matching query.")
                    policy_holder = policy_holders.first()
                else:
                    policy_holder = policy_holders.first()

                extension.valueReference = cls.build_fhir_group_resource_reference(
                    policy_holder, 'GroupOrganisation', reference_type=reference_type)

            elif value == "patient.identification":
                nested_extension = Extension.construct()
                extension.url = f"{GeneralConfiguration.get_system_base_url()}StructureDefinition/patient-identification"
                if hasattr(imis_policy_holder_insuree, "type_of_id") and imis_policy_holder_insuree.type_of_id:
                    if hasattr(imis_policy_holder_insuree, "passport") and imis_policy_holder_insuree.passport:
                        # add number extension
                        nested_extension.url = "number"
                        nested_extension.valueString = imis_policy_holder_insuree.passport
                        extension.extension = [nested_extension]
                        # add identifier extension
                        nested_extension = Extension.construct()
                        nested_extension.url = "type"
                        system = "CodeSystem/patient-identification-type"
                        nested_extension.valueCodeableConcept = cls.build_codeable_concept(
                            code=imis_policy_holder_insuree.type_of_id.code, system=system)
                        extension.extension.append(nested_extension)

            else:
                extension.url = f"{GeneralConfiguration.get_system_base_url()}StructureDefinition/patient-profession"
                if hasattr(imis_policy_holder_insuree, "profession") and imis_policy_holder_insuree.profession is not None:
                    PatientProfessionMapping.load()
                    display = PatientProfessionMapping.patient_profession[str(
                        imis_policy_holder_insuree.profession.id)]
                    system = "CodeSystem/patient-profession"
                    extension.valueCodeableConcept = cls.build_codeable_concept(
                        code=str(imis_policy_holder_insuree.profession.id), system=system)
                    if len(extension.valueCodeableConcept.coding) == 1:
                        extension.valueCodeableConcept.coding[0].display = display

            if type(fhir_patient.extension) is not list:
                fhir_patient.extension = [extension]
            else:
                fhir_patient.extension.append(extension)

        if imis_policy_holder_insuree.head is not None:
            build_extension(fhir_patient, imis_policy_holder_insuree, "head")
        if imis_policy_holder_insuree.education is not None:
            build_extension(
                fhir_patient, imis_policy_holder_insuree, "education.education")
        if imis_policy_holder_insuree.profession is not None:
            build_extension(fhir_patient, imis_policy_holder_insuree,
                            "profession.profession")
        if imis_policy_holder_insuree.card_issued is not None:
            build_extension(
                fhir_patient, imis_policy_holder_insuree, "patient.card.issue")
        if imis_policy_holder_insuree.family is not None:
            build_extension(fhir_patient, imis_policy_holder_insuree,
                            "patient.group.reference")
        if imis_policy_holder_insuree.type_of_id is not None and imis_policy_holder_insuree.passport is not None:
            build_extension(fhir_patient, imis_policy_holder_insuree,
                            "patient.identification")

    @classmethod
    def build_fhir_identifiers(cls, fhir_patient, imis_policy_holder_insuree):
        identifiers = []
        cls._validate_imis_identifier_code(imis_policy_holder_insuree)
        cls.build_all_identifiers(identifiers, imis_policy_holder_insuree)
        cls.build_fhir_passport_identifier(
            identifiers, imis_policy_holder_insuree)
        fhir_patient.identifier = identifiers
        cls._validate_fhir_identifier_is_exist(fhir_patient)

    @classmethod
    def _validate_imis_identifier_code(cls, imis_policy_holder_insuree):
        if not imis_policy_holder_insuree.chf_id:
            raise FHIRException(
                _('Insuree %(insuree_uuid)s without code') % {
                    'insuree_uuid': imis_policy_holder_insuree.uuid}
            )

    @classmethod
    def build_fhir_passport_identifier(cls, identifiers, imis_policy_holder_insuree):
        if hasattr(imis_policy_holder_insuree, "type_of_id") and imis_policy_holder_insuree.type_of_id is not None:
            pass  # TODO typeofid isn't provided, this section should contain logic used to create passport field based on typeofid
        elif imis_policy_holder_insuree.passport:
            identifier = cls.build_fhir_identifier(imis_policy_holder_insuree.passport,
                                                   R4IdentifierConfig.get_fhir_identifier_type_system(),
                                                   R4IdentifierConfig.get_fhir_passport_type_code())
            identifiers.append(identifier)

    @classmethod
    def _validate_fhir_identifier_is_exist(cls, fhir_patient):
        if not fhir_patient.identifier or len(fhir_patient.identifier) == 0:
            raise FHIRException(
                _('FHIR Patient entity without identifier')
            )

    @classmethod
    def build_fhir_marital_status(cls, fhir_patient, imis_policy_holder_insuree):
        if imis_policy_holder_insuree.marital:
            display = MaritalStatusMapping.marital_status[imis_policy_holder_insuree.marital]
            fhir_patient.maritalStatus = \
                cls.build_codeable_concept(code=imis_policy_holder_insuree.marital,
                                           system=R4MaritalConfig.get_fhir_marital_status_system())
            if len(fhir_patient.maritalStatus.coding) == 1:
                fhir_patient.maritalStatus.coding[0].display = display

    @classmethod
    def build_fhir_group_resource_reference(cls, resource, resource_type, reference_type=None):
        return {
            "reference": f"{resource_type}/{resource.uuid}",
            "display": str(resource.uuid),
            "type": reference_type,
            "identifier": {
                "system": cls.get_fhir_code_identifier_type(),
                "value": str(resource.trade_name) or str(None)
            }
        }

    @classmethod
    def get_fhir_code_identifier_type(cls):
        return f"{GeneralConfiguration.get_system_base_url()}CodeSystem/"

    @classmethod
    def _validate_fhir_address_details(cls, addresses):
        addr_errors = {}
        for idx, address in enumerate(addresses):
            errors = []
            # Get last part of each extension url
            if not address.extension:
                raise FHIRException("Missing extensions for Address")

            ext_types = [ext.url.rsplit('/')[-1] for ext in address.extension]
            if 'address-location-reference' not in ext_types:
                errors.append(
                    "FHIR Patient address without address-location-reference extension.")
            if 'address-municipality' not in ext_types:
                errors.append(
                    "FHIR Patient address without address-municipality reference.")
            if len(ext_types) != 2:
                errors.append(
                    "Patient's address should provide exactly 2 extensions")
            if not address.city:
                errors.append("Address 'city' field required")
            if not address.district:
                errors.append("Address 'district' field required")
            if not address.state:
                errors.append("Address 'state' field required")

            if errors:
                addr_errors[idx] = errors

        if addr_errors:
            raise FHIRException(json.dumps(addr_errors))
