/* Typed API models mirroring the FastAPI contracts exactly (API_MAPPING.md). */

export interface Citation {
  document_id: string
  title: string
  page: number | string
  clause: string
  source_url: string
}

export interface RelatedInfo {
  products: any[]
  qcos: any[]
  schemes: any[]
  tests: any[]
  labs: any[]
}

export interface AgentUsage {
  used: boolean
  steps: number
  tools_used: string[]
}

export interface ChatResponse {
  answer: string
  confidence: number
  language: string
  intent: string
  entities: Record<string, any>
  sources: Citation[]
  related: RelatedInfo
  agent: AgentUsage
}

export interface AgentStep {
  node?: string
  tool?: string
  detail?: string
}

export interface EvidenceItem {
  document_id: string
  canonical_is_number: string
  document_type: string
  title: string
  section: string
  clause: string
  page: number | string
  content: string
  source_url: string
  version: string
  effective_date: string
  relevance_score: number
}

export interface AgentRunResponse {
  answer: string
  status: string
  plan: any[]
  steps: AgentStep[]
  tools_used: string[]
  evidence: EvidenceItem[]
  citations: Citation[]
  confidence: number
  entities: Record<string, any>
  unresolved_items: any[]
  conversation_id: string
}

export interface StandardRow {
  is_id: string
  canonical_is_number: string
  display_is_number: string
  title: string
  standard_status: string
  mandatory_voluntary: string
  [k: string]: any
}

export interface ProductRow {
  product_id: string
  product_name: string
  product_category: string | null
  [k: string]: any
}

export interface QcoRow { [k: string]: any }
export interface SchemeRow { [k: string]: any }
export interface TestRow { [k: string]: any }

export interface LabRow {
  lab_id: string
  lab_name: string
  lab_code: string
  lab_type: string | null
  address: string | null
  city: string | null
  state: string | null
  pin: string | null
  contact_number: string | null
  email: string | null
  recognition_status: string | null
  scope_url: string | null
  source_url: string | null
}

export interface LabScopeRow {
  test_name: string | null
  canonical_is_number: string | null
  product_name: string | null
  test_method_standard: string | null
  clause_reference: string | null
  scope_status: string | null
  testing_charge: string | null
}

export interface HallmarkCentre {
  hm_id: string
  centre_name: string
  centre_code: string
  address: string | null
  city: string | null
  state: string | null
  pin: string | null
  recognition_status: string | null
  validity: string | null
  hallmarking_scope: string | null
  source_url: string | null
}

export interface AuditCreateResponse {
  audit_id: string
  product_text: string
  product: any
  is_number: string | null
  status: string
}

export interface UploadedDocument {
  document_id: string
  filename: string
  status: string
  category?: string | null
  pages?: number | null
  evidence_count?: number | null
}

export interface ProcessResponse {
  extract: any[]
  classify: any[]
  evidence_added: number
  documents: UploadedDocument[]
}

export interface ComplianceScore {
  score: number
  total: number
  passed: number
  gaps: number
  unknown: number
  label: string
}

export interface ComplianceDecision {
  requirement_id: string
  requirement: string
  type: string
  decision: 'PASS' | 'GAP' | 'UNKNOWN'
  reason: string
  evidence_refs: any[]
  bis_source: string
  clause: string
  conflicts: any[]
}

export interface RemediationItem {
  requirement_id: string
  gap: string
  missing_evidence: string
  recommendation: string
  bis_source: string
}

export interface AnalyzeResponse {
  audit_id: string
  score: ComplianceScore
  requirements: number
  results: ComplianceDecision[]
  steps: any[]
  latency_sec: number
}

export interface ComplianceResultResponse {
  audit_id: string
  score: ComplianceScore | null
  results: ComplianceDecision[]
  gaps: any[]
  remediation: RemediationItem[]
  status: string
}

export interface ComplianceReport {
  audit_id: string
  product: any
  bis_standard: any
  qco_scheme: any
  documents: any[]
  requirements_checked: number
  passed: ComplianceDecision[]
  gaps: ComplianceDecision[]
  unknown: ComplianceDecision[]
  score: ComplianceScore
  critical_missing_evidence: any[]
  remediation: RemediationItem[]
  bis_sources: any[]
  disclaimer: string
}

export interface AuditSummary {
  audit_id: string
  product_text: string
  created_at: string
  status: string
  documents: any[]
  evidence_count: number
  last_score: ComplianceScore | null
}

export interface HealthResponse {
  status: string
  phase: number
  llm: string
  supabase: { ok: boolean }
  qdrant: { ok: boolean }
}
