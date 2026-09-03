-- BIS SIH26107 PHASE 4 - Supabase validation. Read-only; safe to re-run.
-- Every query must return the stated expectation or Phase 4 is not complete.
SET search_path TO bis, public;

-- 1. TABLE INVENTORY --------------------------------------------------------
--    Expect exactly 50 tables in schema bis.
SELECT count(*) AS tables_in_bis FROM information_schema.tables
 WHERE table_schema = 'bis' AND table_type = 'BASE TABLE';

-- 2. ROW COUNT PER TABLE ---------------------------------------------------
--    Compare against validation/PHASE4_VALIDATION.json -> expected_row_counts,
--    which is measured directly from the Phase-3 CSV files.
SELECT 'is_master' AS table_name, count(*) AS rows FROM bis.is_master
UNION ALL
SELECT 'product_master' AS table_name, count(*) AS rows FROM bis.product_master
UNION ALL
SELECT 'qco_master' AS table_name, count(*) AS rows FROM bis.qco_master
UNION ALL
SELECT 'scheme_master' AS table_name, count(*) AS rows FROM bis.scheme_master
UNION ALL
SELECT 'product_manual_master' AS table_name, count(*) AS rows FROM bis.product_manual_master
UNION ALL
SELECT 'test_master' AS table_name, count(*) AS rows FROM bis.test_master
UNION ALL
SELECT 'lab_master' AS table_name, count(*) AS rows FROM bis.lab_master
UNION ALL
SELECT 'document_master' AS table_name, count(*) AS rows FROM bis.document_master
UNION ALL
SELECT 'faq_master' AS table_name, count(*) AS rows FROM bis.faq_master
UNION ALL
SELECT 'notification_master' AS table_name, count(*) AS rows FROM bis.notification_master
UNION ALL
SELECT 'legal_master' AS table_name, count(*) AS rows FROM bis.legal_master
UNION ALL
SELECT 'hallmarking_master' AS table_name, count(*) AS rows FROM bis.hallmarking_master
UNION ALL
SELECT 'fmcs_master' AS table_name, count(*) AS rows FROM bis.fmcs_master
UNION ALL
SELECT 'is_product_mapping' AS table_name, count(*) AS rows FROM bis.is_product_mapping
UNION ALL
SELECT 'is_qco_mapping' AS table_name, count(*) AS rows FROM bis.is_qco_mapping
UNION ALL
SELECT 'is_scheme_mapping' AS table_name, count(*) AS rows FROM bis.is_scheme_mapping
UNION ALL
SELECT 'is_document_mapping' AS table_name, count(*) AS rows FROM bis.is_document_mapping
UNION ALL
SELECT 'is_test_mapping' AS table_name, count(*) AS rows FROM bis.is_test_mapping
UNION ALL
SELECT 'is_lab_test_mapping' AS table_name, count(*) AS rows FROM bis.is_lab_test_mapping
UNION ALL
SELECT 'is_related_is' AS table_name, count(*) AS rows FROM bis.is_related_is
UNION ALL
SELECT 'qco_scheme_mapping' AS table_name, count(*) AS rows FROM bis.qco_scheme_mapping
UNION ALL
SELECT 'product_document_mapping' AS table_name, count(*) AS rows FROM bis.product_document_mapping
UNION ALL
SELECT 'test_lab_mapping' AS table_name, count(*) AS rows FROM bis.test_lab_mapping
UNION ALL
SELECT 'notification_entity_mapping' AS table_name, count(*) AS rows FROM bis.notification_entity_mapping
UNION ALL
SELECT 'is_amendments' AS table_name, count(*) AS rows FROM bis.is_amendments
UNION ALL
SELECT 'is_product_manual_mapping' AS table_name, count(*) AS rows FROM bis.is_product_manual_mapping
UNION ALL
SELECT 'is_fmcs_mapping' AS table_name, count(*) AS rows FROM bis.is_fmcs_mapping
UNION ALL
SELECT 'entity_document_mapping' AS table_name, count(*) AS rows FROM bis.entity_document_mapping
UNION ALL
SELECT 'scheme_product_mapping' AS table_name, count(*) AS rows FROM bis.scheme_product_mapping
UNION ALL
SELECT 'hallmarking_centre_scope' AS table_name, count(*) AS rows FROM bis.hallmarking_centre_scope
UNION ALL
SELECT 'is_entity_mapping' AS table_name, count(*) AS rows FROM bis.is_entity_mapping
UNION ALL
SELECT 'qco_product_mapping' AS table_name, count(*) AS rows FROM bis.qco_product_mapping
UNION ALL
SELECT 'product_manual_infrastructure' AS table_name, count(*) AS rows FROM bis.product_manual_infrastructure
UNION ALL
SELECT 'product_manual_marking' AS table_name, count(*) AS rows FROM bis.product_manual_marking
UNION ALL
SELECT 'product_manual_requirements' AS table_name, count(*) AS rows FROM bis.product_manual_requirements
UNION ALL
SELECT 'product_manual_sampling' AS table_name, count(*) AS rows FROM bis.product_manual_sampling
UNION ALL
SELECT 'product_manual_testing' AS table_name, count(*) AS rows FROM bis.product_manual_testing
UNION ALL
SELECT 'entity_attributes' AS table_name, count(*) AS rows FROM bis.entity_attributes
UNION ALL
SELECT 'record_provenance' AS table_name, count(*) AS rows FROM bis.record_provenance
UNION ALL
SELECT 'source_file_provenance' AS table_name, count(*) AS rows FROM bis.source_file_provenance
UNION ALL
SELECT 'document_provenance' AS table_name, count(*) AS rows FROM bis.document_provenance
UNION ALL
SELECT 'conflict_status' AS table_name, count(*) AS rows FROM bis.conflict_status
UNION ALL
SELECT 'requires_review' AS table_name, count(*) AS rows FROM bis.requires_review
UNION ALL
SELECT 'data_loss_audit' AS table_name, count(*) AS rows FROM bis.data_loss_audit
UNION ALL
SELECT 'orphan_records' AS table_name, count(*) AS rows FROM bis.orphan_records
UNION ALL
SELECT 'extraction_log' AS table_name, count(*) AS rows FROM bis.extraction_log
UNION ALL
SELECT 'fmcs_country_coverage' AS table_name, count(*) AS rows FROM bis.fmcs_country_coverage
UNION ALL
SELECT 'fmcs_is_coverage' AS table_name, count(*) AS rows FROM bis.fmcs_is_coverage
UNION ALL
SELECT 'lab_scope' AS table_name, count(*) AS rows FROM bis.lab_scope
UNION ALL
SELECT 'unresolved_relationship_references' AS table_name, count(*) AS rows FROM bis.unresolved_relationship_references
ORDER BY table_name;

-- 3. BLANK PRIMARY KEYS ----------------------------------------------------
--    Expect 0 for every table.
SELECT 'is_master' AS table_name, count(*) AS blank_pk FROM bis.is_master WHERE is_id IS NULL OR btrim(is_id) = ''
UNION ALL
SELECT 'product_master' AS table_name, count(*) AS blank_pk FROM bis.product_master WHERE product_id IS NULL OR btrim(product_id) = ''
UNION ALL
SELECT 'qco_master' AS table_name, count(*) AS blank_pk FROM bis.qco_master WHERE qco_id IS NULL OR btrim(qco_id) = ''
UNION ALL
SELECT 'scheme_master' AS table_name, count(*) AS blank_pk FROM bis.scheme_master WHERE scheme_id IS NULL OR btrim(scheme_id) = ''
UNION ALL
SELECT 'product_manual_master' AS table_name, count(*) AS blank_pk FROM bis.product_manual_master WHERE pm_id IS NULL OR btrim(pm_id) = ''
UNION ALL
SELECT 'test_master' AS table_name, count(*) AS blank_pk FROM bis.test_master WHERE test_id IS NULL OR btrim(test_id) = ''
UNION ALL
SELECT 'lab_master' AS table_name, count(*) AS blank_pk FROM bis.lab_master WHERE lab_id IS NULL OR btrim(lab_id) = ''
UNION ALL
SELECT 'document_master' AS table_name, count(*) AS blank_pk FROM bis.document_master WHERE document_id IS NULL OR btrim(document_id) = ''
UNION ALL
SELECT 'faq_master' AS table_name, count(*) AS blank_pk FROM bis.faq_master WHERE faq_id IS NULL OR btrim(faq_id) = ''
UNION ALL
SELECT 'notification_master' AS table_name, count(*) AS blank_pk FROM bis.notification_master WHERE notification_id IS NULL OR btrim(notification_id) = ''
UNION ALL
SELECT 'legal_master' AS table_name, count(*) AS blank_pk FROM bis.legal_master WHERE legal_id IS NULL OR btrim(legal_id) = ''
UNION ALL
SELECT 'hallmarking_master' AS table_name, count(*) AS blank_pk FROM bis.hallmarking_master WHERE hm_id IS NULL OR btrim(hm_id) = ''
UNION ALL
SELECT 'fmcs_master' AS table_name, count(*) AS blank_pk FROM bis.fmcs_master WHERE fmcs_id IS NULL OR btrim(fmcs_id) = ''
UNION ALL
SELECT 'is_product_mapping' AS table_name, count(*) AS blank_pk FROM bis.is_product_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'is_qco_mapping' AS table_name, count(*) AS blank_pk FROM bis.is_qco_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'is_scheme_mapping' AS table_name, count(*) AS blank_pk FROM bis.is_scheme_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'is_document_mapping' AS table_name, count(*) AS blank_pk FROM bis.is_document_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'is_test_mapping' AS table_name, count(*) AS blank_pk FROM bis.is_test_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'is_lab_test_mapping' AS table_name, count(*) AS blank_pk FROM bis.is_lab_test_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'is_related_is' AS table_name, count(*) AS blank_pk FROM bis.is_related_is WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'qco_scheme_mapping' AS table_name, count(*) AS blank_pk FROM bis.qco_scheme_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'product_document_mapping' AS table_name, count(*) AS blank_pk FROM bis.product_document_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'test_lab_mapping' AS table_name, count(*) AS blank_pk FROM bis.test_lab_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'notification_entity_mapping' AS table_name, count(*) AS blank_pk FROM bis.notification_entity_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'is_amendments' AS table_name, count(*) AS blank_pk FROM bis.is_amendments WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'is_product_manual_mapping' AS table_name, count(*) AS blank_pk FROM bis.is_product_manual_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'is_fmcs_mapping' AS table_name, count(*) AS blank_pk FROM bis.is_fmcs_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'entity_document_mapping' AS table_name, count(*) AS blank_pk FROM bis.entity_document_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'scheme_product_mapping' AS table_name, count(*) AS blank_pk FROM bis.scheme_product_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'hallmarking_centre_scope' AS table_name, count(*) AS blank_pk FROM bis.hallmarking_centre_scope WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'is_entity_mapping' AS table_name, count(*) AS blank_pk FROM bis.is_entity_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'qco_product_mapping' AS table_name, count(*) AS blank_pk FROM bis.qco_product_mapping WHERE relationship_id IS NULL OR btrim(relationship_id) = ''
UNION ALL
SELECT 'product_manual_infrastructure' AS table_name, count(*) AS blank_pk FROM bis.product_manual_infrastructure WHERE pm_section_id IS NULL OR btrim(pm_section_id) = ''
UNION ALL
SELECT 'product_manual_marking' AS table_name, count(*) AS blank_pk FROM bis.product_manual_marking WHERE pm_section_id IS NULL OR btrim(pm_section_id) = ''
UNION ALL
SELECT 'product_manual_requirements' AS table_name, count(*) AS blank_pk FROM bis.product_manual_requirements WHERE pm_section_id IS NULL OR btrim(pm_section_id) = ''
UNION ALL
SELECT 'product_manual_sampling' AS table_name, count(*) AS blank_pk FROM bis.product_manual_sampling WHERE pm_section_id IS NULL OR btrim(pm_section_id) = ''
UNION ALL
SELECT 'product_manual_testing' AS table_name, count(*) AS blank_pk FROM bis.product_manual_testing WHERE pm_section_id IS NULL OR btrim(pm_section_id) = ''
UNION ALL
SELECT 'entity_attributes' AS table_name, count(*) AS blank_pk FROM bis.entity_attributes WHERE attribute_id IS NULL OR btrim(attribute_id) = ''
UNION ALL
SELECT 'record_provenance' AS table_name, count(*) AS blank_pk FROM bis.record_provenance WHERE provenance_id IS NULL OR btrim(provenance_id) = ''
UNION ALL
SELECT 'source_file_provenance' AS table_name, count(*) AS blank_pk FROM bis.source_file_provenance WHERE source_file_id IS NULL OR btrim(source_file_id) = ''
UNION ALL
SELECT 'document_provenance' AS table_name, count(*) AS blank_pk FROM bis.document_provenance WHERE document_provenance_id IS NULL OR btrim(document_provenance_id) = ''
UNION ALL
SELECT 'conflict_status' AS table_name, count(*) AS blank_pk FROM bis.conflict_status WHERE conflict_id IS NULL OR btrim(conflict_id) = ''
UNION ALL
SELECT 'requires_review' AS table_name, count(*) AS blank_pk FROM bis.requires_review WHERE review_id IS NULL OR btrim(review_id) = ''
UNION ALL
SELECT 'unresolved_relationship_references' AS table_name, count(*) AS blank_pk FROM bis.unresolved_relationship_references WHERE quarantine_id IS NULL OR btrim(quarantine_id) = '';

-- 4. DUPLICATE PRIMARY KEYS ------------------------------------------------
--    Expect 0 for every table (the PK constraint already guarantees it; this
--    proves the constraint is present and was enforced during the load).
SELECT 'is_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.is_master GROUP BY is_id) q
UNION ALL
SELECT 'product_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.product_master GROUP BY product_id) q
UNION ALL
SELECT 'qco_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.qco_master GROUP BY qco_id) q
UNION ALL
SELECT 'scheme_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.scheme_master GROUP BY scheme_id) q
UNION ALL
SELECT 'product_manual_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.product_manual_master GROUP BY pm_id) q
UNION ALL
SELECT 'test_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.test_master GROUP BY test_id) q
UNION ALL
SELECT 'lab_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.lab_master GROUP BY lab_id) q
UNION ALL
SELECT 'document_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.document_master GROUP BY document_id) q
UNION ALL
SELECT 'faq_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.faq_master GROUP BY faq_id) q
UNION ALL
SELECT 'notification_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.notification_master GROUP BY notification_id) q
UNION ALL
SELECT 'legal_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.legal_master GROUP BY legal_id) q
UNION ALL
SELECT 'hallmarking_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.hallmarking_master GROUP BY hm_id) q
UNION ALL
SELECT 'fmcs_master' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.fmcs_master GROUP BY fmcs_id) q
UNION ALL
SELECT 'is_product_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.is_product_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'is_qco_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.is_qco_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'is_scheme_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.is_scheme_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'is_document_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.is_document_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'is_test_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.is_test_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'is_lab_test_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.is_lab_test_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'is_related_is' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.is_related_is GROUP BY relationship_id) q
UNION ALL
SELECT 'qco_scheme_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.qco_scheme_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'product_document_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.product_document_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'test_lab_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.test_lab_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'notification_entity_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.notification_entity_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'is_amendments' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.is_amendments GROUP BY relationship_id) q
UNION ALL
SELECT 'is_product_manual_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.is_product_manual_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'is_fmcs_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.is_fmcs_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'entity_document_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.entity_document_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'scheme_product_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.scheme_product_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'hallmarking_centre_scope' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.hallmarking_centre_scope GROUP BY relationship_id) q
UNION ALL
SELECT 'is_entity_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.is_entity_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'qco_product_mapping' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.qco_product_mapping GROUP BY relationship_id) q
UNION ALL
SELECT 'product_manual_infrastructure' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.product_manual_infrastructure GROUP BY pm_section_id) q
UNION ALL
SELECT 'product_manual_marking' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.product_manual_marking GROUP BY pm_section_id) q
UNION ALL
SELECT 'product_manual_requirements' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.product_manual_requirements GROUP BY pm_section_id) q
UNION ALL
SELECT 'product_manual_sampling' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.product_manual_sampling GROUP BY pm_section_id) q
UNION ALL
SELECT 'product_manual_testing' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.product_manual_testing GROUP BY pm_section_id) q
UNION ALL
SELECT 'entity_attributes' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.entity_attributes GROUP BY attribute_id) q
UNION ALL
SELECT 'record_provenance' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.record_provenance GROUP BY provenance_id) q
UNION ALL
SELECT 'source_file_provenance' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.source_file_provenance GROUP BY source_file_id) q
UNION ALL
SELECT 'document_provenance' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.document_provenance GROUP BY document_provenance_id) q
UNION ALL
SELECT 'conflict_status' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.conflict_status GROUP BY conflict_id) q
UNION ALL
SELECT 'requires_review' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.requires_review GROUP BY review_id) q
UNION ALL
SELECT 'unresolved_relationship_references' AS table_name, coalesce(sum(c) - count(*), 0) AS dup_pk FROM (SELECT count(*) AS c FROM bis.unresolved_relationship_references GROUP BY quarantine_id) q;

-- 5. FOREIGN KEY CONSTRAINTS PRESENT --------------------------------------
--    Expect 40 rows.
SELECT conrelid::regclass AS child, conname, confrelid::regclass AS parent
  FROM pg_constraint WHERE contype = 'f'
   AND connamespace = 'bis'::regnamespace ORDER BY 1, 2;

-- 6. FOREIGN KEY VALUES RESOLVE -------------------------------------------
--    Expect 0 orphans everywhere. NULL is allowed: it means the uploaded data
--    did not establish that optional dimension.
SELECT 'is_product_mapping.is_id' AS fk, count(*) AS orphans FROM bis.is_product_mapping c LEFT JOIN bis.is_master p ON p.is_id = c.is_id WHERE c.is_id IS NOT NULL AND p.is_id IS NULL
UNION ALL
SELECT 'is_product_mapping.product_id' AS fk, count(*) AS orphans FROM bis.is_product_mapping c LEFT JOIN bis.product_master p ON p.product_id = c.product_id WHERE c.product_id IS NOT NULL AND p.product_id IS NULL
UNION ALL
SELECT 'is_qco_mapping.is_id' AS fk, count(*) AS orphans FROM bis.is_qco_mapping c LEFT JOIN bis.is_master p ON p.is_id = c.is_id WHERE c.is_id IS NOT NULL AND p.is_id IS NULL
UNION ALL
SELECT 'is_qco_mapping.qco_id' AS fk, count(*) AS orphans FROM bis.is_qco_mapping c LEFT JOIN bis.qco_master p ON p.qco_id = c.qco_id WHERE c.qco_id IS NOT NULL AND p.qco_id IS NULL
UNION ALL
SELECT 'is_scheme_mapping.is_id' AS fk, count(*) AS orphans FROM bis.is_scheme_mapping c LEFT JOIN bis.is_master p ON p.is_id = c.is_id WHERE c.is_id IS NOT NULL AND p.is_id IS NULL
UNION ALL
SELECT 'is_scheme_mapping.scheme_id' AS fk, count(*) AS orphans FROM bis.is_scheme_mapping c LEFT JOIN bis.scheme_master p ON p.scheme_id = c.scheme_id WHERE c.scheme_id IS NOT NULL AND p.scheme_id IS NULL
UNION ALL
SELECT 'is_document_mapping.is_id' AS fk, count(*) AS orphans FROM bis.is_document_mapping c LEFT JOIN bis.is_master p ON p.is_id = c.is_id WHERE c.is_id IS NOT NULL AND p.is_id IS NULL
UNION ALL
SELECT 'is_document_mapping.document_id' AS fk, count(*) AS orphans FROM bis.is_document_mapping c LEFT JOIN bis.document_master p ON p.document_id = c.document_id WHERE c.document_id IS NOT NULL AND p.document_id IS NULL
UNION ALL
SELECT 'is_test_mapping.is_id' AS fk, count(*) AS orphans FROM bis.is_test_mapping c LEFT JOIN bis.is_master p ON p.is_id = c.is_id WHERE c.is_id IS NOT NULL AND p.is_id IS NULL
UNION ALL
SELECT 'is_test_mapping.test_id' AS fk, count(*) AS orphans FROM bis.is_test_mapping c LEFT JOIN bis.test_master p ON p.test_id = c.test_id WHERE c.test_id IS NOT NULL AND p.test_id IS NULL
UNION ALL
SELECT 'is_lab_test_mapping.is_id' AS fk, count(*) AS orphans FROM bis.is_lab_test_mapping c LEFT JOIN bis.is_master p ON p.is_id = c.is_id WHERE c.is_id IS NOT NULL AND p.is_id IS NULL
UNION ALL
SELECT 'is_lab_test_mapping.lab_id' AS fk, count(*) AS orphans FROM bis.is_lab_test_mapping c LEFT JOIN bis.lab_master p ON p.lab_id = c.lab_id WHERE c.lab_id IS NOT NULL AND p.lab_id IS NULL
UNION ALL
SELECT 'is_lab_test_mapping.test_id' AS fk, count(*) AS orphans FROM bis.is_lab_test_mapping c LEFT JOIN bis.test_master p ON p.test_id = c.test_id WHERE c.test_id IS NOT NULL AND p.test_id IS NULL
UNION ALL
SELECT 'is_related_is.is_id' AS fk, count(*) AS orphans FROM bis.is_related_is c LEFT JOIN bis.is_master p ON p.is_id = c.is_id WHERE c.is_id IS NOT NULL AND p.is_id IS NULL
UNION ALL
SELECT 'is_related_is.related_is_id' AS fk, count(*) AS orphans FROM bis.is_related_is c LEFT JOIN bis.is_master p ON p.is_id = c.related_is_id WHERE c.related_is_id IS NOT NULL AND p.is_id IS NULL
UNION ALL
SELECT 'qco_scheme_mapping.qco_id' AS fk, count(*) AS orphans FROM bis.qco_scheme_mapping c LEFT JOIN bis.qco_master p ON p.qco_id = c.qco_id WHERE c.qco_id IS NOT NULL AND p.qco_id IS NULL
UNION ALL
SELECT 'qco_scheme_mapping.scheme_id' AS fk, count(*) AS orphans FROM bis.qco_scheme_mapping c LEFT JOIN bis.scheme_master p ON p.scheme_id = c.scheme_id WHERE c.scheme_id IS NOT NULL AND p.scheme_id IS NULL
UNION ALL
SELECT 'product_document_mapping.product_id' AS fk, count(*) AS orphans FROM bis.product_document_mapping c LEFT JOIN bis.product_master p ON p.product_id = c.product_id WHERE c.product_id IS NOT NULL AND p.product_id IS NULL
UNION ALL
SELECT 'product_document_mapping.document_id' AS fk, count(*) AS orphans FROM bis.product_document_mapping c LEFT JOIN bis.document_master p ON p.document_id = c.document_id WHERE c.document_id IS NOT NULL AND p.document_id IS NULL
UNION ALL
SELECT 'test_lab_mapping.test_id' AS fk, count(*) AS orphans FROM bis.test_lab_mapping c LEFT JOIN bis.test_master p ON p.test_id = c.test_id WHERE c.test_id IS NOT NULL AND p.test_id IS NULL
UNION ALL
SELECT 'test_lab_mapping.lab_id' AS fk, count(*) AS orphans FROM bis.test_lab_mapping c LEFT JOIN bis.lab_master p ON p.lab_id = c.lab_id WHERE c.lab_id IS NOT NULL AND p.lab_id IS NULL
UNION ALL
SELECT 'notification_entity_mapping.notification_id' AS fk, count(*) AS orphans FROM bis.notification_entity_mapping c LEFT JOIN bis.notification_master p ON p.notification_id = c.notification_id WHERE c.notification_id IS NOT NULL AND p.notification_id IS NULL
UNION ALL
SELECT 'is_amendments.is_id' AS fk, count(*) AS orphans FROM bis.is_amendments c LEFT JOIN bis.is_master p ON p.is_id = c.is_id WHERE c.is_id IS NOT NULL AND p.is_id IS NULL
UNION ALL
SELECT 'is_amendments.document_id' AS fk, count(*) AS orphans FROM bis.is_amendments c LEFT JOIN bis.document_master p ON p.document_id = c.document_id WHERE c.document_id IS NOT NULL AND p.document_id IS NULL
UNION ALL
SELECT 'is_product_manual_mapping.is_id' AS fk, count(*) AS orphans FROM bis.is_product_manual_mapping c LEFT JOIN bis.is_master p ON p.is_id = c.is_id WHERE c.is_id IS NOT NULL AND p.is_id IS NULL
UNION ALL
SELECT 'is_product_manual_mapping.manual_id' AS fk, count(*) AS orphans FROM bis.is_product_manual_mapping c LEFT JOIN bis.product_manual_master p ON p.pm_id = c.manual_id WHERE c.manual_id IS NOT NULL AND p.pm_id IS NULL
UNION ALL
SELECT 'is_fmcs_mapping.is_id' AS fk, count(*) AS orphans FROM bis.is_fmcs_mapping c LEFT JOIN bis.is_master p ON p.is_id = c.is_id WHERE c.is_id IS NOT NULL AND p.is_id IS NULL
UNION ALL
SELECT 'is_fmcs_mapping.fmcs_id' AS fk, count(*) AS orphans FROM bis.is_fmcs_mapping c LEFT JOIN bis.fmcs_master p ON p.fmcs_id = c.fmcs_id WHERE c.fmcs_id IS NOT NULL AND p.fmcs_id IS NULL
UNION ALL
SELECT 'entity_document_mapping.document_id' AS fk, count(*) AS orphans FROM bis.entity_document_mapping c LEFT JOIN bis.document_master p ON p.document_id = c.document_id WHERE c.document_id IS NOT NULL AND p.document_id IS NULL
UNION ALL
SELECT 'scheme_product_mapping.scheme_id' AS fk, count(*) AS orphans FROM bis.scheme_product_mapping c LEFT JOIN bis.scheme_master p ON p.scheme_id = c.scheme_id WHERE c.scheme_id IS NOT NULL AND p.scheme_id IS NULL
UNION ALL
SELECT 'scheme_product_mapping.product_id' AS fk, count(*) AS orphans FROM bis.scheme_product_mapping c LEFT JOIN bis.product_master p ON p.product_id = c.product_id WHERE c.product_id IS NOT NULL AND p.product_id IS NULL
UNION ALL
SELECT 'hallmarking_centre_scope.centre_id' AS fk, count(*) AS orphans FROM bis.hallmarking_centre_scope c LEFT JOIN bis.hallmarking_master p ON p.hm_id = c.centre_id WHERE c.centre_id IS NOT NULL AND p.hm_id IS NULL
UNION ALL
SELECT 'is_entity_mapping.is_id' AS fk, count(*) AS orphans FROM bis.is_entity_mapping c LEFT JOIN bis.is_master p ON p.is_id = c.is_id WHERE c.is_id IS NOT NULL AND p.is_id IS NULL
UNION ALL
SELECT 'qco_product_mapping.qco_id' AS fk, count(*) AS orphans FROM bis.qco_product_mapping c LEFT JOIN bis.qco_master p ON p.qco_id = c.qco_id WHERE c.qco_id IS NOT NULL AND p.qco_id IS NULL
UNION ALL
SELECT 'qco_product_mapping.product_id' AS fk, count(*) AS orphans FROM bis.qco_product_mapping c LEFT JOIN bis.product_master p ON p.product_id = c.product_id WHERE c.product_id IS NOT NULL AND p.product_id IS NULL
UNION ALL
SELECT 'product_manual_infrastructure.pm_id' AS fk, count(*) AS orphans FROM bis.product_manual_infrastructure c LEFT JOIN bis.product_manual_master p ON p.pm_id = c.pm_id WHERE c.pm_id IS NOT NULL AND p.pm_id IS NULL
UNION ALL
SELECT 'product_manual_marking.pm_id' AS fk, count(*) AS orphans FROM bis.product_manual_marking c LEFT JOIN bis.product_manual_master p ON p.pm_id = c.pm_id WHERE c.pm_id IS NOT NULL AND p.pm_id IS NULL
UNION ALL
SELECT 'product_manual_requirements.pm_id' AS fk, count(*) AS orphans FROM bis.product_manual_requirements c LEFT JOIN bis.product_manual_master p ON p.pm_id = c.pm_id WHERE c.pm_id IS NOT NULL AND p.pm_id IS NULL
UNION ALL
SELECT 'product_manual_sampling.pm_id' AS fk, count(*) AS orphans FROM bis.product_manual_sampling c LEFT JOIN bis.product_manual_master p ON p.pm_id = c.pm_id WHERE c.pm_id IS NOT NULL AND p.pm_id IS NULL
UNION ALL
SELECT 'product_manual_testing.pm_id' AS fk, count(*) AS orphans FROM bis.product_manual_testing c LEFT JOIN bis.product_manual_master p ON p.pm_id = c.pm_id WHERE c.pm_id IS NOT NULL AND p.pm_id IS NULL
ORDER BY orphans DESC, fk;

-- 7. NOT-NULL SANITY ON THE KEY BUSINESS COLUMNS --------------------------
--    Expect 0. These are the columns retrieval depends on.
SELECT 'is_master.canonical_is_number' AS col, count(*) AS nulls FROM bis.is_master
  WHERE canonical_is_number IS NULL OR btrim(canonical_is_number) = ''
UNION ALL SELECT 'product_master.product_name', count(*) FROM bis.product_master
  WHERE product_name IS NULL OR btrim(product_name) = ''
UNION ALL SELECT 'test_master.test_name', count(*) FROM bis.test_master
  WHERE test_name IS NULL OR btrim(test_name) = ''
UNION ALL SELECT 'lab_master.lab_name', count(*) FROM bis.lab_master
  WHERE lab_name IS NULL OR btrim(lab_name) = '';

-- 8. SMOKE TEST: IS 17631 (end-to-end) ------------------------------------
SELECT * FROM standards WHERE canonical_is_number = 'IS 17631';

SELECT s.canonical_is_number, s.title, p.product_name
  FROM standards s
  JOIN is_product_mapping m ON m.is_id = s.is_id
  JOIN products p ON p.product_id = m.product_id
 WHERE s.canonical_is_number = 'IS 17631';

SELECT s.canonical_is_number, q.qco_number, q.qco_name, q.effective_date
  FROM standards s JOIN is_qco_mapping m ON m.is_id = s.is_id
  JOIN qcos q ON q.qco_id = m.qco_id
 WHERE s.canonical_is_number = 'IS 17631';

SELECT s.canonical_is_number, sc.scheme_code, sc.scheme_name
  FROM standards s JOIN is_scheme_mapping m ON m.is_id = s.is_id
  JOIN schemes sc ON sc.scheme_id = m.scheme_id
 WHERE s.canonical_is_number = 'IS 17631';

SELECT s.canonical_is_number, pm.manual_title, pm.manual_version
  FROM standards s JOIN is_product_manual_mapping m ON m.is_id = s.is_id
  JOIN product_manuals pm ON pm.pm_id = m.manual_id
 WHERE s.canonical_is_number = 'IS 17631';

SELECT s.canonical_is_number, t.test_name, t.test_method, t.clause
  FROM standards s JOIN is_test_mapping m ON m.is_id = s.is_id
  JOIN tests t ON t.test_id = m.test_id
 WHERE s.canonical_is_number = 'IS 17631';

SELECT DISTINCT s.canonical_is_number, l.lab_name, l.city, l.state,
       l.recognition_status
  FROM standards s JOIN is_lab_test_mapping m ON m.is_id = s.is_id
  JOIN labs l ON l.lab_id = m.lab_id
 WHERE s.canonical_is_number = 'IS 17631' LIMIT 25;

-- 9. SMOKE TEST: IS 2347:2023 --------------------------------------------
SELECT is_id, canonical_is_number, display_is_number, title, standard_status
  FROM standards WHERE display_is_number = 'IS 2347:2023';
