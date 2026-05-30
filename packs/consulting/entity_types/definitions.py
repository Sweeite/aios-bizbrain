"Consulting entity subtypes and which identity fields each carries."
from engine.spine.types import EntityType


class ConsultingEntityType:
    """Maps consulting-domain entity subtypes to their base EntityType."""
    CLIENT = EntityType.client
    CONTACT = EntityType.contact
    EMPLOYEE = EntityType.employee
    ENGAGEMENT = EntityType.engagement


CLIENT_IDENTITY_FIELDS = [
    "company_name",
    "industry",
    "hubspot_company_id",
    "primary_contact_ref",
    "contract_start_date",
]

CONTACT_IDENTITY_FIELDS = [
    "full_name",
    "email",
    "title",
    "client_ref",
    "hubspot_contact_id",
]

ENGAGEMENT_IDENTITY_FIELDS = [
    "engagement_name",
    "client_ref",
    "asana_project_id",
    "start_date",
    "end_date",
    "fixed_fee_amount",
    "hourly_budget",
]
