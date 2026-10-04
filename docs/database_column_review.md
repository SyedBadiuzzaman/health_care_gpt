# Database column review

Step 1: review the available columns before preparing RAG data.

Inspected on 2026-10-03 using read-only PostgreSQL queries over SSH. No individual patient values were retrieved. The connected account exposes one application table: `public.clinical_records`.

## Record identity

- The table contains 1,000 rows, one distinct `subject_id`, and three distinct (`subject_id`, `hadm_id`) pairs.
- Neither identifier is missing or blank. All 1,000 rows have a nonblank `email`.
- No table constraints or indexes were found.
- Use `subject_id` as the source patient grouping key, with `patient_id` as an optional application alias. Treat `hadm_id` as the admission grouping key, subject to confirmation of the source data definitions.
- Neither `subject_id` nor (`subject_id`, `hadm_id`) uniquely identifies a row. A later indexing step must preserve multiple records per patient and admission with separate record/chunk identifiers.
- The local preparation pipeline uses content fingerprints plus occurrence numbers to preserve every selected row. The source database remains unchanged. These snapshot IDs do not establish permanent upstream event identity.

## Columns for selection

The categories below are inferred from column names, not from patient values. Every column belongs to a patient-linked record. The direct demographic/contact fields are distinguished from clinical fields to make selection easier.

| No. | Column | PostgreSQL type | Inferred purpose |
| --- | --- | --- | --- |
| 1 | `subject_id` | text | Patient identifier; retain as grouping metadata |
| 2 | `hadm_id` | text | Admission identifier; retain as grouping metadata |
| 3 | `admission_type` | character varying | Admission context |
| 4 | `admission_location` | character varying | Admission context |
| 5 | `discharge_location` | character varying | Discharge context |
| 6 | `insurance` | character varying | Personal/administrative information |
| 7 | `marital_status` | character varying | Personal/demographic information |
| 8 | `race` | character varying | Personal/demographic information |
| 9 | `gender` | character varying | Personal/demographic information |
| 10 | `anchor_age` | text | Personal/demographic information; source-specific age field |
| 11 | `drug` | character varying | Medication |
| 12 | `formulary_drug_cd` | character varying | Medication code |
| 13 | `prod_strength` | character varying | Medication strength |
| 14 | `dose_val_rx` | character varying | Prescribed dose |
| 15 | `dose_unit_rx` | character varying | Dose unit |
| 16 | `form_unit_disp` | character varying | Dispensing unit |
| 17 | `route` | character varying | Medication route |
| 18 | `eventtype` | character varying | Clinical event |
| 19 | `careunit` | character varying | Care location/unit |
| 20 | `order_type` | character varying | Order category |
| 21 | `order_subtype` | character varying | Order subcategory |
| 22 | `transaction_type` | character varying | Transaction category |
| 23 | `spec_type_desc` | character varying | Specimen description |
| 24 | `test_name` | character varying | Test name |
| 25 | `org_name` | character varying | Possibly organism name; confirm source meaning |
| 26 | `ab_name` | character varying | Possibly antibiotic name; confirm source meaning |
| 27 | `comments` | text | Free text; may contain personal information |
| 28 | `drg_type` | character varying | DRG classification type |
| 29 | `description` | text | Description; may contain personal information |
| 30 | `drg_severity` | text | DRG severity field |
| 31 | `drg_mortality` | text | DRG mortality field |
| 32 | `email` | character varying | Direct contact information |

There are no explicitly named patient-name, phone-number, postal-address, or date-of-birth columns. That does not rule out identifying information in free text.

## Email decision

Exclude `email` from embedding text and clinical documents. Keep contact lookup in the separate local `patient_contacts` table, keyed by patient identifier and email. Retain multiple addresses without automatically choosing a recipient. The existing project does not include the email microservice, so its interface requires inspection before integration.

## Confirmed selection and next step

The user explicitly excludes `admission_location`, `discharge_location`, `careunit`, `admission_type`, `insurance`, `marital_status`, `race`, and `gender`. Retain the remaining 21 clinical columns, two grouping identifiers, and a separate email lookup. The allowlist is in `packages/db/src/doc_agent_db/contact_schema.py`.

Some excluded fields can still provide context. The names resemble MIMIC fields, but the custom table's provenance has not been verified: [admission type and discharge location](https://mimic.mit.edu/docs/iv/modules/hosp/admissions.html) describe admission urgency and discharge disposition; [care unit](https://mimic.mit.edu/docs/iv/modules/hosp/transfers.html) provides care-location context; and [gender and anchor age](https://mimic.mit.edu/docs/iv/modules/hosp/patients.html) have source-specific meanings. Those references do not justify treating the user's excluded fields as included. `anchor_age` is retained as supplied and is not relabeled as current age.

The contact-sync command prepares the local patient/admission lookup. The separate worker builds the pgvector RAG index from medication, microbiology, DRG, and encounter facts. Source data is not modified, and no emails are sent.

## Verified local preparation

The SQLite contact store preserves repeated source rows and keeps addresses in `patient_contacts`. Clinical JSON and rendered document text exclude demographic fields and redact email-shaped text. The pgvector verification separately confirms that no email-shaped values occur in RAG chunks.
