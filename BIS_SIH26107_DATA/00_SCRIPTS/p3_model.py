"""Phase 3 canonical data model - DECLARATIVE ONLY. No I/O, no source mutation.

Every later Phase 3 script reads its truth from here, so the design in
03_CANONICAL_DESIGN/CANONICAL_DATA_MODEL.xlsx and the data actually produced in
Phase 3B-3T cannot drift apart.

Routing is keyed by file_id (F001..F049), never by filename: Phase 1 recorded the
real names and several carry `output__` / `bis_topic17_` prefixes that are easy to
mis-remember. Nothing here is derived from a filename.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p1_lib import norm_header  # noqa: E402  header normalisation must match Phase 1

# --------------------------------------------------------------- 13 entities (3A/3B)
# (entity, id_prefix, master_csv, natural_key, note)
ENTITIES = [
    ("STANDARD", "STD", "IS_MASTER.csv", "canonical_is_number (incl. part+section)",
     "Indian Standard. IS 1489 (Part 1) and (Part 2) are SEPARATE standards."),
    ("PRODUCT", "PROD", "PRODUCT_MASTER.csv", "lower(product_name)",
     "Certifiable product / product family named by BIS sources."),
    ("QCO", "QCO", "QCO_MASTER.csv", "qco_number | else lower(qco_name)",
     "Quality Control Order made under the BIS Act by a line ministry."),
    ("SCHEME", "SCH", "SCHEME_MASTER.csv", "scheme_code | else lower(scheme_name)",
     "Certification scheme (I, II/CRS, IV/COC+FMCS, X) or sub-scheme."),
    ("PRODUCT_MANUAL", "PM", "PRODUCT_MANUAL_MASTER.csv",
     "lower(manual_title) | else is+product", "BIS Product Manual / STI document."),
    ("TEST", "TEST", "TEST_MASTER.csv",
     "lower(test_name|test_parameter|method_standard|clause)",
     "A distinct test / test parameter with its method."),
    ("LABORATORY", "LAB", "LAB_MASTER.csv", "lab_code | else lower(lab_name)",
     "BIS-recognized / LIMS laboratory."),
    ("DOCUMENT", "DOC", "DOCUMENT_MASTER.csv", "sha256 | else normalized URL",
     "Retrievable artefact: gazette PDF, manual, circular, order, web page."),
    ("FAQ", "FAQ", "FAQ_MASTER.csv", "sha1-16(lower(question))",
     "Published question/answer pair."),
    ("NOTIFICATION", "NOTIF", "NOTIFICATION_MASTER.csv",
     "notification_number+date | else lower(title)",
     "Gazette / BIS notification. notification_type keeps sources distinct."),
    ("LEGAL", "LEGAL", "LEGAL_MASTER.csv", "instrument_number | else lower(title)",
     "Act/Rule/Regulation/Circular/Order. legal_instrument_type discriminates."),
    ("HALLMARKING", "HM", "HALLMARKING_MASTER.csv", "centre_code | else name+city",
     "Assaying & Hallmarking Centre / jeweller-registration entity."),
    ("FMCS", "FMCS", "FMCS_MASTER.csv", "cml_licence_no | else manufacturer+country",
     "Foreign Manufacturer Certification Scheme licence holder."),
]
ENT = [e[0] for e in ENTITIES]
PREFIX = {e[0]: e[1] for e in ENTITIES}
MASTER = {e[0]: e[2] for e in ENTITIES}

# Non-entity canonical outputs that still must exist (aggregates, EAV, registers).
AUX_DATASETS = [
    ("ENTITY_ATTRIBUTES", "00_MASTER/ENTITY_ATTRIBUTES.csv",
     "Long-format lossless store for narrative/singleton columns that do not belong "
     "in any master. Guarantees zero column loss without a 290-column sparse table."),
    ("LAB_SCOPE", "00_MASTER/LAB_SCOPE.csv", "One row per lab x IS x test capability."),
    ("FMCS_COUNTRY_COVERAGE", "00_MASTER/FMCS_COUNTRY_COVERAGE.csv",
     "Aggregate counts per country - statistics, NOT licence-holder entities."),
    ("FMCS_IS_COVERAGE", "00_MASTER/FMCS_IS_COVERAGE.csv",
     "Aggregate counts per IS - statistics, NOT licence-holder entities."),
    ("PRODUCT_MANUAL_REQUIREMENTS", "00_MASTER/PRODUCT_MANUAL_REQUIREMENTS.csv", "3N"),
    ("PRODUCT_MANUAL_TESTING", "00_MASTER/PRODUCT_MANUAL_TESTING.csv", "3N"),
    ("PRODUCT_MANUAL_SAMPLING", "00_MASTER/PRODUCT_MANUAL_SAMPLING.csv", "3N"),
    ("PRODUCT_MANUAL_INFRASTRUCTURE", "00_MASTER/PRODUCT_MANUAL_INFRASTRUCTURE.csv", "3N"),
    ("PRODUCT_MANUAL_MARKING", "00_MASTER/PRODUCT_MANUAL_MARKING.csv", "3N"),
    ("IS_COMPLETE_MASTER", "00_MASTER/IS_COMPLETE_MASTER.xlsx",
     "3M wide view: one logical row per canonical IS, lists kept as counts + ids."),
    ("RECORD_PROVENANCE", "91_PROVENANCE/RECORD_PROVENANCE.csv", "3P"),
    ("SOURCE_FILE_PROVENANCE", "91_PROVENANCE/SOURCE_FILE_PROVENANCE.csv", "3P"),
    ("DOCUMENT_PROVENANCE", "91_PROVENANCE/DOCUMENT_PROVENANCE.csv", "3P"),
    ("CONFLICT_REGISTER", "92_VALIDATION/CONFLICT_STATUS.csv", "3I"),
    ("REVIEW_QUEUE", "92_VALIDATION/REQUIRES_REVIEW.csv",
     "Records whose evidence did not settle - never silently dropped."),
    ("EXTRACTION_LOG", "93_OPERATIONAL/EXTRACTION_LOG.csv",
     "Scrape/extraction telemetry preserved verbatim; not a domain entity."),
]

# ------------------------------------------------------------ file routing (3A/3G)
# file_id -> (primary_target, merge_step, role, secondary_targets)
# primary_target is where the file's ROWS become records; secondary_targets receive
# relationship rows or attributes derived from the same rows. Confirmed against the
# measured 685-column inventory, not against filenames.
ROUTE = {
    "F001": ("STANDARD", "MS-11", "SCHEME_II_CRS_STANDARD_LISTING",
             "SCHEME;PRODUCT;NOTIFICATION"),
    "F002": ("STANDARD", "MS-11", "SCHEME_IV_COC_STANDARD_LISTING",
             "SCHEME;PRODUCT;NOTIFICATION"),
    "F003": ("STANDARD", "MS-11", "SCHEME_X_STANDARD_LISTING",
             "SCHEME;PRODUCT;NOTIFICATION;DOCUMENT"),
    "F004": ("CONFLICT_REGISTER", "MS-14", "PRE_EXISTING_SOURCE_CONFLICT_LOG", ""),
    "F005": ("TEST", "MS-13", "TEST_METHOD_MASTER", "STANDARD"),
    "F006": ("FAQ", "MS-03", "GENERAL_FAQ", "STANDARD;PRODUCT;QCO;SCHEME"),
    "F007": ("LAB_SCOPE", "MS-07", "LAB_TESTING_SCOPE", "LABORATORY;TEST;STANDARD"),
    "F008": ("LEGAL", "MS-06", "MANDATORY_HALLMARKING_ORDER", "DOCUMENT"),
    "F009": ("NOTIFICATION", "MS-08", "BIS_NOTIFICATION_MASTER",
             "STANDARD;QCO;DOCUMENT"),
    "F010": ("PRODUCT_MANUAL", "MS-02", "PRODUCT_MANUAL_MASTER",
             "STANDARD;PRODUCT;SCHEME;DOCUMENT"),
    "F011": ("PRODUCT", "MS-09", "PRODUCT_DETAILS", "STANDARD;QCO;SCHEME"),
    "F012": ("PRODUCT", "MS-09", "PRODUCT_FULL_INFO_SUPERSEDED_BY_F013",
             "STANDARD;QCO;SCHEME"),
    "F013": ("PRODUCT", "MS-09", "PRODUCT_FULL_INFO_REPAIRED",
             "STANDARD;QCO;SCHEME"),
    "F014": ("QCO", "MS-10", "QCO_SCHEMA_2", "STANDARD;PRODUCT;SCHEME;DOCUMENT"),
    "F015": ("QCO", "MS-10", "QCO_MASTER_RECORDS", "STANDARD;PRODUCT;SCHEME;DOCUMENT"),
    "F016": ("QCO", "MS-10", "QCO_MASTER_RECORDS_V3",
             "STANDARD;PRODUCT;SCHEME;DOCUMENT"),
    "F017": ("QCO", "MS-10", "QCO_MASTER_SCHEME_1",
             "STANDARD;PRODUCT;SCHEME;DOCUMENT"),
    "F018": ("QCO", "MS-10", "QCO_PRODUCTS_LIST", "STANDARD;PRODUCT;NOTIFICATION"),
    "F019": ("QCO", "MS-10", "QCO_SUMMARY_COMPOSITE_COLUMNS",
             "STANDARD;NOTIFICATION;DOCUMENT"),
    "F020": ("LABORATORY", "MS-07", "RECOGNIZED_LABORATORIES", "DOCUMENT"),
    "F021": ("SCHEME", "MS-04", "SCHEME_IV_FMCS_GUIDANCE",
             "STANDARD;PRODUCT;QCO;PRODUCT_MANUAL"),
    "F022": ("SCHEME", "MS-11", "SCHEME_X_INDUSTRIAL",
             "STANDARD;PRODUCT;QCO;PRODUCT_MANUAL"),
    "F023": ("SCHEME", "MS-11", "SCHEME_X_INDUSTRIAL_V2_IDENTICAL_MULTISET",
             "STANDARD;PRODUCT;QCO;PRODUCT_MANUAL"),
    "F024": ("SCHEME", "MS-11", "SCHEMES_MASTER",
             "STANDARD;PRODUCT;QCO;PRODUCT_MANUAL"),
    "F025": ("SCHEME", "MS-11", "SCHEMES_MASTER_SCHEME_2_DIFFERENT_ENTITY",
             "STANDARD;PRODUCT;QCO;PRODUCT_MANUAL"),
    "F026": ("STANDARD", "MS-12", "STANDARD_AMENDMENT_RELATION", "DOCUMENT"),
    "F027": ("STANDARD", "MS-12", "STANDARDS_DETAILS_V2_BYTE_TWIN", "DOCUMENT"),
    "F028": ("STANDARD", "MS-12", "STANDARDS_DETAILS_V2_SUPERSEDED_BY_F029",
             "DOCUMENT"),
    "F029": ("STANDARD", "MS-12", "STANDARDS_DETAILS_V3_ENRICHED", "DOCUMENT"),
    "F030": ("STANDARD", "MS-09", "CERTIFICATION_GUIDANCE_BY_PRODUCT_SCHEME",
             "SCHEME;PRODUCT"),
    "F031": ("STANDARD", "MS-09", "CERTIFICATION_GUIDANCE_BY_GROUP_STORE_SCHEME",
             "SCHEME;PRODUCT"),
    "F032": ("TEST", "MS-13", "TESTING_PARAMETERS", "STANDARD;PRODUCT;DOCUMENT"),
    "F033": ("LEGAL", "MS-08", "BIS_CIRCULAR", "STANDARD;DOCUMENT"),
    "F034": ("NOTIFICATION", "MS-08", "GAZETTE_NOTIFICATION_INDEX", "STANDARD"),
    "F035": ("LABORATORY", "MS-07", "LIMS_LABORATORIES", "STANDARD"),
    "F036": ("FAQ", "MS-03", "PRODUCT_CERTIFICATION_FAQ", "STANDARD;PRODUCT;SCHEME"),
    "F037": ("SCHEME", "MS-01", "PRODUCT_CERTIFICATION_GUIDELINES", "DOCUMENT"),
    "F038": ("HALLMARKING", "MS-05", "HALLMARKING_CENTRES_ACTIVE", ""),
    "F039": ("HALLMARKING", "MS-05", "HALLMARKING_CENTRES_CANCELLED_SUSPENDED", ""),
    "F040": ("FMCS", "MS-04", "FMCS_LICENCE_LIST_RAW", "STANDARD"),
    "F041": ("EXTRACTION_LOG", "MS-14", "EXTRACTION_TELEMETRY", ""),
    "F042": ("FMCS_COUNTRY_COVERAGE", "MS-04", "FMCS_AGGREGATE_BY_COUNTRY", ""),
    "F043": ("FMCS_IS_COVERAGE", "MS-04", "FMCS_AGGREGATE_BY_IS", "STANDARD"),
    "F044": ("DOCUMENT", "MS-14", "HTTP_SOURCE_INVENTORY", ""),
    "F045": ("FMCS", "MS-04", "FMCS_MANUFACTURERS_PARSED", "STANDARD;PRODUCT"),
    "F046": ("DOCUMENT", "MS-04", "OFFICIAL_DOCUMENT_REGISTRY",
             "STANDARD;PRODUCT;SCHEME;QCO"),
    "F047": ("RECORD_PROVENANCE", "MS-14", "FIELD_LEVEL_PROVENANCE_EAV", "DOCUMENT"),
    "F048": ("REVIEW_QUEUE", "MS-14", "UNRESOLVED_SOURCE_RECORDS", ""),
    "F049": ("DOCUMENT", "-", "SIH_PROBLEM_STATEMENT_REFERENCE_PDF", ""),
}
ARCHIVE_AFTER_VALIDATION = ("F012", "F023", "F027", "F028")   # Phase 2, 3H
PENDING_REVIEW = ("F005", "F019", "F037", "F044", "F047")     # Phase 2

# ------------------------------------------------------- canonical master schemas
# Provenance/audit tail carried by EVERY master row (3P, 3T, zero-data-loss rule).
TAIL = ["source_file_count", "source_file_ids", "source_files", "source_sheets",
        "source_rows", "record_disposition", "conflict_count", "conflict_fields",
        "review_flag", "review_reason", "populated_field_count", "completeness_pct"]

MASTER_COLS = {
    "STANDARD": [
        "is_id", "canonical_is_number", "display_is_number", "raw_is_number_variants",
        "standard_number", "standard_year", "part_number", "section_number",
        "amendment_reference", "iec_reference", "part_source", "is_iec_flag",
        "title", "title_vernacular", "standard_scope", "part_section_label",
        "revision", "version", "publication_date", "publication_date_precision",
        "revision_date", "reaffirmation_review_date", "standard_status",
        "standard_status_original", "superseded_standard", "superseding_standard",
        "technical_committee", "subcommittee", "product_category",
        "degree_of_equivalence", "mandatory_voluntary", "certification_type",
        "official_url", "document_url", "source_url", "source_reference_label",
        "parse_status"],
    "PRODUCT": [
        "product_id", "product_name", "alternate_names", "product_category",
        "product_subcategory", "product_description", "keywords", "product_group",
        "certification_scheme_to_store", "source_product_ids", "source_url",
        "source_reference_label"],
    "QCO": [
        "qco_id", "qco_name", "qco_number", "qco_number_normalized",
        "qco_product_text", "notification_number", "notification_date",
        "notification_date_precision", "effective_date", "effective_date_precision",
        "ministry", "department", "mandatory_status", "mandatory_status_original",
        "qco_scope", "qco_exclusions", "qco_exemptions", "qco_amendments",
        "qco_extensions", "qco_deferments", "qco_corrigendas", "qco_supersession",
        "qco_status", "qco_status_original",
        "qco_scope_exclusions_amendments_combined", "qco_schemes_text",
        "official_document_url", "source_gazette_url", "source_url",
        "source_reference_label", "source_qco_ids"],
    "SCHEME": [
        "scheme_id", "scheme_name", "scheme_code", "scheme_label", "scheme_type",
        "certification_type", "mandatory_voluntary", "mandatory_voluntary_original",
        "certification_scope", "certification_requirements", "fmcs_requirements",
        "guideline_title", "applicability", "application_procedure", "fee_structure",
        "inspection_testing_norm", "document_url", "source_url",
        "source_reference_label", "source_scheme_ids", "source_scheme_record_ids"],
    "PRODUCT_MANUAL": [
        "pm_id", "manual_title", "manual_version", "revision_date",
        "revision_date_precision", "document_scope", "pm_scheme_text", "is_id",
        "canonical_is_number", "product_id", "product_name", "document_id",
        "document_url", "source_url", "source_reference_label", "source_manual_ids"],
    "TEST": [
        "test_id", "test_name", "test_parameter", "test_method",
        "test_method_standard", "method_standard_is_id", "clause", "sample_size",
        "sampling_frequency", "test_frequency", "acceptance_criteria",
        "required_equipment", "laboratory_requirement", "rejection_handling",
        "remarks", "source_document", "source_page", "source_url",
        "source_reference_label", "source_test_ids"],
    "LABORATORY": [
        "lab_id", "lab_name", "lab_code", "lab_type", "address", "city", "district",
        "state", "pin", "contact_person", "contact_number", "email",
        "contact_details", "recognition_status", "recognition_status_original",
        "validity", "validity_date", "accreditation_validity", "scope_url",
        "source_url", "source_reference_label", "source_lab_ids"],
    "DOCUMENT": [
        "document_id", "document_type", "title", "is_id", "canonical_is_number",
        "product_id", "scheme_id", "qco_id", "version", "publication_date",
        "effective_date", "source_url", "download_url", "local_path", "sha256",
        "access_type", "parser_status", "retrieved_at", "page_count", "http_status",
        "content_type", "bytes", "last_modified", "dedup_status",
        "license_access_restriction", "source_reference_label",
        "source_document_ids"],
    "FAQ": [
        "faq_id", "question", "answer", "faq_category", "related_is_text",
        "related_product_text", "related_qco_text", "related_scheme_text",
        "document_reference", "source_url", "source_reference_label",
        "source_faq_ids"],
    "NOTIFICATION": [
        "notification_id", "notification_type", "notification_number",
        "notification_number_normalized", "title", "title_vernacular",
        "notification_category", "notification_date", "effective_date", "ministry",
        "department", "subject", "related_is_text", "related_qco_text",
        "related_amendment_text", "document_url", "source_url",
        "source_reference_label", "source_notification_ids"],
    "LEGAL": [
        "legal_id", "legal_instrument_type", "instrument_number",
        "instrument_number_normalized", "title", "issuing_authority", "ministry",
        "release_date", "effective_date", "subject", "metal", "fineness",
        "mandatory_status", "mandatory_status_original",
        "geographical_applicability", "district_phase", "amendment", "exemption",
        "supersession", "implementation_instructions", "related_is_text",
        "document_url", "source_url", "source_reference_label", "source_legal_ids"],
    "HALLMARKING": [
        "hm_id", "centre_name", "centre_code", "hallmarking_entity_type", "address",
        "city", "district", "state", "pin", "recognition_status",
        "recognition_status_original", "recognition_status_raw", "validity",
        "validity_date", "suspended_cancelled_date", "region", "centre_type",
        "hallmarking_scope", "services", "source_url", "source_reference_label",
        "source_centre_ids"],
    "FMCS": [
        "fmcs_id", "manufacturer_name", "country", "factory", "cml_licence_no",
        "licence", "licence_status", "licence_status_original", "validity_date",
        "is_id", "canonical_is_number", "fmcs_product", "variety_brand",
        "name_address_raw", "fmcs_eligibility", "machinery_requirements",
        "testing_facilities", "competent_personnel", "air_requirements",
        "application_requirements", "fees", "fmcs_documents", "source_url",
        "source_reference_label", "source_fmcs_ids"],
}
for _e in MASTER_COLS:
    MASTER_COLS[_e] = MASTER_COLS[_e] + TAIL

# ------------------------------------------------- column semantics (3D) - part 1/3
# normalized_source_column -> (canonical_column, semantic_type, merge_action, transform)
# Resolution order at build time: FILE_OVERRIDE -> (entity, column) -> CMAP -> attribute.
# `transform` names a p3_lib function; `verbatim` means the cell is copied unchanged.
CMAP = {
    # --- IS / standard identity -------------------------------------------------
    "is_number": ("canonical_is_number", "IS_REFERENCE", "KEY_IDENTITY", "nis"),
    "is": ("canonical_is_number", "IS_REFERENCE", "KEY_IDENTITY", "nis"),
    "canonical_is_number": ("canonical_is_number", "IS_REFERENCE", "KEY_IDENTITY",
                            "nis"),
    "display_is_number": ("display_is_number", "IS_REFERENCE", "UNION_COALESCE",
                          "nis"),
    "raw_is_number": ("raw_is_number_variants", "IS_REFERENCE",
                      "UNION_APPEND_DISTINCT", "verbatim"),
    "standard_year": ("standard_year", "NUMBER", "UNION_COALESCE", "nws"),
    "year": ("standard_year", "NUMBER", "UNION_COALESCE", "nws"),
    "part_section": ("part_section_label", "CODE", "UNION_COALESCE", "nws"),
    "revision": ("revision", "TEXT", "UNION_COALESCE", "nws"),
    "reaffirmation_review_date": ("reaffirmation_review_date", "DATE",
                                  "UNION_COALESCE", "ndate"),
    "technical_committee": ("technical_committee", "NAME", "UNION_COALESCE", "nname"),
    "subcommittee": ("subcommittee", "NAME", "UNION_COALESCE", "nname"),
    "degree_of_equivalence": ("degree_of_equivalence", "ENUM", "UNION_COALESCE",
                              "nws"),
    "superseded_standard": ("superseded_standard", "IS_REFERENCE",
                            "EXPLODE_TO_RELATIONSHIP", "is_all"),
    "superseding_standard": ("superseding_standard", "IS_REFERENCE",
                             "EXPLODE_TO_RELATIONSHIP", "is_all"),
    "official_url": ("official_url", "URL", "UNION_COALESCE", "nurl"),
    # --- multi-value list columns: exploded, never left as the only representation
    "is_numbers": ("related_is_text", "LIST", "EXPLODE_TO_RELATIONSHIP",
                   "msplit+is_all"),
    "related_is_numbers": ("related_is_text", "LIST", "EXPLODE_TO_RELATIONSHIP",
                           "msplit+is_all"),
    "related_is": ("related_is_text", "LIST", "EXPLODE_TO_RELATIONSHIP",
                   "msplit+is_all"),
    "tested_is_numbers": ("related_is_text", "LIST", "EXPLODE_TO_RELATIONSHIP",
                          "msplit+is_all"),
    "related_qcos": ("related_qco_text", "LIST", "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "related_qco": ("related_qco_text", "LIST", "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "related_schemes": ("related_scheme_text", "LIST", "EXPLODE_TO_RELATIONSHIP",
                        "msplit"),
    "related_scheme": ("related_scheme_text", "LIST", "EXPLODE_TO_RELATIONSHIP",
                       "msplit"),
    "related_product": ("related_product_text", "LIST", "EXPLODE_TO_RELATIONSHIP",
                        "msplit"),
    "related_product_manual": ("related_product_manual_text", "LIST",
                               "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "related_sit": ("related_sit_text", "LIST", "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "related_amendment": ("related_amendment_text", "LIST",
                          "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "amendments": ("qco_amendments", "LIST", "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "schemes": ("qco_schemes_text", "LIST", "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "keywords": ("keywords", "LIST", "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "alternate_names": ("alternate_names", "LIST", "EXPLODE_TO_RELATIONSHIP",
                        "msplit"),
}

# ------------------------------------------------- column semantics (3D) - part 2/3
CMAP.update({
    # --- names, titles, prose ---------------------------------------------------
    "title": ("title", "TITLE", "UNION_LONGEST", "nname"),
    "product_name": ("product_name", "NAME", "KEY_IDENTITY", "nname"),
    "product": ("product_name", "NAME", "KEY_IDENTITY", "nname"),
    "category": ("product_category", "ENUM", "UNION_COALESCE", "nname"),
    "subcategory": ("product_subcategory", "ENUM", "UNION_COALESCE", "nname"),
    "product_category": ("product_category", "ENUM", "UNION_COALESCE", "nname"),
    "description": ("product_description", "NARRATIVE", "UNION_LONGEST", "nws"),
    "subject": ("subject", "NARRATIVE", "UNION_LONGEST", "nws"),
    "notes": ("notes", "NARRATIVE", "UNION_APPEND_DISTINCT", "nws"),
    "remarks": ("remarks", "NARRATIVE", "UNION_APPEND_DISTINCT", "nws"),
    # --- QCO --------------------------------------------------------------------
    "qco_name": ("qco_name", "NAME", "KEY_IDENTITY", "nname"),
    "qco_number": ("qco_number", "CODE", "KEY_IDENTITY", "nqco"),
    "qco_order": ("qco_number", "CODE", "KEY_IDENTITY", "nqco"),
    "qco": ("related_qco_text", "LIST", "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "exclusions": ("qco_exclusions", "NARRATIVE", "PRESERVE_BOTH_ON_CONFLICT", "nws"),
    "exemptions": ("qco_exemptions", "NARRATIVE", "PRESERVE_BOTH_ON_CONFLICT", "nws"),
    "extensions": ("qco_extensions", "NARRATIVE", "UNION_LONGEST", "nws"),
    "deferments": ("qco_deferments", "NARRATIVE", "UNION_LONGEST", "nws"),
    "corrigendas": ("qco_corrigendas", "NARRATIVE", "UNION_LONGEST", "nws"),
    "supersession": ("qco_supersession", "NARRATIVE", "UNION_LONGEST", "nws"),
    "amendments_extensions": ("qco_amendments", "NARRATIVE",
                              "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "official_document_url": ("official_document_url", "URL", "UNION_COALESCE",
                              "nurl"),
    "source_gazette_url": ("source_gazette_url", "URL", "UNION_COALESCE", "nurl"),
    # --- scheme -----------------------------------------------------------------
    "scheme_name": ("scheme_name", "NAME", "KEY_IDENTITY", "nname"),
    "scheme_code": ("scheme_code", "CODE", "KEY_IDENTITY", "nws"),
    "scheme_id_code": ("scheme_code", "CODE", "KEY_IDENTITY", "nws"),
    "scheme_label": ("scheme_label", "NAME", "UNION_COALESCE", "nname"),
    "scheme_type": ("scheme_type", "ENUM", "UNION_COALESCE", "nname"),
    "certification_type": ("certification_type", "ENUM", "UNION_COALESCE", "nname"),
    "scheme": ("related_scheme_text", "LIST", "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "guideline_title": ("guideline_title", "TITLE", "UNION_LONGEST", "nname"),
    "applicability": ("applicability", "NARRATIVE", "UNION_LONGEST", "nws"),
    "fee_structure": ("fee_structure", "NARRATIVE", "UNION_LONGEST", "nws"),
    "inspection_testing_norm": ("inspection_testing_norm", "NARRATIVE",
                                "UNION_LONGEST", "nws"),
    # --- status / flags ---------------------------------------------------------
    "mandatory_voluntary": ("mandatory_voluntary", "ENUM", "UNION_COALESCE", "nmand"),
    "mandatory_voluntary_status": ("mandatory_voluntary", "ENUM", "UNION_COALESCE",
                                   "nmand"),
    "mandatory_status": ("mandatory_status", "ENUM", "UNION_COALESCE", "nmand"),
    "scheme_status": ("qco_status", "STATUS", "UNION_COALESCE", "nstatus"),
    "status": ("status", "STATUS", "UNION_COALESCE", "nstatus"),
    "recognition_status": ("recognition_status", "STATUS", "PRESERVE_BOTH_ON_CONFLICT",
                           "nstatus"),
    "recognition_status_raw": ("recognition_status_raw", "STATUS", "UNION_COALESCE",
                               "verbatim"),
    "licence_status": ("licence_status", "STATUS", "UNION_COALESCE", "nstatus"),
    "scope_status": ("scope_status", "STATUS", "UNION_COALESCE", "nstatus"),
    "capability": ("capability", "TEXT", "UNION_COALESCE", "nws"),
    "verification_status": ("verification_status", "STATUS", "PROVENANCE_ONLY",
                            "verbatim"),
    "record_status": ("record_status", "STATUS", "PROVENANCE_ONLY", "verbatim"),
    "missing_reason": ("missing_reason", "TEXT", "PROVENANCE_ONLY", "verbatim"),
})

# ------------------------------------------------- column semantics (3D) - part 3/3
CMAP.update({
    # --- dates ------------------------------------------------------------------
    "date": ("notification_date", "DATE", "UNION_COALESCE", "ndate"),
    "notification_date": ("notification_date", "DATE", "UNION_COALESCE", "ndate"),
    "effective_date": ("effective_date", "DATE", "PRESERVE_BOTH_ON_CONFLICT", "ndate"),
    "effective_implementation_date": ("effective_date", "DATE",
                                      "PRESERVE_BOTH_ON_CONFLICT", "ndate"),
    "publication_date": ("publication_date", "DATE", "UNION_COALESCE", "ndate"),
    "revision_date": ("revision_date", "DATE", "UNION_COALESCE", "ndate"),
    "release_date": ("release_date", "DATE", "UNION_COALESCE", "ndate"),
    "amendment_date": ("amendment_date", "DATE", "UNION_COALESCE", "ndate"),
    "suspended_cancelled_date": ("suspended_cancelled_date", "DATE",
                                 "UNION_COALESCE", "ndate"),
    "validity": ("validity", "TEXT", "UNION_COALESCE", "nws"),
    "scope_validity": ("scope_validity", "TEXT", "UNION_COALESCE", "nws"),
    "accreditation_validity": ("accreditation_validity", "TEXT", "UNION_COALESCE",
                               "nws"),
    "last_modified": ("last_modified", "TIMESTAMP", "UNION_COALESCE", "verbatim"),
    "retrieved_at": ("retrieved_at", "TIMESTAMP", "PROVENANCE_ONLY", "verbatim"),
    "retrieval_timestamp": ("retrieved_at", "TIMESTAMP", "PROVENANCE_ONLY",
                            "verbatim"),
    "detected_at": ("detected_at", "TIMESTAMP", "PROVENANCE_ONLY", "verbatim"),
    "timestamp": ("event_timestamp", "TIMESTAMP", "PROVENANCE_ONLY", "verbatim"),
    # --- notification / legal ---------------------------------------------------
    "notification_number": ("notification_number", "CODE", "KEY_IDENTITY", "nnotif"),
    "notification_reference": ("notification_number", "CODE",
                               "EXPLODE_TO_RELATIONSHIP", "nnotif"),
    "notified_by": ("ministry", "NAME", "UNION_COALESCE", "nname"),
    "ministry": ("ministry", "NAME", "PRESERVE_BOTH_ON_CONFLICT", "nname"),
    "department": ("department", "NAME", "UNION_COALESCE", "nname"),
    "issuing_authority": ("issuing_authority", "NAME", "UNION_COALESCE", "nname"),
    "circular_number": ("instrument_number", "CODE", "KEY_IDENTITY", "nnotif"),
    "order_number": ("instrument_number", "CODE", "KEY_IDENTITY", "nqco"),
    "order_title": ("title", "TITLE", "UNION_LONGEST", "nname"),
    "metal": ("metal", "ENUM", "UNION_COALESCE", "nname"),
    "fineness": ("fineness", "TEXT", "UNION_COALESCE", "nws"),
    "geographical_applicability": ("geographical_applicability", "NARRATIVE",
                                   "UNION_LONGEST", "nws"),
    "district_phase": ("district_phase", "NARRATIVE", "UNION_LONGEST", "nws"),
    "amendment": ("amendment", "NARRATIVE", "UNION_LONGEST", "nws"),
    "exemption": ("exemption", "NARRATIVE", "UNION_LONGEST", "nws"),
    "implementation_instructions": ("implementation_instructions", "NARRATIVE",
                                    "UNION_LONGEST", "nws"),
    # --- test -------------------------------------------------------------------
    "test_name": ("test_name", "NAME", "KEY_IDENTITY", "nname"),
    "test_parameter": ("test_parameter", "NAME", "KEY_IDENTITY", "nname"),
    "parameter": ("test_parameter", "NAME", "KEY_IDENTITY", "nname"),
    "test_method": ("test_method", "TEXT", "UNION_COALESCE", "nws"),
    "method": ("test_method", "TEXT", "UNION_COALESCE", "nws"),
    "method_standard": ("test_method_standard", "IS_REFERENCE",
                        "EXPLODE_TO_RELATIONSHIP", "is_all"),
    "test_method_standard": ("test_method_standard", "IS_REFERENCE",
                             "EXPLODE_TO_RELATIONSHIP", "is_all"),
    "clause": ("clause", "CODE", "KEY_IDENTITY", "nws"),
    "sample_size": ("sample_size", "TEXT", "UNION_COALESCE", "nws"),
    "frequency": ("test_frequency", "TEXT", "UNION_COALESCE", "nws"),
    "test_frequency": ("test_frequency", "TEXT", "UNION_COALESCE", "nws"),
    "sampling_frequency": ("sampling_frequency", "TEXT", "UNION_COALESCE", "nws"),
    "acceptance_criteria": ("acceptance_criteria", "NARRATIVE", "UNION_LONGEST",
                            "nws"),
    "required_equipment": ("required_equipment", "NARRATIVE", "UNION_LONGEST", "nws"),
    "laboratory_requirement": ("laboratory_requirement", "NARRATIVE",
                               "UNION_LONGEST", "nws"),
    "rejection_handling": ("rejection_handling", "NARRATIVE", "UNION_LONGEST", "nws"),
    "testing_charge": ("testing_charge", "TEXT", "UNION_COALESCE", "nws"),
})

CMAP.update({
    # --- laboratory / hallmarking centre / address block ------------------------
    "lab_name": ("lab_name", "NAME", "KEY_IDENTITY", "nname"),
    "lab_code": ("lab_code", "CODE", "KEY_IDENTITY", "nws"),
    "lab_type": ("lab_type", "ENUM", "UNION_COALESCE", "nname"),
    "centre_name": ("centre_name", "NAME", "KEY_IDENTITY", "nname"),
    "centre_code": ("centre_code", "CODE", "KEY_IDENTITY", "nws"),
    "centre_type": ("centre_type", "ENUM", "UNION_COALESCE", "nname"),
    "region": ("region", "NAME", "UNION_COALESCE", "nname"),
    "address": ("address", "ADDRESS", "UNION_LONGEST", "nws"),
    "city": ("city", "NAME", "UNION_COALESCE", "nname"),
    "district": ("district", "NAME", "UNION_COALESCE", "nname"),
    "state": ("state", "NAME", "UNION_COALESCE", "nname"),
    "pin": ("pin", "CODE", "UNION_COALESCE", "nws"),
    "contact_person": ("contact_person", "NAME", "UNION_COALESCE", "nname"),
    "contact_number": ("contact_number", "CONTACT", "UNION_APPEND_DISTINCT", "nws"),
    "contact_details": ("contact_details", "CONTACT", "UNION_APPEND_DISTINCT", "nws"),
    "email": ("email", "CONTACT", "UNION_APPEND_DISTINCT", "nws"),
    "services": ("services", "LIST", "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "scope_url": ("scope_url", "URL", "UNION_COALESCE", "nurl"),
    # --- FMCS -------------------------------------------------------------------
    "manufacturer": ("manufacturer_name", "NAME", "KEY_IDENTITY", "nname"),
    "country": ("country", "NAME", "KEY_IDENTITY", "nname"),
    "factory": ("factory", "NAME", "UNION_LONGEST", "nws"),
    "licence": ("licence", "CODE", "KEY_IDENTITY", "nws"),
    "documents": ("fmcs_documents", "LIST", "EXPLODE_TO_RELATIONSHIP", "msplit"),
    "manufacturer_count": ("manufacturer_count", "NUMBER", "UNION_COALESCE", "nws"),
    "licence_count": ("licence_count", "NUMBER", "UNION_COALESCE", "nws"),
    # --- document ---------------------------------------------------------------
    "document_type": ("document_type", "ENUM", "UNION_COALESCE", "nname"),
    "document_title": ("title", "TITLE", "UNION_LONGEST", "nname"),
    "document_url": ("document_url", "URL", "UNION_COALESCE", "nurl"),
    "notification_document_url": ("document_url", "URL", "UNION_COALESCE", "nurl"),
    "download_url": ("download_url", "URL", "UNION_COALESCE", "nurl"),
    "source_document_link": ("document_url", "URL", "UNION_COALESCE", "nurl"),
    "document_reference": ("document_reference", "TEXT", "UNION_COALESCE", "nws"),
    "local_file": ("local_path", "TEXT", "UNION_COALESCE", "verbatim"),
    "sha256": ("sha256", "HASH", "KEY_IDENTITY", "nws"),
    "document_hash": ("sha256", "HASH", "KEY_IDENTITY", "nws"),
    "page_count": ("page_count", "NUMBER", "UNION_COALESCE", "nws"),
    "access_status": ("access_type", "ENUM", "UNION_COALESCE", "nws"),
    "license_access_restriction": ("license_access_restriction", "TEXT",
                                   "UNION_COALESCE", "nws"),
    "http_status": ("http_status", "NUMBER", "UNION_COALESCE", "nws"),
    "content_type": ("content_type", "ENUM", "UNION_COALESCE", "nws"),
    "bytes": ("bytes", "NUMBER", "UNION_COALESCE", "nws"),
    "dedup_status": ("dedup_status", "ENUM", "UNION_COALESCE", "nws"),
    "source_type": ("document_type", "ENUM", "UNION_COALESCE", "nname"),
    "source_title": ("title", "TITLE", "UNION_LONGEST", "nname"),
    "version": ("version", "TEXT", "UNION_COALESCE", "nws"),
    # --- FAQ --------------------------------------------------------------------
    "question": ("question", "TEXT", "KEY_IDENTITY", "nws"),
    "answer": ("answer", "NARRATIVE", "UNION_LONGEST", "nws"),
    # --- provenance columns present in the sources (never treated as domain data)
    "source_url": ("source_url", "URL", "SPLIT_HOMONYM", "nurl"),
    "source_id": ("source_record_id", "IDENTIFIER", "PROVENANCE_ONLY", "verbatim"),
    "source_document": ("source_document", "TEXT", "UNION_COALESCE", "nws"),
    "source_page": ("source_page", "NUMBER", "UNION_COALESCE", "nws"),
    "scraper_engine": ("scraper_engine", "TEXT", "PROVENANCE_ONLY", "verbatim"),
    "extraction_method": ("extraction_method", "TEXT", "PROVENANCE_ONLY", "verbatim"),
    "sr_no": ("source_row_label", "NUMBER", "PROVENANCE_ONLY", "verbatim"),
    "s_no": ("source_row_label", "NUMBER", "PROVENANCE_ONLY", "verbatim"),
    "id": ("source_record_id", "IDENTIFIER", "DROP_SURROGATE_KEEP_AS_SOURCE_ID",
           "verbatim"),
    "table_caption": ("source_table_caption", "TEXT", "PROVENANCE_ONLY", "verbatim"),
})

# Source-side surrogate keys. They are per-file, collide across files, and carry no
# regulatory meaning, so they must NOT become canonical ids - but they are the only
# handle back to the source row, so every one is retained as a source id.
SURROGATE = {
    "standard_id": "source_standard_ids", "product_id": "source_product_ids",
    "qco_id": "source_qco_ids", "scheme_id": "source_scheme_ids",
    "scheme_record_id": "source_scheme_record_ids", "manual_id": "source_manual_ids",
    "test_id": "source_test_ids", "lab_id": "source_lab_ids",
    "scope_id": "source_scope_ids", "faq_id": "source_faq_ids",
    "notification_id": "source_notification_ids", "circular_id": "source_legal_ids",
    "order_id": "source_legal_ids", "centre_id": "source_centre_ids",
    "amendment_id": "source_amendment_ids", "document_id": "source_document_ids",
    "canonical_document_id": "source_document_ids",
    "manufacturer_id": "source_fmcs_ids", "record_id": "source_record_id",
    "conflict_id": "source_conflict_id",
}
for _k, _v in SURROGATE.items():
    CMAP[_k] = (_v, "IDENTIFIER", "DROP_SURROGATE_KEEP_AS_SOURCE_ID", "verbatim")

# ------------------------------------------------ homonym resolution (3D, 19 columns)
# Phase 2 proved these names carry different meanings in different files. Resolution
# is by (target_entity, column): the same word becomes a different canonical column
# per entity, so no two meanings are ever unioned into one field.
ENTITY_SCOPED = {
    ("PRODUCT_MANUAL", "scope"): ("document_scope", "NARRATIVE", "SPLIT_HOMONYM",
                                  "nws"),
    ("QCO", "scope"): ("qco_scope", "NARRATIVE", "SPLIT_HOMONYM", "nws"),
    ("SCHEME", "scope"): ("certification_scope", "NARRATIVE", "SPLIT_HOMONYM", "nws"),
    ("HALLMARKING", "scope"): ("hallmarking_scope", "NARRATIVE", "SPLIT_HOMONYM",
                               "nws"),
    ("LAB_SCOPE", "scope"): ("assessment_scope", "NARRATIVE", "SPLIT_HOMONYM", "nws"),
    ("STANDARD", "scope"): ("standard_scope", "NARRATIVE", "SPLIT_HOMONYM", "nws"),
    ("DOCUMENT", "scope"): ("document_scope", "NARRATIVE", "SPLIT_HOMONYM", "nws"),
    ("QCO", "current_status"): ("qco_status", "STATUS", "SPLIT_HOMONYM", "nstatus"),
    ("STANDARD", "current_status"): ("standard_status", "STATUS", "SPLIT_HOMONYM",
                                     "nstatus"),
    ("STANDARD", "status"): ("standard_status", "STATUS", "SPLIT_HOMONYM", "nstatus"),
    ("STANDARD", "title"): ("title", "TITLE", "UNION_LONGEST", "nname"),
    ("SCHEME", "requirements"): ("certification_requirements", "NARRATIVE",
                                 "SPLIT_HOMONYM", "nws"),
    ("SCHEME", "product"): ("related_product_text", "LIST",
                            "EXPLODE_TO_RELATIONSHIP", "msplit"),
    ("QCO", "product"): ("qco_product_text", "LIST", "EXPLODE_TO_RELATIONSHIP",
                         "msplit"),
    ("FMCS", "product"): ("fmcs_product", "NAME", "UNION_COALESCE", "nname"),
    ("FMCS", "eligibility"): ("fmcs_eligibility", "NARRATIVE", "SPLIT_HOMONYM", "nws"),
    ("FMCS", "fees"): ("fees", "NARRATIVE", "UNION_LONGEST", "nws"),
    ("FMCS", "air"): ("air_requirements", "NARRATIVE", "UNION_LONGEST", "nws"),
    ("FMCS", "application_requirements"): ("application_requirements", "NARRATIVE",
                                           "UNION_LONGEST", "nws"),
    ("FMCS", "machinery_requirements"): ("machinery_requirements", "NARRATIVE",
                                         "UNION_LONGEST", "nws"),
    ("FMCS", "testing_facilities"): ("testing_facilities", "NARRATIVE",
                                     "UNION_LONGEST", "nws"),
    ("FMCS", "competent_personnel"): ("competent_personnel", "NARRATIVE",
                                      "UNION_LONGEST", "nws"),
    ("LEGAL", "mandatory_status"): ("mandatory_status", "ENUM", "UNION_COALESCE",
                                    "nmand"),
    ("LABORATORY", "recognition_status"): ("recognition_status", "STATUS",
                                           "PRESERVE_BOTH_ON_CONFLICT", "nstatus"),
    ("HALLMARKING", "recognition_status"): ("recognition_status", "STATUS",
                                            "PRESERVE_BOTH_ON_CONFLICT", "nstatus"),
    ("NOTIFICATION", "type"): ("notification_category", "ENUM", "UNION_COALESCE",
                               "nname"),
}

# --------------------------------------------------- per-file overrides (3D highest)
# Keyed (file_id, normalized_column) -> (canonical_column, semantic_type, merge_action,
# transform, target). `target` empty means "the file's primary entity"; otherwise the
# column is routed to that dataset instead. Column names below were read from
# COLUMN_PROFILING.csv, never remembered.
FILE_OVERRIDE = {}

# F019 BIS_QCO_Summary - every column is a composite of 2-3 facts.
FILE_OVERRIDE.update({
    ("F019", "product_standard_is"): ("qco_product_standard_composite", "TEXT",
                                      "DECOMPOSE_COMPOSITE", "split_is_and_product", ""),
    ("F019", "qco_name_identifier"): ("qco_name", "NAME", "UNION_LONGEST", "nname", ""),
    ("F019", "notification_no_date"): ("qco_number_date_composite", "TEXT",
                                       "DECOMPOSE_COMPOSITE", "split_no_and_date", ""),
    ("F019", "ministry_department"): ("ministry", "NAME",
                                      "PRESERVE_BOTH_ON_CONFLICT", "nname", ""),
    ("F019", "scheme_status"): ("qco_status", "STATUS", "SPLIT_HOMONYM", "nstatus", ""),
    ("F019", "key_scope_exclusions_amendments"): (
        "qco_scope_exclusions_amendments_composite", "NARRATIVE",
        "DECOMPOSE_COMPOSITE", "split_scope_excl_amend", ""),
    ("F019", "source_document_link"): ("source_url", "URL", "SPLIT_HOMONYM", "nurl", ""),
})

# F040 raw FMCS scrape - the `*_raw` columns are the authoritative original_value
# source for the parsed twin F045; they are normalised but never discarded.
FILE_OVERRIDE.update({
    ("F040", "s_no"): ("source_row_ordinal", "NUMBER", "PROVENANCE_ONLY", "verbatim", ""),
    ("F040", "cml_no_raw"): ("cml_licence_no", "CODE", "KEY_IDENTITY", "nlic", ""),
    ("F040", "name_address_raw"): ("manufacturer_name_address_composite", "TEXT",
                                   "DECOMPOSE_COMPOSITE", "split_name_address", ""),
    ("F040", "validity_date_raw"): ("licence_validity_date", "DATE",
                                    "PRESERVE_BOTH_ON_CONFLICT", "ndate", ""),
    ("F040", "standard_no_raw"): ("licensed_is_text", "LIST",
                                  "EXPLODE_TO_RELATIONSHIP", "msplit+is_all", ""),
    ("F040", "status_raw"): ("licence_status", "STATUS",
                             "PRESERVE_BOTH_ON_CONFLICT", "nstatus", ""),
    ("F040", "variety_brand_raw"): ("variety_brand", "TEXT", "UNION_LONGEST", "nws", ""),
    ("F040", "retrieved_at"): ("retrieved_at", "TIMESTAMP", "PROVENANCE_ONLY", "ndate", ""),
})

# F030 / F031 - 19 identically-named certification-guidance columns whose VALUES are
# keyed differently: F030 is guidance per (IS, product, scheme), F031 per (IS, group,
# scheme-to-store). Phase 2 flagged 9 of them as homonyms. Unioning them would merge
# two different guidance regimes, so each becomes an ENTITY_ATTRIBUTES row carrying a
# context tag; nothing is dropped and nothing is co-mingled.
GUIDANCE = ["eligibility", "application_procedure", "required_documents",
            "factory_requirements", "infrastructure_requirements", "process_controls",
            "quality_control", "testing", "inspection", "laboratory_testing",
            "conformity_assessment", "licence_or_coc_grant", "surveillance", "renewal",
            "scope_extension", "retesting", "fees", "forms"]
ATTR_CONTEXT = {"F030": "PRODUCT_SCHEME_GUIDANCE", "F031": "GROUP_STORE_SCHEME_GUIDANCE",
                "F021": "FMCS", "F024": "SCHEME_X", "F025": "SCHEMES_MASTER_SCHEME_2"}
for _f in ("F030", "F031"):
    for _c in GUIDANCE:
        FILE_OVERRIDE[(_f, _c)] = (_c, "NARRATIVE", "PRESERVE_AS_ATTRIBUTE", "nws",
                                   "ENTITY_ATTRIBUTES")
    # `timelines` (F030) and `timeliness` (F031) are the same fact, spelled differently.
    FILE_OVERRIDE[(_f, "timelines" if _f == "F030" else "timeliness")] = (
        "timelines", "NARRATIVE", "PRESERVE_AS_ATTRIBUTE", "nws", "ENTITY_ATTRIBUTES")
FILE_OVERRIDE.update({
    ("F030", "product"): ("related_product_text", "LIST", "EXPLODE_TO_RELATIONSHIP",
                          "msplit", ""),
    ("F030", "scheme"): ("related_scheme_text", "LIST", "EXPLODE_TO_RELATIONSHIP",
                         "msplit", ""),
    ("F031", "group"): ("product_group", "NAME", "UNION_COALESCE", "nname", ""),
    ("F031", "certification_scheme_to_store"): ("related_scheme_text", "LIST",
                                                "EXPLODE_TO_RELATIONSHIP", "msplit", ""),
})

# F034 gazette index - `unnamed_3` is untitled Devanagari/English notification text,
# not a stray column; it is preserved as vernacular title, never discarded as noise.
FILE_OVERRIDE.update({
    ("F034", "related_is"): ("related_is_text", "LIST", "EXPLODE_TO_RELATIONSHIP",
                             "msplit+is_all", ""),
    ("F034", "title"): ("notification_title", "TITLE", "UNION_LONGEST", "nname", ""),
    ("F034", "unnamed_3"): ("title_vernacular", "TEXT", "UNION_LONGEST", "nws", ""),
})

# F026 standards amendments - one row per amendment event, so it drives IS_AMENDMENTS
# and never overwrites the parent standard's own identity fields.
FILE_OVERRIDE.update({
    ("F026", "parent_entity"): ("canonical_is_number", "IS_REFERENCE", "KEY_IDENTITY",
                                "nis", ""),
    ("F026", "original_version"): ("amended_from_version", "TEXT", "UNION_COALESCE",
                                   "nws", "IS_AMENDMENTS"),
    ("F026", "new_version"): ("amended_to_version", "TEXT", "UNION_COALESCE", "nws",
                              "IS_AMENDMENTS"),
    ("F026", "amendment_number"): ("amendment_reference", "CODE", "KEY_IDENTITY",
                                   "nname", "IS_AMENDMENTS"),
    ("F026", "amendment_date"): ("amendment_date", "DATE", "UNION_COALESCE", "ndate",
                                 "IS_AMENDMENTS"),
    ("F026", "status"): ("amendment_status", "STATUS", "UNION_COALESCE", "nstatus",
                         "IS_AMENDMENTS"),
})

# F007 laboratory scopes - a lab x IS x test capability grid. `scope` here means
# assessment scope, not product scope; `test_method` is a method reference, not a test.
FILE_OVERRIDE.update({
    ("F007", "is_number"): ("canonical_is_number", "IS_REFERENCE", "KEY_IDENTITY",
                            "nis", ""),
    ("F007", "product"): ("product_name", "NAME", "UNION_COALESCE", "nname", ""),
    ("F007", "test_name"): ("test_name", "NAME", "KEY_IDENTITY", "nname", ""),
    ("F007", "test_method"): ("test_method_standard", "IS_REFERENCE",
                              "EXPLODE_TO_RELATIONSHIP", "is_all", ""),
    ("F007", "clause"): ("clause_reference", "CODE", "UNION_COALESCE", "nws", ""),
    ("F007", "capability"): ("capability", "TEXT", "UNION_COALESCE", "nws", ""),
    ("F007", "scope_status"): ("scope_status", "STATUS", "UNION_COALESCE", "nstatus", ""),
    ("F007", "scope_validity"): ("scope_validity", "TEXT", "UNION_COALESCE", "nws", ""),
    ("F007", "testing_charge"): ("testing_charge", "TEXT", "UNION_COALESCE", "nws", ""),
})

# Meta / operational files. These are NOT domain entities; forcing them into a master
# would invent regulatory records, so each keeps its own shape and disposition.
FILE_OVERRIDE.update({
    ("F004", "entity_key"): ("entity_key", "IDENTIFIER", "KEY_IDENTITY", "nws", ""),
    ("F004", "field_name"): ("field", "IDENTIFIER", "KEY_IDENTITY", "norm_header", ""),
    ("F004", "value_a"): ("value_a", "TEXT", "PRESERVE_BOTH_ON_CONFLICT", "verbatim", ""),
    ("F004", "value_b"): ("value_b", "TEXT", "PRESERVE_BOTH_ON_CONFLICT", "verbatim", ""),
    ("F004", "source_a_id"): ("source_a", "IDENTIFIER", "PROVENANCE_ONLY", "verbatim", ""),
    ("F004", "source_b_id"): ("source_b", "IDENTIFIER", "PROVENANCE_ONLY", "verbatim", ""),
    ("F004", "source_a_url"): ("source_a_url", "URL", "PROVENANCE_ONLY", "nurl", ""),
    ("F004", "source_b_url"): ("source_b_url", "URL", "PROVENANCE_ONLY", "nurl", ""),
    ("F004", "resolution_rule"): ("resolution_reason", "TEXT", "UNION_COALESCE",
                                  "nws", ""),
    # A pre-existing resolved_value from the scraper is EVIDENCE, not authority: it is
    # recorded as source_proposed_value and never promoted to canonical_value.
    ("F004", "resolved_value"): ("source_proposed_value", "TEXT",
                                 "PRESERVE_BOTH_ON_CONFLICT", "verbatim", ""),
    ("F004", "detected_at"): ("detected_at", "TIMESTAMP", "PROVENANCE_ONLY", "ndate", ""),
    ("F042", "country"): ("country", "NAME", "KEY_IDENTITY", "nname", ""),
    ("F043", "is_number"): ("canonical_is_number", "IS_REFERENCE", "KEY_IDENTITY",
                            "nis", ""),
    ("F044", "url"): ("source_url", "URL", "KEY_IDENTITY", "nurl", ""),
    ("F044", "source_title"): ("title", "TITLE", "UNION_LONGEST", "nname", ""),
    ("F044", "dedup_status"): ("dedup_status", "ENUM", "UNION_COALESCE", "nws", ""),
    ("F047", "field_name"): ("original_field", "IDENTIFIER", "KEY_IDENTITY",
                             "norm_header", ""),
    ("F047", "field_value"): ("original_value", "TEXT", "PROVENANCE_ONLY", "verbatim", ""),
    ("F048", "reason"): ("review_reason", "TEXT", "UNION_COALESCE", "nws", ""),
    ("F048", "resolution_needed"): ("resolution_needed", "TEXT", "UNION_COALESCE",
                                    "nws", ""),
    ("F048", "attempted_source_url"): ("source_url", "URL", "PROVENANCE_ONLY", "nurl", ""),
})

# ------------------------------------------------------ relationship model (3F / 3L)
# Every exploded multi-value cell lands here, so no relational fact survives only as a
# comma-separated string. `relation_context` is what keeps two same-named but different
# regimes (FMCS vs general scheme, product-scheme vs group-store guidance) apart.
REL_TAIL = ["relationship_type", "relation_context", "evidence_column",
            "evidence_value", "unmatched_reference", "source_file_ids", "source_files",
            "source_sheets", "source_rows", "confidence", "review_flag"]

REL = [
    ("IS_PRODUCT_MAPPING", "IS_PRODUCT_MAPPING.csv", "STANDARD", "PRODUCT",
     ["is_id", "canonical_is_number", "product_id", "product_name"],
     "Standard <-> product covered. Sources: product masters, QCO product lists."),
    ("IS_QCO_MAPPING", "IS_QCO_MAPPING.csv", "STANDARD", "QCO",
     ["is_id", "canonical_is_number", "qco_id", "qco_number"],
     "Standard made mandatory by a Quality Control Order."),
    ("IS_SCHEME_MAPPING", "IS_SCHEME_MAPPING.csv", "STANDARD", "SCHEME",
     ["is_id", "canonical_is_number", "scheme_id", "scheme_name"],
     "Standard certifiable under a BIS scheme (I / II-CRS / IV-COC / X / FMCS)."),
    ("IS_DOCUMENT_MAPPING", "IS_DOCUMENT_MAPPING.csv", "STANDARD", "DOCUMENT",
     ["is_id", "canonical_is_number", "document_id", "document_type", "title"],
     "Standard <-> supporting document (manual, gazette PDF, circular, web page)."),
    ("IS_TEST_MAPPING", "IS_TEST_MAPPING.csv", "STANDARD", "TEST",
     ["is_id", "canonical_is_number", "test_id", "test_name", "clause_reference"],
     "Test / parameter required by a standard, clause retained where stated."),
    ("IS_LAB_TEST_MAPPING", "IS_LAB_TEST_MAPPING.csv", "STANDARD", "LABORATORY",
     ["is_id", "canonical_is_number", "lab_id", "lab_name", "test_id", "test_name",
      "capability", "scope_status"],
     "Three-way: which lab can perform which test for which standard (F007/F020/F035)."),
    ("IS_RELATED_IS", "IS_RELATED_IS.csv", "STANDARD", "STANDARD",
     ["is_id", "canonical_is_number", "related_is_id", "related_canonical_is_number"],
     "Directed IS<->IS link: REFERENCES / SUPERSEDES / SUPERSEDED_BY / EQUIVALENT_TO."),
    ("QCO_SCHEME_MAPPING", "QCO_SCHEME_MAPPING.csv", "QCO", "SCHEME",
     ["qco_id", "qco_number", "scheme_id", "scheme_name"],
     "QCO enforced through a certification scheme."),
    ("PRODUCT_DOCUMENT_MAPPING", "PRODUCT_DOCUMENT_MAPPING.csv", "PRODUCT", "DOCUMENT",
     ["product_id", "product_name", "document_id", "document_type", "title"],
     "Product <-> product manual / guidance document."),
    ("TEST_LAB_MAPPING", "TEST_LAB_MAPPING.csv", "TEST", "LABORATORY",
     ["test_id", "test_name", "lab_id", "lab_name", "capability", "testing_charge"],
     "Lab capability for a test irrespective of standard."),
    ("NOTIFICATION_ENTITY_MAPPING", "NOTIFICATION_ENTITY_MAPPING.csv", "NOTIFICATION",
     "ANY", ["notification_id", "notification_number", "target_entity",
             "target_entity_id", "target_entity_label"],
     "Notification -> whatever it acts on (standard, QCO, scheme, product, lab)."),
]

# Beyond the 11 mandated tables: relational facts the corpus actually contains and
# which would otherwise be flattened back into cells.
REL += [
    ("IS_AMENDMENTS", "IS_AMENDMENTS.csv", "STANDARD", "STANDARD",
     ["is_id", "canonical_is_number", "amendment_reference", "amendment_date",
      "amended_from_version", "amended_to_version", "amendment_status",
      "superseded_standard", "superseding_standard", "document_id"],
     "3F `amendments` exploded. One row per amendment event (F026, plus amendment "
     "references parsed out of IS strings by p2_lib)."),
    ("IS_PRODUCT_MANUAL_MAPPING", "IS_PRODUCT_MANUAL_MAPPING.csv", "STANDARD",
     "PRODUCT_MANUAL", ["is_id", "canonical_is_number", "manual_id", "manual_title"],
     "Standard <-> its BIS Product Manual / SIT document."),
    ("IS_FMCS_MAPPING", "IS_FMCS_MAPPING.csv", "STANDARD", "FMCS",
     ["is_id", "canonical_is_number", "fmcs_id", "cml_licence_no",
      "manufacturer_name", "country"],
     "Foreign manufacturer licensed against a standard (F040/F045; F043 gives counts)."),
    ("ENTITY_DOCUMENT_MAPPING", "ENTITY_DOCUMENT_MAPPING.csv", "ANY", "DOCUMENT",
     ["entity_type", "entity_id", "entity_label", "document_id", "document_type",
      "title", "source_url"],
     "Generic evidence edge for entities with no dedicated document table (QCO, "
     "scheme, lab, hallmarking centre, FAQ, legal instrument)."),
    ("SCHEME_PRODUCT_MAPPING", "SCHEME_PRODUCT_MAPPING.csv", "SCHEME", "PRODUCT",
     ["scheme_id", "scheme_name", "product_id", "product_name"],
     "Product certifiable under a scheme, where the source states it directly."),
    ("HALLMARKING_CENTRE_SCOPE", "HALLMARKING_CENTRE_SCOPE.csv", "HALLMARKING", "ANY",
     ["centre_id", "centre_name", "scope_item", "recognition_status", "city", "state"],
     "AHC recognition scope / metal-purity coverage as stated (F038/F039)."),
    ("IS_ENTITY_MAPPING", "IS_ENTITY_MAPPING.csv", "STANDARD", "ANY",
     ["is_id", "canonical_is_number", "entity_type", "entity_id", "entity_label"],
     "Generic IS edge for entities with no dedicated IS<->X table (FAQ, legal "
     "instrument, hallmarking order). Mirrors ENTITY_DOCUMENT_MAPPING so an IS "
     "reference is never dropped merely because its counterpart lacks a table."),
    ("QCO_PRODUCT_MAPPING", "QCO_PRODUCT_MAPPING.csv", "QCO", "PRODUCT",
     ["qco_id", "qco_number", "product_id", "product_name"],
     "Product brought under a QCO. Required because QCO product lists are measured "
     "multi-value columns (F014-F019) and flattening them into a cell is forbidden."),
]
REL_BY_NAME = {r[0]: r for r in REL}
REL_COLS = {r[0]: ["relationship_id"] + r[4] + REL_TAIL for r in REL}

# ------------------------------------------------------------- ID rules (3B) table
ID_RULES = [(PREFIX[e], e, MASTER[e], nk,
             PREFIX[e] + "-00001..., zero-padded to 5 digits, minted in sorted "
             "natural-key order so the same corpus always yields the same id",
             note) for e, _p, _m, nk, note in
            [(x[0], x[1], x[2], x[3], x[4]) for x in ENTITIES]]
ID_RULES += [
    ("REL", "RELATIONSHIP_ROW", "90_RELATIONSHIPS/*.csv",
     "table + left_id + right_id + relationship_type + relation_context",
     "REL-<table>-<00000>", "Stable per relationship table; duplicates collapse."),
    ("ATTR", "ENTITY_ATTRIBUTE_ROW", "00_MASTER/ENTITY_ATTRIBUTES.csv",
     "entity_id + canonical_attribute + attribute_context + source_file_id + source_row",
     "ATTR-<0000000>", "One row per surviving narrative/singleton source cell."),
    ("CONF", "CONFLICT", "92_VALIDATION/CONFLICT_STATUS.csv",
     "entity_id + field + source_a + source_b",
     "CONF-<000000>", "Carried over from Phase 2 conflict ids where they exist."),
    ("CHUNK", "QDRANT_CHUNK", "QDRANT_READY/qdrant_chunks.jsonl",
     "document_id + section + clause + ordinal", "CHUNK-<document_id>-<0000>",
     "Deterministic: re-running Phase 3 reproduces identical chunk ids."),
]

# F045 parsed FMCS twin of F040. Merged on a normalised licence key, never on row order.
FILE_OVERRIDE.update({
    ("F045", "manufacturer"): ("manufacturer_name", "NAME", "KEY_IDENTITY", "nname", ""),
    ("F045", "factory"): ("factory_address", "ADDRESS", "UNION_LONGEST", "nws", ""),
    ("F045", "licence"): ("cml_licence_no", "CODE", "KEY_IDENTITY", "nlic", ""),
    ("F045", "licence_status"): ("licence_status", "STATUS",
                                "PRESERVE_BOTH_ON_CONFLICT", "nstatus", ""),
    ("F045", "documents"): ("required_documents", "NARRATIVE", "UNION_LONGEST", "nws", ""),
    ("F045", "is_number"): ("licensed_is_text", "LIST", "EXPLODE_TO_RELATIONSHIP",
                            "msplit+is_all", ""),
})

# ------------------------------------------------------- 3Q final source folders
# Domain assignment is Phase 1's measured `primary_domain` (DATASET_CLASSIFICATION.csv),
# not a re-guess from filenames. Each folder receives the CANONICALISED domain view of
# its source files - masters and relationships live in 00_MASTER / 90_RELATIONSHIPS, so
# nothing is duplicated as authority.
FOLDER_PLAN = [
    ("01_KNOW_YOUR_STANDARD", "F026,F027,F028,F029"),
    ("02_PRODUCTS", "F011,F012,F013"),
    ("03_QCO", "F014,F015,F016,F017,F018,F019"),
    ("04_SCHEME_I", "F024"),
    ("05_SCHEME_II_CRS", "F001,F025"),
    ("06_SCHEME_IV_COC", "F002"),
    ("07_SCHEME_X", "F003,F022,F023"),
    ("08_PRODUCT_SPECIFIC", "F030,F031"),
    ("09_PRODUCT_MANUALS", "F010"),
    ("10_TESTING", "F005,F032"),
    ("11_CERTIFICATION_PROCESS", "F037"),
    ("12_CERTIFICATION_FAQ", "F006,F036"),
    ("13_LAB_SERVICES", "F007"),
    ("14_LIMS_LABS", "F020,F035"),
    ("15_LIMS_IS_TEST", ""),
    ("16_ACT_RULES_REGULATIONS", "F009,F033,F034"),
    ("17_HALLMARKING_OVERVIEW", ""),
    ("18_HALLMARKING_FAQ", ""),
    ("19_HALLMARKING_ORDERS", "F008"),
    ("20_HALLMARKING_CENTRES", "F038,F039"),
    ("21_JEWELLER_REGISTRATION", ""),
    ("22_FMCS", "F021,F040,F042,F043,F045,F046"),
    ("OTHER_RELEVANT", "F004,F041,F044,F047,F048"),
    ("UNKNOWN", ""),
]
# Four domains are legitimately empty: Phase 1 measured zero files for them. Creating
# the folder documents the gap; inventing a dataset to fill it would fabricate data.
EMPTY_DOMAINS = tuple(d for d, f in FOLDER_PLAN if not f)

# ---------------------------------------------------------------- 3I conflict policy
CONFLICT_STATUSES = ("RESOLVED", "UNRESOLVED_PRESERVE_BOTH", "REQUIRES_REVIEW")
CONFLICT_COLS = ["conflict_id", "entity_type", "entity_id", "entity_label", "field",
                 "source_a", "source_a_file_id", "value_a", "source_row_a", "date_a",
                 "source_b", "source_b_file_id", "value_b", "source_row_b", "date_b",
                 "resolution_status", "resolution_rule", "resolution_reason",
                 "canonical_value", "confidence", "review_flag"]

# Resolution is allowed ONLY where the sources themselves settle it. Each rule below
# names the evidence that licenses it; everything else stays PRESERVE_BOTH.
CONFLICT_POLICY = [
    ("SAME_VALUE_DIFFERENT_FORMAT", "Values equal after the field's declared transform "
     "(date reformat, IS spacing, case, whitespace).", "RESOLVED",
     "Normalised forms are byte-equal - no fact is in dispute.", "1.00"),
    ("ONE_SIDE_NULL", "One side is NULL_UNKNOWN, the other POPULATED.", "RESOLVED",
     "Coalesce to the populated value; absence of a statement is not a counter-claim.",
     "0.95"),
    ("ONE_SIDE_PLACEHOLDER", "One side is AMBIGUOUS_REQUIRES_REVIEW ('-', 'TBD', 'NA'), "
     "the other POPULATED.", "RESOLVED",
     "A placeholder asserts nothing; the populated value stands. Placeholder retained "
     "as original_value.", "0.90"),
    ("ASSERTED_ABSENCE_VS_VALUE", "One side asserts absence ('None'), the other gives a "
     "value.", "REQUIRES_REVIEW",
     "Both are positive claims and they contradict. Never silently coalesced.", "0.00"),
    ("SUBSTRING_ENRICHMENT", "One value strictly contains the other after "
     "normalisation.", "RESOLVED",
     "Longer value is the same statement with more detail; shorter kept as "
     "original_value. Applies to TITLE / NARRATIVE only, never to STATUS or DATE.",
     "0.80"),
    ("VERSION_EVIDENCE", "Phase 2 proved one file is an ENRICHMENT/REPAIR of the other "
     "for this field.", "RESOLVED",
     "Direction came from measured content, never from the filename.", "0.85"),
    ("STATUS_DISAGREEMENT", "Two different canonical status values for the same entity "
     "(e.g. the 136 hallmarking suspended-vs-active disagreements).",
     "UNRESOLVED_PRESERVE_BOTH",
     "A regulatory status is a fact about a point in time; without a stated effective "
     "date, choosing one would fabricate a compliance answer.", "0.00"),
    ("DATE_DISAGREEMENT", "Two different parsed dates for the same field.",
     "UNRESOLVED_PRESERVE_BOTH",
     "Both retained with precision and AMBIGUOUS_DMY flags; no arbitration.", "0.00"),
    ("NUMERIC_DISAGREEMENT", "Two different numbers (fees, counts, sample sizes).",
     "UNRESOLVED_PRESERVE_BOTH", "No basis to prefer one measurement.", "0.00"),
    ("FREE_TEXT_DIVERGENCE", "Two substantively different narratives for one field.",
     "UNRESOLVED_PRESERVE_BOTH",
     "Both are source statements; the RAG layer must be able to cite either.", "0.00"),
    ("HOMONYM_NOT_A_CONFLICT", "Same column name, different meaning per source.",
     "RESOLVED", "Not a conflict at all: 3D splits the column, so the two values "
     "occupy different canonical fields and never meet.", "1.00"),
]

# ------------------------------------------------------------------ 3J null semantics
NULL_SEMANTICS = [
    ("POPULATED", "A real value is present.", "the normalised value", "(none)",
     "Genuine data. original_value retained whenever the transform changed the text."),
    ("NULL_UNKNOWN", "Cell empty, or literally 'null' / 'nan' / 'blank' / '(null)'.",
     "empty string in CSV, SQL NULL after load", "SOURCE_CELL_EMPTY",
     "The source says nothing. Never rendered as 'N/A', 'Unknown', 'None' or '-'."),
    ("ASSERTED_ABSENCE", "Source explicitly states there is nothing: 'None', 'Nil', "
     "'Not applicable', 'Not required', 'No'.",
     "empty in the typed column + flag in <field>_null_class", "SOURCE_ASSERTS_ABSENCE",
     "This is DATA, not a null: 'no lab required' differs from 'lab unknown'. The "
     "assertion is preserved verbatim in <field>_original_value and must never be "
     "flattened into NULL_UNKNOWN."),
    ("AMBIGUOUS_REQUIRES_REVIEW", "Placeholder that asserts nothing either way: '-', "
     "'--', 'TBD', 'N/A', '?', 'pending', 'as above', '-do-'.",
     "empty in the typed column + flag in <field>_null_class",
     "SOURCE_PLACEHOLDER_AMBIGUOUS",
     "Cannot be read as absence or as unknown. Raised in REQUIRES_REVIEW so a human "
     "can decide; the raw token is preserved."),
]
NULL_FLAG_SUFFIX = ("_null_class", "_original_value", "_missing_reason")

# ------------------------------------------------- Zero Data Loss dispositions
DISPOSITIONS = [
    ("CANONICAL", "Source row became a canonical master row on its own."),
    ("MERGED", "Source row was unioned into a canonical row shared with other files; "
     "provenance lists every contributor."),
    ("DUPLICATE_ARCHIVED", "Row's content is fully carried by a retained file; the "
     "source file is copied (not moved-and-lost) to the archive after validation."),
    ("CONFLICT_PRESERVED", "Row contributed a value that disagrees with another source; "
     "both sides live in CONFLICT_STATUS.csv."),
    ("REQUIRES_REVIEW", "Row could not be resolved on the evidence available."),
    ("NOT_APPLICABLE", "Row is operational telemetry or a provenance/meta record, not a "
     "domain entity; retained in 91_PROVENANCE / 93_OPERATIONAL."),
]

# ------------------------------------------------------------------ 3R / 3S readiness
POSTGRES_NOTE = ("One CSV per table, stable column order, canonical ids as PK, "
                 "relationship tables as FK pairs, no list-valued cells, NULL as empty "
                 "field. DDL emitted alongside so no schema redesign is needed later.")
QDRANT_FIELDS = ["chunk_id", "document_id", "is_id", "canonical_is_number",
                 "document_type", "title", "section", "clause", "page_start",
                 "page_end", "breadcrumb", "content", "source_url", "version",
                 "effective_date", "sha256"]


# --------------------------------------------------------------- the resolver (3D)
def target_of(file_id):
    """Primary canonical target for a source file, from ROUTE. Never from the filename."""
    return ROUTE.get(file_id, ("ENTITY_ATTRIBUTES", "-", "UNROUTED", ""))[0]


def resolve(file_id, column, entity=None):
    """(canonical_column, semantic_type, merge_action, transform, target, rule_source).

    Precedence, most specific first:
      1. FILE_OVERRIDE[(file_id, column)]  - this file's column means something specific
      2. ENTITY_SCOPED[(entity, column)]   - homonym: meaning depends on the entity
      3. CMAP[column]                      - corpus-wide agreed meaning
      4. PRESERVE_AS_ATTRIBUTE             - unknown/singleton: kept losslessly in EAV

    Rule 4 is why no source column can be silently dropped: an unmapped column still
    has a defined destination.
    """
    c = norm_header(column) if column else ""
    ent = entity or target_of(file_id)
    if (file_id, c) in FILE_OVERRIDE:
        cc, st, ma, tr, tg = FILE_OVERRIDE[(file_id, c)]
        return (cc, st, ma, tr, tg or ent, "FILE_OVERRIDE")
    if (ent, c) in ENTITY_SCOPED:
        cc, st, ma, tr = ENTITY_SCOPED[(ent, c)]
        return (cc, st, ma, tr, ent, "ENTITY_SCOPED_HOMONYM")
    if c in CMAP:
        cc, st, ma, tr = CMAP[c]
        tg = "ENTITY_ATTRIBUTES" if ma == "PRESERVE_AS_ATTRIBUTE" else ent
        return (cc, st, ma, tr, tg, "CMAP")
    return (c, "TEXT", "PRESERVE_AS_ATTRIBUTE", "nws", "ENTITY_ATTRIBUTES",
            "DEFAULT_ATTRIBUTE")


def attr_context(file_id):
    """Context tag stamped on ENTITY_ATTRIBUTES / relationship rows from this file, so
    two guidance regimes with identical column names never read as one."""
    return ATTR_CONTEXT.get(file_id, "")


def self_check():
    """Cheap internal consistency guard - run before anything writes output."""
    p = []
    if len(ENTITIES) != 13:
        p.append("ENTITIES must define 13 entities, found %d" % len(ENTITIES))
    if len(set(PREFIX.values())) != 13:
        p.append("id prefixes are not unique")
    for f, r in ROUTE.items():
        if r[0] not in ENT and r[0] not in {a[0] for a in AUX_DATASETS} \
                and r[0] not in REL_BY_NAME:
            p.append("%s routes to unknown target %s" % (f, r[0]))
    if len(ROUTE) != 49:
        p.append("ROUTE must cover 49 sources, found %d" % len(ROUTE))
    named = {r[0] for r in REL}
    for m in ("IS_PRODUCT_MAPPING", "IS_QCO_MAPPING", "IS_SCHEME_MAPPING",
              "IS_DOCUMENT_MAPPING", "IS_TEST_MAPPING", "IS_LAB_TEST_MAPPING",
              "IS_RELATED_IS", "QCO_SCHEME_MAPPING", "PRODUCT_DOCUMENT_MAPPING",
              "TEST_LAB_MAPPING", "NOTIFICATION_ENTITY_MAPPING"):
        if m not in named:
            p.append("mandated relationship table missing: %s" % m)
    # every explode destination must be a real relationship table (kind REL) and every
    # counterpart entity a real entity - a typo here would silently strip a
    # multi-value column's fragments at build time.
    aux = {a[0] for a in AUX_DATASETS}
    for (ent, col), (kind, dest, rtype, counter, mint) in EXPLODE_ROUTE.items():
        if ent not in ENT and ent not in aux:
            p.append("EXPLODE_ROUTE owner %s is not an entity or aux dataset" % ent)
        if kind == "REL":
            if dest not in REL_BY_NAME:
                p.append("EXPLODE_ROUTE %s.%s -> unknown table %s" % (ent, col, dest))
            if not rtype:
                p.append("EXPLODE_ROUTE %s.%s has no relationship_type" % (ent, col))
        elif kind != "ATTR":
            p.append("EXPLODE_ROUTE %s.%s has unknown kind %s" % (ent, col, kind))
        if counter and counter not in ENT:
            p.append("EXPLODE_ROUTE %s.%s counterpart %s unknown" % (ent, col, counter))
        if mint and not counter:
            p.append("EXPLODE_ROUTE %s.%s mints without a counterpart" % (ent, col))
    for (ent, col), tgt in MASTER_ALIAS.items():
        if ent not in MASTER_COLS:
            p.append("MASTER_ALIAS owner %s is not an entity" % ent)
        elif tgt not in MASTER_COLS[ent]:
            p.append("MASTER_ALIAS %s.%s -> %s which is not a %s master column"
                     % (ent, col, tgt, ent))
        elif col in MASTER_COLS[ent]:
            p.append("MASTER_ALIAS %s.%s aliases a real master column" % (ent, col))
    for (ent, col), (tbl, rt, counter, mint, also) in LINK_FIELD.items():
        if ent not in MASTER_COLS:
            p.append("LINK_FIELD owner %s is not an entity" % ent)
        if tbl not in REL_BY_NAME:
            p.append("LINK_FIELD %s.%s -> unknown table %s" % (ent, col, tbl))
        if not rt:
            p.append("LINK_FIELD %s.%s has no relationship_type" % (ent, col))
        if counter not in ENT:
            p.append("LINK_FIELD %s.%s counterpart %s unknown" % (ent, col, counter))
        if also and ent in MASTER_COLS and also not in MASTER_COLS[ent]:
            p.append("LINK_FIELD %s.%s also_column %s not in master" % (ent, col, also))
        if (ent, col) in EXPLODE_ROUTE:
            p.append("LINK_FIELD %s.%s also has an EXPLODE_ROUTE" % (ent, col))
    used_tr = {v[3] for v in CMAP.values()} | {v[3] for v in ENTITY_SCOPED.values()} \
        | {v[3] for v in FILE_OVERRIDE.values()}
    for t in SUBFIELD:
        if t not in used_tr:
            p.append("SUBFIELD names transform %s that no column uses" % t)
    pmsets = {v for v in PM_SECTION_ROUTE.values()}
    for s in pmsets:
        if "PRODUCT_MANUAL_" + s not in {a[0] for a in AUX_DATASETS}:
            p.append("PM_SECTION_ROUTE target PRODUCT_MANUAL_%s has no dataset" % s)
    for name in AUX_COLS:
        if name not in {a[0] for a in AUX_DATASETS}:
            p.append("AUX_COLS declares unknown dataset %s" % name)
    return p


# ---------------------------------------------------------------------------
# OUTPUT_TREE - the physical folder layout Phase 3 creates, declared once here so
# the design workbook (3A) and every build script write to the same paths.
# 'ALWAYS' folders are created unconditionally; 'IF_NONEMPTY' only when the
# measured source list is non-empty; 'EMPTY_BY_MEASUREMENT' is created empty on
# purpose - Phase 1 measured zero files for that BIS domain, and the empty folder
# documents the gap. Inventing a dataset to fill it would fabricate data.
# ---------------------------------------------------------------------------
OUTPUT_TREE = [
    ("03_CANONICAL_DESIGN", "DESIGN", "ALWAYS",
     "CANONICAL_DATA_MODEL.xlsx - the 10-sheet design contract (3A). Written "
     "before any source data is read for transformation."),
    ("00_MASTER", "CANONICAL", "ALWAYS",
     "13 entity master CSVs + ENTITY_ATTRIBUTES.csv + the Product-Manual technical "
     "datasets + IS_COMPLETE_MASTER.xlsx. The single authority for entity identity."),
    ("01_SOURCE_DATA", "SOURCE_DOMAIN_ROOT", "ALWAYS",
     "22 numbered BIS domain folders holding the canonicalised per-source view of "
     "each file, placed by Phase 1's measured primary_domain."),
    ("90_RELATIONSHIPS", "CANONICAL", "ALWAYS",
     "19 relationship tables. Every many-to-many fact lives here as id pairs, never "
     "as a comma-separated cell in a master."),
    ("91_PROVENANCE", "PROVENANCE", "ALWAYS",
     "SOURCE_FILE_PROVENANCE.csv, RECORD_PROVENANCE.csv, DOCUMENT_PROVENANCE.csv - "
     "every canonical value traceable to file, sheet and row."),
    ("92_VALIDATION", "VALIDATION", "ALWAYS",
     "FINAL_DATA_VALIDATION_REPORT.xlsx and the 9 audit CSVs, incl. "
     "CONFLICT_STATUS.csv and REQUIRES_REVIEW.csv."),
    ("93_OPERATIONAL", "OPERATIONAL", "ALWAYS",
     "EXTRACTION_LOG.csv and other scrape telemetry - retained, but not domain data, "
     "so it is kept out of the entity masters."),
    ("99_RAW/ARCHIVE_DUPLICATES", "ARCHIVE", "ALWAYS",
     "COPIES of the 4 archivable duplicates, written only after canonical export "
     "validation passes. Originals are never deleted or moved."),
    ("POSTGRES_READY", "LOAD", "ALWAYS",
     "Relational-load-ready CSVs plus DDL. No list-valued cells, NULL as empty."),
    ("QDRANT_READY", "LOAD", "ALWAYS",
     "qdrant_chunks.jsonl with the 16 declared payload fields. No embeddings."),
]

# ---------------------------------------------------------------------------
# EXPLODE_ROUTE (3F) - where every measured multi-value column's fragments go.
# Key: (owning_entity, canonical_column). Value:
#   (kind, destination, relationship_type, counterpart_entity, mint)
# kind REL  -> one relationship row per fragment in `destination`
# kind ATTR -> one ENTITY_ATTRIBUTES row per fragment, attribute name `destination`
# mint       -> counterpart entity is created from the fragment when the fragment
#               yields that entity's natural key; otherwise the fragment is kept in
#               `unmatched_reference` so the reference survives without inventing an
#               entity. An IS number or a QCO/licence number is a hard identifier, so
#               minting from it states nothing the source did not.
# Every pair measured in COLUMN_PROFILING as multi-value is listed here; a pair with
# no entry falls back to ATTR under its own column name, so nothing is ever dropped.
# ---------------------------------------------------------------------------
EXPLODE_ROUTE = {
    ("PRODUCT", "alternate_names"): ("ATTR", "alternate_name", "", "", False),
    ("PRODUCT", "keywords"): ("ATTR", "keyword", "", "", False),
    ("FMCS", "licensed_is_text"): ("REL", "IS_FMCS_MAPPING", "LICENSED_FOR",
                                   "STANDARD", True),
    ("STANDARD", "notification_number"): ("REL", "NOTIFICATION_ENTITY_MAPPING",
                                          "NOTIFIES", "NOTIFICATION", True),
    ("QCO", "qco_amendments"): ("ATTR", "qco_amendment", "", "", False),
    ("QCO", "qco_product_text"): ("REL", "QCO_PRODUCT_MAPPING", "COVERS",
                                  "PRODUCT", True),
    ("QCO", "qco_schemes_text"): ("REL", "QCO_SCHEME_MAPPING", "ENFORCED_THROUGH",
                                  "SCHEME", True),
    ("NOTIFICATION", "related_amendment_text"): ("REL", "IS_AMENDMENTS", "AMENDS",
                                                 "STANDARD", True),
    ("FAQ", "related_is_text"): ("REL", "IS_ENTITY_MAPPING", "REFERENCED_BY",
                                 "STANDARD", True),
    ("LABORATORY", "related_is_text"): ("REL", "IS_LAB_TEST_MAPPING", "TESTABLE_AT",
                                        "STANDARD", True),
    ("LEGAL", "related_is_text"): ("REL", "IS_ENTITY_MAPPING", "REFERENCED_BY",
                                   "STANDARD", True),
    ("NOTIFICATION", "related_is_text"): ("REL", "NOTIFICATION_ENTITY_MAPPING",
                                          "ACTS_ON", "STANDARD", True),
    ("PRODUCT", "related_is_text"): ("REL", "IS_PRODUCT_MAPPING", "COVERED_BY",
                                     "STANDARD", True),
    ("QCO", "related_is_text"): ("REL", "IS_QCO_MAPPING", "MANDATES", "STANDARD",
                                 True),
    ("SCHEME", "related_product_manual_text"): ("ATTR", "product_manual_reference",
                                                "", "", False),
    ("FAQ", "related_product_text"): ("ATTR", "product_reference", "", "", False),
    ("SCHEME", "related_product_text"): ("REL", "SCHEME_PRODUCT_MAPPING", "COVERS",
                                         "PRODUCT", True),
    ("STANDARD", "related_product_text"): ("REL", "IS_PRODUCT_MAPPING", "COVERS",
                                           "PRODUCT", True),
    ("DOCUMENT", "related_qco_text"): ("REL", "ENTITY_DOCUMENT_MAPPING",
                                       "EVIDENCED_BY", "QCO", True),
    ("FAQ", "related_qco_text"): ("ATTR", "qco_reference", "", "", False),
    ("NOTIFICATION", "related_qco_text"): ("REL", "NOTIFICATION_ENTITY_MAPPING",
                                           "ACTS_ON", "QCO", True),
    ("PRODUCT", "related_qco_text"): ("REL", "QCO_PRODUCT_MAPPING", "COVERED_BY",
                                      "QCO", True),
    ("SCHEME", "related_qco_text"): ("REL", "QCO_SCHEME_MAPPING", "ENFORCES", "QCO",
                                     True),
    ("DOCUMENT", "related_scheme_text"): ("REL", "ENTITY_DOCUMENT_MAPPING",
                                          "EVIDENCED_BY", "SCHEME", True),
    ("FAQ", "related_scheme_text"): ("ATTR", "scheme_reference", "", "", False),
    ("PRODUCT", "related_scheme_text"): ("REL", "SCHEME_PRODUCT_MAPPING",
                                         "CERTIFIABLE_UNDER", "SCHEME", True),
    ("PRODUCT_MANUAL", "related_scheme_text"): ("ATTR", "scheme_reference", "", "",
                                                False),
    ("STANDARD", "related_scheme_text"): ("REL", "IS_SCHEME_MAPPING",
                                          "CERTIFIABLE_UNDER", "SCHEME", True),
    ("SCHEME", "related_sit_text"): ("ATTR", "sit_reference", "", "", False),
    ("HALLMARKING", "services"): ("REL", "HALLMARKING_CENTRE_SCOPE", "PROVIDES",
                                  "", False),
    ("STANDARD", "superseded_standard"): ("REL", "IS_RELATED_IS", "SUPERSEDES",
                                          "STANDARD", True),
    ("STANDARD", "superseding_standard"): ("REL", "IS_RELATED_IS", "SUPERSEDED_BY",
                                           "STANDARD", True),
    ("LAB_SCOPE", "test_method_standard"): ("REL", "IS_LAB_TEST_MAPPING",
                                            "TESTED_UNDER", "STANDARD", True),
    ("TEST", "test_method_standard"): ("REL", "IS_TEST_MAPPING", "REQUIRED_BY",
                                       "STANDARD", True),
}

# MASTER_ALIAS - the only 5 cases where two source-derived canonical names are the
# same field of the same entity on the evidence of the sources themselves. Applied
# before placement, so the value lands in a real master column instead of an
# attribute row. Deliberately short: a synonym the sources do not establish is not
# asserted here, it goes to ENTITY_ATTRIBUTES instead.
MASTER_ALIAS = {
    ("FMCS", "licence_validity_date"): "validity_date",
    ("FMCS", "required_documents"): "fmcs_documents",
    ("NOTIFICATION", "notification_title"): "title",
    ("PRODUCT_MANUAL", "version"): "manual_version",
    ("QCO", "mandatory_voluntary"): "mandatory_status",
}

# LINK_FIELD - a cross-entity identity field carried on a row of a *different*
# entity. Writing it into that entity's master would flatten a one-to-many, which
# the spec forbids, so it becomes a relationship row instead. `also_column` is
# filled on the owning master only when the master really has that column (a single
# stable pointer), and stays "" otherwise.
# (owner_entity, canonical_column) ->
#     (table, relationship_type, counterpart_entity, mint, also_column)
LINK_FIELD = {
    ("QCO", "canonical_is_number"): ("IS_QCO_MAPPING", "MANDATES", "STANDARD", True, ""),
    ("SCHEME", "canonical_is_number"): ("IS_SCHEME_MAPPING", "CERTIFIABLE_UNDER",
                                        "STANDARD", True, ""),
    ("TEST", "canonical_is_number"): ("IS_TEST_MAPPING", "REQUIRED_BY", "STANDARD",
                                      True, "method_standard_is_id"),
    ("STANDARD", "product_name"): ("IS_PRODUCT_MAPPING", "COVERS", "PRODUCT", True, ""),
    ("STANDARD", "scheme_label"): ("IS_SCHEME_MAPPING", "CERTIFIABLE_UNDER", "SCHEME",
                                   True, ""),
    ("DOCUMENT", "product_name"): ("PRODUCT_DOCUMENT_MAPPING", "DOCUMENTS", "PRODUCT",
                                   True, "product_id"),
    ("TEST", "product_name"): ("IS_PRODUCT_MAPPING", "TESTED_FOR", "PRODUCT", True, ""),
    ("PRODUCT_MANUAL", "product_name"): ("IS_PRODUCT_MAPPING", "DOCUMENTED_FOR",
                                         "PRODUCT", True, "product_id"),
}

# SUBFIELD - a transform that returns a dict or a tuple produces several canonical
# fields from one cell. This names them; placement then decides master column vs
# attribute row exactly as it does for a plain string. "{}" is the canonical column
# the cell resolved to. Sentinels: @original -> "{}_original_value" attribute row,
# @review -> raises the row's review flag, @drop -> kept in provenance only,
# @label -> the entity's source_reference_label when the base is a URL column.
# Tuple transforms are keyed positionally.
SUBFIELD = {
    "nis": {"is_id": "is_semantic_key", "raw_is_number": "raw_is_number_variants",
            "display_is_number": "display_is_number",
            "canonical_is_number": "canonical_is_number",
            "standard_year": "standard_year", "part_number": "part_number",
            "section_number": "section_number",
            "amendment_reference": "amendment_reference",
            "iec_reference": "iec_reference", "part_source": "part_source",
            "parse_status": "parse_status"},
    "ndate": {"iso": "{}", "precision": "{}_precision", "flag": "@review",
              "raw": "@original"},
    "nurl": {"url": "{}", "label": "@label", "cls": "@drop"},
    "nlic": {"licence_no": "{}", "licence_key": "licence_key",
             "original": "@original", "cls": "@drop"},
    "nstatus": {0: "{}", 1: "{}_original"},
    "nmand": {0: "{}", 1: "{}_original"},
    "split_no_and_date": {"number": "notification_number",
                          "number_note": "notification_number_note",
                          "date_iso": "notification_date",
                          "date_precision": "notification_date_precision",
                          "date_flag": "@review", "date_text": "@drop",
                          "original": "@original", "split_method": "@drop"},
    "split_is_and_product": {"is_list": "related_is_text",
                             "product_text": "qco_product_text",
                             "range_flag": "@review",
                             "alt_year_text": "standard_year_alternatives",
                             "original": "@original", "split_method": "@drop"},
    "split_scope_excl_amend": {"scope": "qco_scope", "exclusions": "qco_exclusions",
                               "amendments": "qco_amendments",
                               "original": "@original", "split_method": "@drop"},
    "split_name_address": {"name": "manufacturer_name", "address": "factory_address",
                           "city": "city", "country": "country",
                           "original": "@original", "split_method": "@drop"},
}

# PM_SECTION_ROUTE (3N) - the Product Manual narrative columns measured on F010,
# each assigned to exactly one technical dataset. Long format, one row per
# (manual, section), so nothing is flattened and nothing is invented: the five
# datasets contain only text that exists in the source manual columns.
PM_SECTION_ROUTE = {
    "raw_material_requirements": "REQUIREMENTS",
    "process_requirements": "REQUIREMENTS",
    "licensing_requirements": "REQUIREMENTS",
    "document_scope": "REQUIREMENTS",
    "testing_requirements": "TESTING",
    "inspection_requirements": "TESTING",
    "sit_sti": "TESTING",
    "sampling_guidelines": "SAMPLING",
    "grouping_guidelines": "SAMPLING",
    "test_equipment": "INFRASTRUCTURE",
    "marking_requirements": "MARKING",
}
PM_SECTION_COLS = [
    "pm_section_id", "pm_id", "manual_title", "manual_version", "is_id",
    "canonical_is_number", "product_id", "product_name", "section_category",
    "source_column", "requirement_text", "text_length", "clause", "source_file_id",
    "source_file", "source_sheet", "source_row", "source_url", "review_flag",
]

# AUX_COLS - explicit schema for every aux dataset that this build writes rows into
# from more than one place (so it cannot be derived from one file's columns alone).
# The four pass-through aux datasets (LAB_SCOPE, the two FMCS coverage aggregates,
# EXTRACTION_LOG) get their columns from the resolved canonical names of their single
# source file, computed at build time, so a source column can never be silently lost.
AUX_COLS = {
    "ENTITY_ATTRIBUTES": [
        "attribute_id", "entity_type", "entity_id", "entity_label", "attribute_name",
        "attribute_value", "value_length", "semantic_type", "attribute_context",
        "null_class", "original_value", "missing_reason", "source_file_id",
        "source_file", "source_sheet", "source_row", "source_column",
        "transformation_rule", "merge_action", "rule_source", "source_url",
        "review_flag",
    ],
    "RECORD_PROVENANCE": [
        "provenance_id", "provenance_origin", "entity_type", "entity_id",
        "entity_label", "canonical_column", "canonical_value", "source_file_id",
        "source_file", "source_sheet", "source_row", "source_column", "source_value",
        "null_class", "missing_reason", "transformation_rule", "merge_action",
        "rule_source", "record_disposition", "source_url", "source_title",
        "source_type", "document_id", "document_title", "page", "section", "clause",
        "version", "effective_date", "document_hash", "retrieved_at", "evidence_text",
        "verification_status", "confidence",
    ],
    "SOURCE_FILE_PROVENANCE": [
        "source_file_id", "original_filename", "extension", "exact_path",
        "source_location", "sha256", "file_size_bytes", "encoding", "sheet_name",
        "sheet_count", "total_data_rows", "total_columns", "canonical_target",
        "canonical_dataset", "candidate_topic", "rows_read", "cells_projected",
        "records_canonical", "records_merged", "records_conflict_preserved",
        "records_requires_review", "records_not_applicable", "records_accounted",
        "retention_decision", "archive_path", "structural_issue", "analysis_status",
        "modified_time_utc", "notes",
    ],
    "DOCUMENT_PROVENANCE": [
        "document_provenance_id", "document_id", "document_type", "title", "is_id",
        "canonical_is_number", "source_url", "download_url", "local_path", "sha256",
        "page_count", "http_status", "content_type", "bytes", "last_modified",
        "access_type", "parser_status", "dedup_status", "retrieved_at", "chunk_count",
        "evidence_row_count", "source_file_id", "source_file", "source_sheet",
        "source_row", "notes",
    ],
    "REVIEW_QUEUE": [
        "review_id", "entity_type", "entity_id", "entity_label", "field",
        "field_value", "review_class", "review_reason", "required_action",
        "source_file_id", "source_file", "source_sheet", "source_row",
        "attempted_source_url", "phase2_verdict", "resolution_status",
    ],
}

if __name__ == "__main__":
    bad = self_check()
    print("p3_model: %d entities, %d aux datasets, %d routed files, %d relationship "
          "tables, %d CMAP, %d entity-scoped, %d file overrides, %d folders"
          % (len(ENTITIES), len(AUX_DATASETS), len(ROUTE), len(REL), len(CMAP),
             len(ENTITY_SCOPED), len(FILE_OVERRIDE), len(FOLDER_PLAN)))
    print("SELF-CHECK: " + ("OK" if not bad else "FAIL\n  " + "\n  ".join(bad)))
