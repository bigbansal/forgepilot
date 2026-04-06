export interface ApprovalRequest {
  id: string;
  task_id: string;
  step_id: string | null;
  operation_type: string | null;
  risk_level: string | null;
  reason: string | null;
  decision: string | null;
  decided_by: string | null;
  paused_step_index: number | null;
  requested_at: string;
  resolved_at: string | null;
}

export interface ApprovalDecision {
  decision: 'approve' | 'reject';
  reason?: string;
}

export interface DiffArtifact {
  id: string;
  step_id: string | null;
  content: string;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
}
