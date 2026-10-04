"""Read domain-level facts from the joined source table."""

from typing import cast

from doc_agent_core.state import AggregatedFact, ClinicalDomain
from psycopg import AsyncConnection
from psycopg.rows import dict_row

DOMAIN_AGGREGATION_SQL = """
WITH domain_facts AS (
    SELECT subject_id AS patient_id, hadm_id AS admission_id,
           'encounter'::text AS domain,
           jsonb_strip_nulls(jsonb_build_object(
               'anchor_age', NULLIF(btrim(anchor_age), ''),
               'eventtype', NULLIF(btrim(eventtype), '')
           )) AS facts,
           count(*)::integer AS repeat_count
    FROM public.clinical_records
    GROUP BY subject_id, hadm_id, anchor_age, eventtype

    UNION ALL

    SELECT subject_id, hadm_id, 'medication',
           jsonb_strip_nulls(jsonb_build_object(
               'drug', NULLIF(btrim(drug), ''),
               'formulary_drug_cd', NULLIF(btrim(formulary_drug_cd), ''),
               'prod_strength', NULLIF(btrim(prod_strength), ''),
               'dose_val_rx', NULLIF(btrim(dose_val_rx), ''),
               'dose_unit_rx', NULLIF(btrim(dose_unit_rx), ''),
               'form_unit_disp', NULLIF(btrim(form_unit_disp), ''),
               'route', NULLIF(btrim(route), ''),
               'order_type', NULLIF(btrim(order_type), ''),
               'order_subtype', NULLIF(btrim(order_subtype), ''),
               'transaction_type', NULLIF(btrim(transaction_type), '')
           )), count(*)::integer
    FROM public.clinical_records
    GROUP BY subject_id, hadm_id, drug, formulary_drug_cd, prod_strength,
             dose_val_rx, dose_unit_rx, form_unit_disp, route, order_type,
             order_subtype, transaction_type

    UNION ALL

    SELECT subject_id, hadm_id, 'microbiology',
           jsonb_strip_nulls(jsonb_build_object(
               'spec_type_desc', NULLIF(btrim(spec_type_desc), ''),
               'test_name', NULLIF(btrim(test_name), ''),
               'org_name', NULLIF(btrim(org_name), ''),
               'ab_name', NULLIF(btrim(ab_name), ''),
               'comments', NULLIF(btrim(comments), '')
           )), count(*)::integer
    FROM public.clinical_records
    GROUP BY subject_id, hadm_id, spec_type_desc, test_name, org_name,
             ab_name, comments

    UNION ALL

    SELECT subject_id, hadm_id, 'drg',
           jsonb_strip_nulls(jsonb_build_object(
               'drg_type', NULLIF(btrim(drg_type), ''),
               'description', NULLIF(btrim(description), ''),
               'drg_severity', NULLIF(btrim(drg_severity), ''),
               'drg_mortality', NULLIF(btrim(drg_mortality), '')
           )), count(*)::integer
    FROM public.clinical_records
    GROUP BY subject_id, hadm_id, drg_type, description, drg_severity,
             drg_mortality
)
SELECT patient_id, admission_id, domain, facts, repeat_count
FROM domain_facts
WHERE patient_id IS NOT NULL AND btrim(patient_id) <> ''
  AND admission_id IS NOT NULL AND btrim(admission_id) <> ''
  AND facts <> '{}'::jsonb
ORDER BY patient_id, admission_id, domain
"""


async def read_aggregated_facts(
    connection: AsyncConnection[object],
) -> tuple[list[AggregatedFact], int, dict[str, int]]:
    """Fetch SQL-grouped facts and the raw source-row count."""
    async with connection.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(DOMAIN_AGGREGATION_SQL)
        rows = await cursor.fetchall()
        await cursor.execute("SELECT count(*)::integer FROM public.clinical_records")
        source_count_row = await cursor.fetchone()
        if source_count_row is None:
            raise RuntimeError("The source row count query returned no result.")
        source_rows = source_count_row["count"]
        await cursor.execute("""SELECT subject_id, count(*)::integer AS source_rows
               FROM public.clinical_records
               WHERE subject_id IS NOT NULL AND btrim(subject_id) <> ''
               GROUP BY subject_id""")
        patient_counts = await cursor.fetchall()

    facts = [
        AggregatedFact(
            patient_id=str(row["patient_id"]),
            admission_id=str(row["admission_id"]),
            domain=cast(ClinicalDomain, row["domain"]),
            facts={str(key): str(value) for key, value in row["facts"].items()},
            repeat_count=int(row["repeat_count"]),
        )
        for row in rows
    ]
    return (
        facts,
        int(source_rows),
        {str(row["subject_id"]): int(row["source_rows"]) for row in patient_counts},
    )
