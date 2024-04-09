from urllib.parse import urljoin

from django.utils.translation import gettext as _
from fhir.resources.R4B.address import Address
from fhir.resources.R4B.extension import Extension
from fhir.resources.R4B.humanname import HumanName
from api_fhir_r4.converters import PatientConverter
from api_fhir_r4.mapping.organizationMapping import PolicyHolderOrganisationLegalFormMapping, \
    PolicyHolderOrganisationActivityMapping
from api_fhir_r4.models.imisModelEnums import ImisLocationType, ContactPointSystem, AddressType
from location.models import Location
from policyholder.models import PolicyHolder, PolicyHolderInsuree
from api_fhir_r4.configurations import R4IdentifierConfig, R4OrganisationConfig, GeneralConfiguration
from api_fhir_r4.converters import BaseFHIRConverter, ReferenceConverterMixin
from fhir.resources.R4B.organization import Organization
from api_fhir_r4.mapping.organizationMapping import HealthFacilityOrganizationTypeMapping

from location.models import HealthFacilityLegalForm
from api_fhir_r4.utils import DbManagerUtils


class PolicyHolderOrganisationConverter(BaseFHIRConverter, ReferenceConverterMixin):
    @classmethod
    def to_fhir_obj(cls, imis_organisation:PolicyHolder, reference_type=ReferenceConverterMixin.UUID_REFERENCE_TYPE):
        fhir_organisation = Organization()
        cls.build_fhir_pk(fhir_organisation, imis_organisation, reference_type)
        cls.build_fhir_extensions(fhir_organisation, imis_organisation, reference_type)
        cls.build_fhir_identifiers(fhir_organisation, imis_organisation, reference_type)
        cls.build_fhir_type(fhir_organisation)
        cls.build_fhir_name(fhir_organisation, imis_organisation)
        cls.build_fhir_telecom(fhir_organisation, imis_organisation)
        cls.build_fhir_ph_address(fhir_organisation, imis_organisation, reference_type)
        cls.build_fhir_contact(fhir_organisation, imis_organisation)
        return fhir_organisation

    @classmethod
    def to_imis_obj(cls, fhir_organisation):
        errors = []
        fhir_ph = Organization(**fhir_organisation)
        imis_ph = PolicyHolder()
        cls.build_imis_ph_identiftier(imis_ph, fhir_ph, errors)
        cls.build_imis_ph_name(imis_ph, fhir_ph, errors)
        cls.build_imis_ph_telecom(imis_ph, fhir_ph, errors)
        cls.build_imis_ph_address(imis_ph, fhir_ph, errors)
        cls.build_imis_legal_form(imis_ph, fhir_ph, errors)
        cls.build_imis_parent_location_id(imis_ph, fhir_ph, errors)
        cls.check_errors(errors)
        return imis_ph

    @classmethod
    def get_imis_obj_by_fhir_reference(cls, reference, errors=None):
        return DbManagerUtils.get_object_or_none(
            PolicyHolder,
            **cls.get_database_query_id_parameteres_from_reference(reference))

    @classmethod
    def get_reference_obj_id(cls, obj):
        return obj.id

    @classmethod
    def get_reference_obj_uuid(cls, obj):
        return obj.uuid

    @classmethod
    def get_reference_obj_code(cls, obj):
        return obj.code

    @classmethod
    def get_fhir_code_identifier_type(cls):
        return R4IdentifierConfig.get_fhir_generic_type_code()

    @classmethod
    def get_fhir_resource_type(cls):
        return Organization

    @classmethod
    def build_fhir_identifiers(cls, fhir_organisation, imis_organisation, reference_type):
        identifiers = []
        cls.build_all_identifiers(identifiers, imis_organisation, reference_type)
        fhir_organisation.identifier = identifiers

    @classmethod
    def build_fhir_extensions(cls, fhir_organisation, imis_organisation, reference_type):
        cls.build_fhir_legal_form_extension(fhir_organisation, imis_organisation)
        cls.build_fhir_activity_extension(fhir_organisation, imis_organisation)
        cls.build_fhir_policy_insuree_extension(fhir_organisation, imis_organisation, reference_type)
        

    @classmethod
    def build_fhir_legal_form_extension(cls, fhir_organisation, imis_organisation):
        codeable_concept = cls.build_codeable_concept_from_coding(cls.build_fhir_mapped_coding(
            PolicyHolderOrganisationLegalFormMapping.fhir_ph_code_system(imis_organisation.legal_form)
        ))
        base = GeneralConfiguration.get_system_base_url()
        url = urljoin(base, R4OrganisationConfig.get_fhir_ph_organisation_legal_form_extension_system())
        extension = cls.build_fhir_codeable_concept_extension(codeable_concept, url)
        if isinstance(fhir_organisation.extension, list):
            fhir_organisation.extension.append(extension)
        else:
            fhir_organisation.extension = [extension]

    @classmethod
    def build_fhir_activity_extension(cls, fhir_organisation, imis_organisation):
        codeable_concept = cls.build_codeable_concept_from_coding(cls.build_fhir_mapped_coding(
            PolicyHolderOrganisationActivityMapping.fhir_ph_code_system(imis_organisation.activity_code)
        ))
        base = GeneralConfiguration.get_system_base_url()
        url = urljoin(base, R4OrganisationConfig.get_fhir_ph_organisation_activity_extension_system())
        extension = cls.build_fhir_codeable_concept_extension(codeable_concept, url)
        if isinstance(fhir_organisation.extension, list):
            fhir_organisation.extension.append(extension)
        else:
            fhir_organisation.extension = [extension]

    @classmethod
    def build_fhir_type(cls, fhir_organisation):
        fhir_organisation.type = [cls.build_codeable_concept(
            R4OrganisationConfig.get_fhir_ph_organisation_type(),
            system=R4OrganisationConfig.get_fhir_ph_organisation_type_system()
        )]

    @classmethod
    def build_fhir_name(cls, fhir_organisation, imis_organisation):
        fhir_organisation.name = imis_organisation.trade_name 

    @classmethod
    def build_fhir_telecom(cls, fhir_organisation, imis_organisation):
        fhir_organisation.telecom = []
        if imis_organisation.email:
            fhir_organisation.telecom.append(cls.build_fhir_contact_point(
                system=ContactPointSystem.EMAIL,
                value=imis_organisation.email))
        if imis_organisation.fax:
            fhir_organisation.telecom.append(cls.build_fhir_contact_point(
                system=ContactPointSystem.FAX,
                value=imis_organisation.fax))
        if imis_organisation.phone:
            fhir_organisation.telecom.append(cls.build_fhir_contact_point(
                system=ContactPointSystem.PHONE,
                value=imis_organisation.phone))

    @classmethod
    def build_fhir_ph_address(cls, fhir_organisation, imis_organisation, reference_type):
        address = Address.construct()
        address.type = AddressType.PHYSICAL.value
        if imis_organisation.address and "address" in imis_organisation.address:
            address.line = [imis_organisation.address["address"]]
        fhir_organisation.address = [address]
        if imis_organisation.locations:
            cls.build_fhir_address_field(fhir_organisation, imis_organisation.locations)
            cls.build_fhir_location_extension(fhir_organisation, imis_organisation, reference_type)

    @classmethod
    def build_fhir_address_field(cls, fhir_organisation, location: Location):
        current_location = location
        while current_location:
            if current_location.type == ImisLocationType.REGION.value:
                fhir_organisation.address[0].state = current_location.name
            elif current_location.type == ImisLocationType.DISTRICT.value:
                fhir_organisation.address[0].district = current_location.name
            elif current_location.type == ImisLocationType.WARD.value:
                cls.build_fhir_municipality_extension(fhir_organisation, current_location)
            elif current_location.type == ImisLocationType.VILLAGE.value:
                fhir_organisation.address[0].city = current_location.name
            current_location = current_location.parent

    @classmethod
    def build_fhir_municipality_extension(cls, fhir_organisation, municipality: Location):
        extension = Extension.construct()
        base = GeneralConfiguration.get_system_base_url()
        extension.url = urljoin(base, R4OrganisationConfig.get_fhir_address_municipality_extension_system())
        extension.valueString = municipality.name
        if isinstance(fhir_organisation.address[0].extension, list):
            fhir_organisation.address[0].extension.append(extension)
        else:
            fhir_organisation.address[0].extension = [extension]

    @classmethod
    def build_fhir_location_extension(cls, fhir_organisation, imis_organisation, reference_type):
        base = GeneralConfiguration.get_system_base_url()
        url = urljoin(base, R4OrganisationConfig.get_fhir_location_reference_extension_system())
        extension = cls.build_fhir_reference_extension(cls.build_fhir_resource_reference
                                                       (imis_organisation.locations,
                                                        type='Location',
                                                        display=imis_organisation.locations.name,
                                                        reference_type=reference_type),
                                                       url)
        if isinstance(fhir_organisation.address[0].extension, list):
            fhir_organisation.address[0].extension.append(extension)
        else:
            fhir_organisation.address[0].extension = [extension]

    @classmethod
    def build_fhir_contact(cls, fhir_organisation, imis_organisation):
        fhir_organisation.contact = []
        if imis_organisation.contact_name:
            name = HumanName.construct()
            name.text = "%s" % (imis_organisation.contact_name['contactName'])
            fhir_organisation.contact.append({'name': name})
    @classmethod
    def build_fhir_policy_insuree_extension(cls, fhir_organisation, imis_organisation, reference_type):
        insurees = PolicyHolderInsuree.objects.filter(policy_holder=imis_organisation, is_deleted=False)
        insuree_extensions = []

        for insuree_relation in insurees:
            # Primary extension for the insuree
            insuree_extension = Extension.construct()
            insuree_extension.url = "http://example.org/fhir/StructureDefinition/policyholder-insuree-details"

            # HumanName extension
            human_name = HumanName.construct()
            human_name.given = [insuree_relation.insuree.other_names]
            human_name.family = insuree_relation.insuree.last_name
            name_extension = Extension.construct()
            name_extension.url = "http://example.org/fhir/StructureDefinition/insuree-name"
            name_extension.valueHumanName = human_name

            

            
            # Adding name and address extensions to the primary insuree extension
            
            # Reference to Patient
            insuree_extension.valueReference = PatientConverter\
                 .build_fhir_resource_reference(insuree_relation.insuree, type='Patient', display=insuree_relation.insuree.chf_id, reference_type=reference_type)

            insuree_extensions.append(insuree_extension)
            insuree_extensions.append(name_extension)

        if not hasattr(fhir_organisation, 'extension') or not fhir_organisation.extension:
            fhir_organisation.extension = []
        fhir_organisation.extension.extend(insuree_extensions)

    @classmethod
    def build_imis_ph_identiftier(cls, imis_ph, fhir_ph, errors):

        value = cls.get_fhir_identifier_by_code(     
            fhir_ph.identifier,
            R4IdentifierConfig.get_fhir_generic_type_code()
        )

        if value:
            imis_ph.code = value
        cls.valid_condition(imis_ph.code is None,_('Missing PH Organization code', errors))
    
    @classmethod
    def build_imis_ph_name(cls, imis_ph, fhir_ph, errors):
        imis_ph.trade_name = fhir_ph.name or 'name is not found'
        cls.valid_condition(imis_ph.code is None, _('Missing PH Name'), errors)

    @classmethod
    def build_imis_ph_telecom(cls, imis_ph, fhir_ph, errors):
        cls._build_imis_ph_email(imis_ph,fhir_ph,  errors)
        cls._build_imis_ph_fax(imis_ph, fhir_ph,errors)
        cls._build_imis_ph_phone(imis_ph, fhir_ph, errors)

    @classmethod
    def _build_imis_ph_email(cls, imis_ph, fhir_ph, errors):

        imis_ph.email = cls.__get_unique_telecom(
            fhir_ph,
            HealthFacilityOrganizationTypeMapping.EMAIL_CONTACT_POINT_SYSTEM,
            errors
        )
    
    @classmethod
    def _build_imis_ph_fax(cls, imis_ph, fhir_ph, errors ):
        imis_ph.fax = cls.__get_unique_telecom(
            fhir_ph,
            HealthFacilityOrganizationTypeMapping.FAX_CONTACT_POINT_SYSTEM,
            errors
        )

    @classmethod
    def _build_imis_ph_phone(cls, imis_ph, fhir_ph, errors):
        imis_ph.phone = cls.__get_unique_telecom(
            fhir_ph,
            HealthFacilityOrganizationTypeMapping.PHONE_CONTACT_POINT_SYSTEM,
           errors
        )

    @classmethod
    def build_imis_ph_address(cls, imis_ph:PolicyHolder, fhir_ph:Organization, errors):
        if fhir_ph.address:
            imis_ph.address = fhir_ph.address[0].line[0]

    @classmethod
    def build_imis_legal_form(cls, imis_ph, fhir_ph, errors):
        ext_url_suffix = 'organization-legal-form'
        value = cls.__get_extension_by_url_suffix(fhir_ph.extension, ext_url_suffix)
        cls.valid_condition(
            value not in HealthFacilityOrganizationTypeMapping.LEGAL_FORM_MAPPING.keys(),
            _("Invalid PH legal form code, has to be one of %(codes)s") % {
                'codes': HealthFacilityOrganizationTypeMapping.LEGAL_FORM_MAPPING.keys()},
            errors)
        if value:
            legal_form = HealthFacilityLegalForm.objects.get(code=value)
            imis_ph.legal_form = legal_form
        else:
            cls.valid_condition(True, _("Extension with PH legal form not found"), errors)

            
    @classmethod
    def build_imis_parent_location_id(cls, imis_ph, fhir_ph, errors):
        from api_fhir_r4.converters import LocationConverter
        if not fhir_ph.address or len(fhir_ph.address) == 0:
            msg = "address not found in the Policy_Holder Organisation"
            cls.valid_condition(len(fhir_ph.address) == 1, msg, errors)
            return
        imis_ph.location = LocationConverter.get_location_from_address(LocationConverter, fhir_ph.address[0])

