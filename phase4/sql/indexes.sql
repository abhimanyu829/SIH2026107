-- BIS SIH26107 PHASE 4 - foreign keys and indexes. Re-runnable.
-- Applied AFTER the bulk COPY: constraint checking once over a full table is
-- far cheaper than per-row checking during the load.
-- Every FK below is the one Phase 3 already declared in
-- POSTGRES_READY/TABLE_MANIFEST.csv (column foreign_keys). None is invented.
SET search_path TO bis, public;

-- ---------------------------- FOREIGN KEYS -----------------------------
-- NULL is allowed and expected: an optional dimension (is_lab_test_mapping
-- .test_id on a lab-scope row) means 'not established by the uploaded data'.
-- A FK constraint rejects a value pointing at a missing parent, not a NULL.
ALTER TABLE bis.is_product_mapping DROP CONSTRAINT IF EXISTS fk_is_product_mapping_is_id;
ALTER TABLE bis.is_product_mapping ADD CONSTRAINT fk_is_product_mapping_is_id FOREIGN KEY (is_id)
    REFERENCES bis.is_master (is_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_product_mapping DROP CONSTRAINT IF EXISTS fk_is_product_mapping_product_id;
ALTER TABLE bis.is_product_mapping ADD CONSTRAINT fk_is_product_mapping_product_id FOREIGN KEY (product_id)
    REFERENCES bis.product_master (product_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_qco_mapping DROP CONSTRAINT IF EXISTS fk_is_qco_mapping_is_id;
ALTER TABLE bis.is_qco_mapping ADD CONSTRAINT fk_is_qco_mapping_is_id FOREIGN KEY (is_id)
    REFERENCES bis.is_master (is_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_qco_mapping DROP CONSTRAINT IF EXISTS fk_is_qco_mapping_qco_id;
ALTER TABLE bis.is_qco_mapping ADD CONSTRAINT fk_is_qco_mapping_qco_id FOREIGN KEY (qco_id)
    REFERENCES bis.qco_master (qco_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_scheme_mapping DROP CONSTRAINT IF EXISTS fk_is_scheme_mapping_is_id;
ALTER TABLE bis.is_scheme_mapping ADD CONSTRAINT fk_is_scheme_mapping_is_id FOREIGN KEY (is_id)
    REFERENCES bis.is_master (is_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_scheme_mapping DROP CONSTRAINT IF EXISTS fk_is_scheme_mapping_scheme_id;
ALTER TABLE bis.is_scheme_mapping ADD CONSTRAINT fk_is_scheme_mapping_scheme_id FOREIGN KEY (scheme_id)
    REFERENCES bis.scheme_master (scheme_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_document_mapping DROP CONSTRAINT IF EXISTS fk_is_document_mapping_is_id;
ALTER TABLE bis.is_document_mapping ADD CONSTRAINT fk_is_document_mapping_is_id FOREIGN KEY (is_id)
    REFERENCES bis.is_master (is_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_document_mapping DROP CONSTRAINT IF EXISTS fk_is_document_mapping_document_id;
ALTER TABLE bis.is_document_mapping ADD CONSTRAINT fk_is_document_mapping_document_id FOREIGN KEY (document_id)
    REFERENCES bis.document_master (document_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_test_mapping DROP CONSTRAINT IF EXISTS fk_is_test_mapping_is_id;
ALTER TABLE bis.is_test_mapping ADD CONSTRAINT fk_is_test_mapping_is_id FOREIGN KEY (is_id)
    REFERENCES bis.is_master (is_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_test_mapping DROP CONSTRAINT IF EXISTS fk_is_test_mapping_test_id;
ALTER TABLE bis.is_test_mapping ADD CONSTRAINT fk_is_test_mapping_test_id FOREIGN KEY (test_id)
    REFERENCES bis.test_master (test_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_lab_test_mapping DROP CONSTRAINT IF EXISTS fk_is_lab_test_mapping_is_id;
ALTER TABLE bis.is_lab_test_mapping ADD CONSTRAINT fk_is_lab_test_mapping_is_id FOREIGN KEY (is_id)
    REFERENCES bis.is_master (is_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_lab_test_mapping DROP CONSTRAINT IF EXISTS fk_is_lab_test_mapping_lab_id;
ALTER TABLE bis.is_lab_test_mapping ADD CONSTRAINT fk_is_lab_test_mapping_lab_id FOREIGN KEY (lab_id)
    REFERENCES bis.lab_master (lab_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_lab_test_mapping DROP CONSTRAINT IF EXISTS fk_is_lab_test_mapping_test_id;
ALTER TABLE bis.is_lab_test_mapping ADD CONSTRAINT fk_is_lab_test_mapping_test_id FOREIGN KEY (test_id)
    REFERENCES bis.test_master (test_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_related_is DROP CONSTRAINT IF EXISTS fk_is_related_is_is_id;
ALTER TABLE bis.is_related_is ADD CONSTRAINT fk_is_related_is_is_id FOREIGN KEY (is_id)
    REFERENCES bis.is_master (is_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_related_is DROP CONSTRAINT IF EXISTS fk_is_related_is_related_is_id;
ALTER TABLE bis.is_related_is ADD CONSTRAINT fk_is_related_is_related_is_id FOREIGN KEY (related_is_id)
    REFERENCES bis.is_master (is_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.qco_scheme_mapping DROP CONSTRAINT IF EXISTS fk_qco_scheme_mapping_qco_id;
ALTER TABLE bis.qco_scheme_mapping ADD CONSTRAINT fk_qco_scheme_mapping_qco_id FOREIGN KEY (qco_id)
    REFERENCES bis.qco_master (qco_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.qco_scheme_mapping DROP CONSTRAINT IF EXISTS fk_qco_scheme_mapping_scheme_id;
ALTER TABLE bis.qco_scheme_mapping ADD CONSTRAINT fk_qco_scheme_mapping_scheme_id FOREIGN KEY (scheme_id)
    REFERENCES bis.scheme_master (scheme_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.product_document_mapping DROP CONSTRAINT IF EXISTS fk_product_document_mapping_product_id;
ALTER TABLE bis.product_document_mapping ADD CONSTRAINT fk_product_document_mapping_product_id FOREIGN KEY (product_id)
    REFERENCES bis.product_master (product_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.product_document_mapping DROP CONSTRAINT IF EXISTS fk_product_document_mapping_document_id;
ALTER TABLE bis.product_document_mapping ADD CONSTRAINT fk_product_document_mapping_document_id FOREIGN KEY (document_id)
    REFERENCES bis.document_master (document_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.test_lab_mapping DROP CONSTRAINT IF EXISTS fk_test_lab_mapping_test_id;
ALTER TABLE bis.test_lab_mapping ADD CONSTRAINT fk_test_lab_mapping_test_id FOREIGN KEY (test_id)
    REFERENCES bis.test_master (test_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.test_lab_mapping DROP CONSTRAINT IF EXISTS fk_test_lab_mapping_lab_id;
ALTER TABLE bis.test_lab_mapping ADD CONSTRAINT fk_test_lab_mapping_lab_id FOREIGN KEY (lab_id)
    REFERENCES bis.lab_master (lab_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.notification_entity_mapping DROP CONSTRAINT IF EXISTS fk_notification_entity_mapping_notification_id;
ALTER TABLE bis.notification_entity_mapping ADD CONSTRAINT fk_notification_entity_mapping_notification_id FOREIGN KEY (notification_id)
    REFERENCES bis.notification_master (notification_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_amendments DROP CONSTRAINT IF EXISTS fk_is_amendments_is_id;
ALTER TABLE bis.is_amendments ADD CONSTRAINT fk_is_amendments_is_id FOREIGN KEY (is_id)
    REFERENCES bis.is_master (is_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_amendments DROP CONSTRAINT IF EXISTS fk_is_amendments_document_id;
ALTER TABLE bis.is_amendments ADD CONSTRAINT fk_is_amendments_document_id FOREIGN KEY (document_id)
    REFERENCES bis.document_master (document_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_product_manual_mapping DROP CONSTRAINT IF EXISTS fk_is_product_manual_mapping_is_id;
ALTER TABLE bis.is_product_manual_mapping ADD CONSTRAINT fk_is_product_manual_mapping_is_id FOREIGN KEY (is_id)
    REFERENCES bis.is_master (is_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_product_manual_mapping DROP CONSTRAINT IF EXISTS fk_is_product_manual_mapping_manual_id;
ALTER TABLE bis.is_product_manual_mapping ADD CONSTRAINT fk_is_product_manual_mapping_manual_id FOREIGN KEY (manual_id)
    REFERENCES bis.product_manual_master (pm_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_fmcs_mapping DROP CONSTRAINT IF EXISTS fk_is_fmcs_mapping_is_id;
ALTER TABLE bis.is_fmcs_mapping ADD CONSTRAINT fk_is_fmcs_mapping_is_id FOREIGN KEY (is_id)
    REFERENCES bis.is_master (is_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_fmcs_mapping DROP CONSTRAINT IF EXISTS fk_is_fmcs_mapping_fmcs_id;
ALTER TABLE bis.is_fmcs_mapping ADD CONSTRAINT fk_is_fmcs_mapping_fmcs_id FOREIGN KEY (fmcs_id)
    REFERENCES bis.fmcs_master (fmcs_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.entity_document_mapping DROP CONSTRAINT IF EXISTS fk_entity_document_mapping_document_id;
ALTER TABLE bis.entity_document_mapping ADD CONSTRAINT fk_entity_document_mapping_document_id FOREIGN KEY (document_id)
    REFERENCES bis.document_master (document_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.scheme_product_mapping DROP CONSTRAINT IF EXISTS fk_scheme_product_mapping_scheme_id;
ALTER TABLE bis.scheme_product_mapping ADD CONSTRAINT fk_scheme_product_mapping_scheme_id FOREIGN KEY (scheme_id)
    REFERENCES bis.scheme_master (scheme_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.scheme_product_mapping DROP CONSTRAINT IF EXISTS fk_scheme_product_mapping_product_id;
ALTER TABLE bis.scheme_product_mapping ADD CONSTRAINT fk_scheme_product_mapping_product_id FOREIGN KEY (product_id)
    REFERENCES bis.product_master (product_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.hallmarking_centre_scope DROP CONSTRAINT IF EXISTS fk_hallmarking_centre_scope_centre_id;
ALTER TABLE bis.hallmarking_centre_scope ADD CONSTRAINT fk_hallmarking_centre_scope_centre_id FOREIGN KEY (centre_id)
    REFERENCES bis.hallmarking_master (hm_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.is_entity_mapping DROP CONSTRAINT IF EXISTS fk_is_entity_mapping_is_id;
ALTER TABLE bis.is_entity_mapping ADD CONSTRAINT fk_is_entity_mapping_is_id FOREIGN KEY (is_id)
    REFERENCES bis.is_master (is_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.qco_product_mapping DROP CONSTRAINT IF EXISTS fk_qco_product_mapping_qco_id;
ALTER TABLE bis.qco_product_mapping ADD CONSTRAINT fk_qco_product_mapping_qco_id FOREIGN KEY (qco_id)
    REFERENCES bis.qco_master (qco_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.qco_product_mapping DROP CONSTRAINT IF EXISTS fk_qco_product_mapping_product_id;
ALTER TABLE bis.qco_product_mapping ADD CONSTRAINT fk_qco_product_mapping_product_id FOREIGN KEY (product_id)
    REFERENCES bis.product_master (product_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.product_manual_infrastructure DROP CONSTRAINT IF EXISTS fk_product_manual_infrastructure_pm_id;
ALTER TABLE bis.product_manual_infrastructure ADD CONSTRAINT fk_product_manual_infrastructure_pm_id FOREIGN KEY (pm_id)
    REFERENCES bis.product_manual_master (pm_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.product_manual_marking DROP CONSTRAINT IF EXISTS fk_product_manual_marking_pm_id;
ALTER TABLE bis.product_manual_marking ADD CONSTRAINT fk_product_manual_marking_pm_id FOREIGN KEY (pm_id)
    REFERENCES bis.product_manual_master (pm_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.product_manual_requirements DROP CONSTRAINT IF EXISTS fk_product_manual_requirements_pm_id;
ALTER TABLE bis.product_manual_requirements ADD CONSTRAINT fk_product_manual_requirements_pm_id FOREIGN KEY (pm_id)
    REFERENCES bis.product_manual_master (pm_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.product_manual_sampling DROP CONSTRAINT IF EXISTS fk_product_manual_sampling_pm_id;
ALTER TABLE bis.product_manual_sampling ADD CONSTRAINT fk_product_manual_sampling_pm_id FOREIGN KEY (pm_id)
    REFERENCES bis.product_manual_master (pm_id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE bis.product_manual_testing DROP CONSTRAINT IF EXISTS fk_product_manual_testing_pm_id;
ALTER TABLE bis.product_manual_testing ADD CONSTRAINT fk_product_manual_testing_pm_id FOREIGN KEY (pm_id)
    REFERENCES bis.product_manual_master (pm_id) ON UPDATE CASCADE ON DELETE RESTRICT;

-- ------------------------ FK / LOOKUP INDEXES --------------------------
CREATE INDEX IF NOT EXISTS ix_is_product_mapping_is_id ON bis.is_product_mapping (is_id);
CREATE INDEX IF NOT EXISTS ix_is_product_mapping_product_id ON bis.is_product_mapping (product_id);
CREATE INDEX IF NOT EXISTS ix_is_qco_mapping_is_id ON bis.is_qco_mapping (is_id);
CREATE INDEX IF NOT EXISTS ix_is_qco_mapping_qco_id ON bis.is_qco_mapping (qco_id);
CREATE INDEX IF NOT EXISTS ix_is_scheme_mapping_is_id ON bis.is_scheme_mapping (is_id);
CREATE INDEX IF NOT EXISTS ix_is_scheme_mapping_scheme_id ON bis.is_scheme_mapping (scheme_id);
CREATE INDEX IF NOT EXISTS ix_is_document_mapping_is_id ON bis.is_document_mapping (is_id);
CREATE INDEX IF NOT EXISTS ix_is_document_mapping_document_id ON bis.is_document_mapping (document_id);
CREATE INDEX IF NOT EXISTS ix_is_test_mapping_is_id ON bis.is_test_mapping (is_id);
CREATE INDEX IF NOT EXISTS ix_is_test_mapping_test_id ON bis.is_test_mapping (test_id);
CREATE INDEX IF NOT EXISTS ix_is_lab_test_mapping_is_id ON bis.is_lab_test_mapping (is_id);
CREATE INDEX IF NOT EXISTS ix_is_lab_test_mapping_lab_id ON bis.is_lab_test_mapping (lab_id);
CREATE INDEX IF NOT EXISTS ix_is_lab_test_mapping_test_id ON bis.is_lab_test_mapping (test_id);
CREATE INDEX IF NOT EXISTS ix_is_related_is_is_id ON bis.is_related_is (is_id);
CREATE INDEX IF NOT EXISTS ix_is_related_is_related_is_id ON bis.is_related_is (related_is_id);
CREATE INDEX IF NOT EXISTS ix_qco_scheme_mapping_qco_id ON bis.qco_scheme_mapping (qco_id);
CREATE INDEX IF NOT EXISTS ix_qco_scheme_mapping_scheme_id ON bis.qco_scheme_mapping (scheme_id);
CREATE INDEX IF NOT EXISTS ix_product_document_mapping_product_id ON bis.product_document_mapping (product_id);
CREATE INDEX IF NOT EXISTS ix_product_document_mapping_document_id ON bis.product_document_mapping (document_id);
CREATE INDEX IF NOT EXISTS ix_test_lab_mapping_test_id ON bis.test_lab_mapping (test_id);
CREATE INDEX IF NOT EXISTS ix_test_lab_mapping_lab_id ON bis.test_lab_mapping (lab_id);
CREATE INDEX IF NOT EXISTS ix_notification_entity_mapping_notification_id ON bis.notification_entity_mapping (notification_id);
CREATE INDEX IF NOT EXISTS ix_is_amendments_is_id ON bis.is_amendments (is_id);
CREATE INDEX IF NOT EXISTS ix_is_amendments_document_id ON bis.is_amendments (document_id);
CREATE INDEX IF NOT EXISTS ix_is_product_manual_mapping_is_id ON bis.is_product_manual_mapping (is_id);
CREATE INDEX IF NOT EXISTS ix_is_product_manual_mapping_manual_id ON bis.is_product_manual_mapping (manual_id);
CREATE INDEX IF NOT EXISTS ix_is_fmcs_mapping_is_id ON bis.is_fmcs_mapping (is_id);
CREATE INDEX IF NOT EXISTS ix_is_fmcs_mapping_fmcs_id ON bis.is_fmcs_mapping (fmcs_id);
CREATE INDEX IF NOT EXISTS ix_entity_document_mapping_document_id ON bis.entity_document_mapping (document_id);
CREATE INDEX IF NOT EXISTS ix_scheme_product_mapping_scheme_id ON bis.scheme_product_mapping (scheme_id);
CREATE INDEX IF NOT EXISTS ix_scheme_product_mapping_product_id ON bis.scheme_product_mapping (product_id);
CREATE INDEX IF NOT EXISTS ix_hallmarking_centre_scope_centre_id ON bis.hallmarking_centre_scope (centre_id);
CREATE INDEX IF NOT EXISTS ix_is_entity_mapping_is_id ON bis.is_entity_mapping (is_id);
CREATE INDEX IF NOT EXISTS ix_qco_product_mapping_qco_id ON bis.qco_product_mapping (qco_id);
CREATE INDEX IF NOT EXISTS ix_qco_product_mapping_product_id ON bis.qco_product_mapping (product_id);
CREATE INDEX IF NOT EXISTS ix_product_manual_infrastructure_pm_id ON bis.product_manual_infrastructure (pm_id);
CREATE INDEX IF NOT EXISTS ix_product_manual_marking_pm_id ON bis.product_manual_marking (pm_id);
CREATE INDEX IF NOT EXISTS ix_product_manual_requirements_pm_id ON bis.product_manual_requirements (pm_id);
CREATE INDEX IF NOT EXISTS ix_product_manual_sampling_pm_id ON bis.product_manual_sampling (pm_id);
CREATE INDEX IF NOT EXISTS ix_product_manual_testing_pm_id ON bis.product_manual_testing (pm_id);

-- Lookup paths used by retrieval/postgres_retriever.py.
CREATE INDEX IF NOT EXISTS ix_is_master_canonical_is_number ON bis.is_master (canonical_is_number);
CREATE INDEX IF NOT EXISTS ix_is_master_standard_status ON bis.is_master (standard_status);
CREATE INDEX IF NOT EXISTS ix_product_master_product_name ON bis.product_master (product_name);
CREATE INDEX IF NOT EXISTS ix_qco_master_qco_number_normalized ON bis.qco_master (qco_number_normalized);
CREATE INDEX IF NOT EXISTS ix_scheme_master_scheme_code ON bis.scheme_master (scheme_code);
CREATE INDEX IF NOT EXISTS ix_test_master_test_name ON bis.test_master (test_name);
CREATE INDEX IF NOT EXISTS ix_lab_master_lab_name ON bis.lab_master (lab_name);
CREATE INDEX IF NOT EXISTS ix_lab_master_state ON bis.lab_master (state);
CREATE INDEX IF NOT EXISTS ix_document_master_document_type ON bis.document_master (document_type);
CREATE INDEX IF NOT EXISTS ix_faq_master_faq_category ON bis.faq_master (faq_category);
CREATE INDEX IF NOT EXISTS ix_notification_master_notification_number ON bis.notification_master (notification_number);
CREATE INDEX IF NOT EXISTS ix_product_manual_master_canonical_is_number ON bis.product_manual_master (canonical_is_number);
CREATE INDEX IF NOT EXISTS ix_entity_attributes_entity_id ON bis.entity_attributes (entity_id);
CREATE INDEX IF NOT EXISTS ix_record_provenance_entity_id ON bis.record_provenance (entity_id);

-- Optional trigram acceleration for the product/title ILIKE searches.
-- Wrapped so a Supabase project without pg_trgm still loads cleanly; the
-- retriever works either way, just with a sequential scan.
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE INDEX IF NOT EXISTS ix_is_master_title_trgm
        ON bis.is_master USING gin (title gin_trgm_ops);
    CREATE INDEX IF NOT EXISTS ix_product_master_name_trgm
        ON bis.product_master USING gin (product_name gin_trgm_ops);
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pg_trgm unavailable (%), ILIKE will use a scan', SQLERRM;
END $$;
