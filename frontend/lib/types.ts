export type User = { id: number; username: string; name: string; role: string; organization: string; department?: string; crew?: string };
export type Project = { id: number; name: string; organization: string; address: string; status: string; timezone: string };
export type Location = { id: number; building: string; floor: string; zone: string };
export type Photo = { id: number; original_name: string; mime_type: string; size_bytes: number; content_url: string };
export type RecordItem = {
  id: number; project_id: number; category: string; description: string; occurred_at: string;
  latitude?: number; longitude?: number; gps_accuracy?: number; gps_captured_at?: string; gps_status: string;
  recorder: User; project: Project; location: Location; photos: Photo[]; created_at: string; updated_at: string;
  source_type: "MANUAL" | "VOICE_AI"; structured_event?: string; event_schema_version?: string;
};
export type TaskItem = {
  id: number; project_id: number; source_record_id?: number; title: string; description: string; due_at: string;
  source_issue_id?: string; kind: "GENERAL" | "RECTIFICATION"; status: string; creator: User; assignee: User; created_at: string; updated_at: string;
};
export type Dashboard = {
  today_records: number; pending_tasks: number; completed_tasks: number;
  confirmed_events: number; pending_issues: number; waiting_review_rectifications: number; closed_rectifications_today: number;
  recent_records: RecordItem[]; upcoming_tasks: TaskItem[];
};

export type Media = Photo & { media_type: string };
export type TranscriptionJob = {
  id: string; project_id: number; original_audio_media_id?: number; normalized_audio_media_id?: number;
  status: "QUEUED" | "PROCESSING" | "SUCCEEDED" | "FAILED"; detected_language?: string;
  raw_transcript?: string; edited_transcript?: string; provider: string; model: string; error_code?: string;
  safe_error_message?: string; created_at: string; started_at?: string; completed_at?: string; record_id?: number;
  original_audio?: Media;
};
export type EvidenceRef = { source_type: "raw_transcript" | "edited_transcript" | "audio"; quote?: string };
export type EventIssue = {
  description: string; category: "safety" | "quality" | "civilized_construction" | "other";
  responsible_person_text?: string; candidate_project_member_id?: number; deadline_text?: string;
  proposed_deadline?: string; evidence_quote: string; needs_confirmation: boolean;
};
export type EventPayload = {
  schema_version: "1.0"; event_type: "construction_progress" | "safety_inspection" | "quality_inspection" | "general";
  construction: { activity?: string; progress_percent?: number; crew?: string; worker_count?: number };
  issues: EventIssue[]; notes?: string; missing_fields: string[]; warnings: string[];
  field_evidence: Record<string, EvidenceRef[]>;
};
export type EventDraft = {
  id: string; transcription_job_id: string; project_id: number; status: "GENERATING" | "READY" | "FAILED" | "CONFIRMED" | "REJECTED";
  raw_payload?: EventPayload; system_resolved_payload?: EventPayload; user_corrected_payload?: EventPayload; schema_version: string; provider: string; model: string;
  prompt_version: string; safe_error_message?: string; confirmed_record_id?: number; created_at: string; updated_at: string; confirmed_at?: string;
};
export type VoiceEvidence = { job: TranscriptionJob; draft?: EventDraft };

export type SiteEvidenceRef = {
  evidence_type: "confirmed_transcript" | "photo" | "manual_location" | "record_metadata";
  source_id: string; quote?: string; description?: string; media_file_id?: number; confidence: number;
};
export type SiteEventIssue = {
  description: string; category: "文明施工/安全" | "安全" | "质量" | "文明施工" | "其他";
  risk_level: "pending_confirmation"; responsible_person?: string; due_at?: string; due_text?: string;
  confidence: number; evidence: SiteEvidenceRef[]; needs_confirmation: boolean;
};
export type SiteEventPayload = {
  schema_version: "1.0"; event_type: "site_inspection";
  construction: { activity?: string; crew?: string; worker_count?: number; progress?: number };
  issues: SiteEventIssue[]; field_evidence: Record<string, SiteEvidenceRef[]>;
  needs_confirmation_fields: string[]; warnings: string[]; overall_confidence: number;
};
export type EventExtractionJob = {
  id: string; project_id: number; record_id: number; status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
  stage: string; provider: string; model: string; schema_version: string; result_event_id?: string;
  retry_of_job_id?: string; error_code?: string; error_message?: string; created_at: string;
  started_at?: string; finished_at?: string;
};
export type SiteEventRevision = {
  id: number; actor_id: number; action: string; before_data?: SiteEventPayload;
  after_data?: SiteEventPayload; created_at: string;
};
export type SiteEvent = {
  id: string; project_id: number; source_record_id: number; extraction_job_id: string;
  status: "DRAFT" | "CONFIRMED" | "REJECTED"; schema_version: string; event_type: string;
  ai_output: SiteEventPayload; draft_data: SiteEventPayload; confirmed_data?: SiteEventPayload;
  evidence_map: Record<string, SiteEvidenceRef[]>; overall_confidence: number;
  confirmed_by?: number; confirmed_at?: string; rejected_by?: number; rejected_at?: string;
  rejection_reason?: string; created_at: string; updated_at: string; revisions: SiteEventRevision[];
};
export type RecordEventState = {
  record_id: number; confirmed_text?: string; confirmed_text_source?: "edited_transcript" | "manual_description";
  can_extract: boolean; unavailable_reason?: string;
  authoritative: {
    project_id: number; project_name: string; record_id: number; recorder_id: number; recorder_name: string;
    recorder_role: string; occurred_at: string; location_id: number; building: string; floor: string; zone: string;
    photo_ids: number[];
  };
  latest_job?: EventExtractionJob; event?: SiteEvent;
};

export type DailyLogType = "CONSTRUCTION" | "SAFETY";
export type HazardClassification = "UNCLASSIFIED" | "GENERAL" | "MAJOR" | "NOT_HAZARD";
export type DailyLogIssue = {
  key: string; description: string; category: string; responsible_person?: string;
  evidence: SiteEvidenceRef[];
};
export type DailyLogEntry = {
  event_id: string; record_id: number; occurred_at: string; category: string;
  recorder_name: string; recorder_role: string;
  location: { building: string; floor: string; zone: string };
  construction: { activity?: string; crew?: string; worker_count?: number; progress?: number };
  issues: DailyLogIssue[]; field_evidence: Record<string, SiteEvidenceRef[]>;
};
export type DailyLogManual = {
  weather: string; machinery: string; production_notes: string; technical_quality_safety: string;
  inspection_acceptance: string; construction_other: string; pre_shift_inspection: string;
  pre_shift_education: string; dangerous_projects: string; high_risk_work: string;
  incident_response: string; personnel_duties: string; other_safety_management: string;
  hazard_classifications: Record<string, HazardClassification>;
};
export type DailyLog = {
  id: string; document_id: number; project_id: number; project_name: string; date: string;
  log_type: DailyLogType; version: number; status: "DRAFT" | "CONFIRMED";
  auto_content: { schema_version: "1.0"; entries: DailyLogEntry[] }; manual_content: DailyLogManual;
  stale: boolean; new_event_count: number;
  sources: { event_id: string; record_id: number; evidence: Record<string, unknown> }[];
  audits: { id: number; actor_id: number; action: string; created_at: string }[];
  created_by: number; updated_by: number; confirmed_by?: number; confirmed_at?: string;
  created_at: string; updated_at: string;
};
export type DailyLogList = { date: string; logs: DailyLog[] };
export type DailyLogVersion = {
  id: string; version: number; status: "DRAFT" | "CONFIRMED"; source_count: number;
  confirmed_at?: string; created_at: string;
};

export type KnowledgeDocument = {
  id: string; project_id: number; uploaded_by: number; title: string; original_name: string;
  mime_type: string; size_bytes: number; sha256: string; status: "PROCESSING" | "ACTIVE" | "FAILED" | "ARCHIVED";
  is_demo: boolean; error_message?: string; archived_by?: number; archived_at?: string;
  created_at: string; chunk_count: number; notice?: string;
};
export type RagCitation = { chunk_id: number; document_id: string; document_title: string; locator: string; excerpt: string; is_demo: boolean };
export type RagJob = {
  id: string; issue_id: string; project_id: number; status: "RUNNING" | "SUCCEEDED" | "FAILED" | "NO_EVIDENCE";
  provider: string; model: string; query: string; retrieved: { chunk_id: number; document_title: string; locator: string; content: string; score: number; is_demo: boolean }[];
  result?: { suspected_impact: string; recommendations: string[]; confidence: number; warnings: string[]; citations: RagCitation[] };
  error_message?: string; retry_of_job_id?: string; created_at: string; completed_at?: string;
};
export type Issue = {
  id: string; project_id: number; event_id: string; record_id: number; issue_index: number;
  category: "安全" | "文明施工/安全"; description: string;
  location: { building?: string; floor?: string; zone?: string }; evidence: SiteEvidenceRef[];
  occurred_at: string; status: string; ignored_reason?: string; task_id?: number;
  latest_rag_job?: RagJob; created_at: string;
};
export type TaskWorkflow = {
  id: number; project_id: number; source_record_id?: number; source_issue_id?: string;
  kind: "GENERAL" | "RECTIFICATION"; creator_id: number; assignee_id: number; title: string;
  description: string; due_at: string; status: string; created_at: string; updated_at: string;
  submissions: { id: string; round_number: number; submitted_by: number; note: string; created_at: string;
    photos: Photo[]; review?: { reviewer_id: number; decision: "APPROVE" | "REJECT"; reason?: string; created_at: string } }[];
  audits: { action: string; actor_id: number; payload?: unknown; created_at: string }[];
};
export type TaskReminders = { yesterday_unclosed: number[]; overdue: number[]; waiting_review: number[]; counts: { yesterday_unclosed: number; overdue: number; waiting_review: number } };
