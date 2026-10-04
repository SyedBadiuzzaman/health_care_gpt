"""Keep the user's column choices in one readable place."""

EXCLUDED_COLUMNS = (
    "admission_location",
    "discharge_location",
    "careunit",
    "admission_type",
    "insurance",
    "marital_status",
    "race",
    "gender",
)

# Identifiers group records; they are not part of the clinical document text.
IDENTIFIER_COLUMNS = ("subject_id", "hadm_id")

CLINICAL_COLUMNS = (
    "anchor_age",
    "drug",
    "formulary_drug_cd",
    "prod_strength",
    "dose_val_rx",
    "dose_unit_rx",
    "form_unit_disp",
    "route",
    "eventtype",
    "order_type",
    "order_subtype",
    "transaction_type",
    "spec_type_desc",
    "test_name",
    "org_name",
    "ab_name",
    "comments",
    "drg_type",
    "description",
    "drg_severity",
    "drg_mortality",
)

# Email goes to a contact table and never to the clinical document fields.
SOURCE_COLUMNS = IDENTIFIER_COLUMNS + CLINICAL_COLUMNS + ("email",)
