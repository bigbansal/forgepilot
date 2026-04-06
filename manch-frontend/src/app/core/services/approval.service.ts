import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ApiBaseService } from './api-base.service';
import { ApprovalDecision, ApprovalRequest, DiffArtifact } from '../models/approval.model';

@Injectable({ providedIn: 'root' })
export class ApprovalService {
  constructor(
    private readonly http: HttpClient,
    private readonly apiBase: ApiBaseService,
  ) {}

  /** List all pending approvals for the current user (global endpoint). */
  listPending(): Promise<ApprovalRequest[]> {
    return firstValueFrom(
      this.http.get<ApprovalRequest[]>(`${this.apiBase.baseUrl}/approvals`)
    );
  }

  /** Get count of pending approvals (for badge). */
  pendingCount(): Promise<{ count: number }> {
    return firstValueFrom(
      this.http.get<{ count: number }>(`${this.apiBase.baseUrl}/approvals/count`)
    );
  }

  /** List approvals for a specific task. */
  listForTask(taskId: string): Promise<ApprovalRequest[]> {
    return firstValueFrom(
      this.http.get<ApprovalRequest[]>(`${this.apiBase.baseUrl}/tasks/${taskId}/approvals`)
    );
  }

  /** Approve or reject an approval request. */
  decide(taskId: string, approvalId: string, decision: ApprovalDecision): Promise<unknown> {
    return firstValueFrom(
      this.http.post(
        `${this.apiBase.baseUrl}/tasks/${taskId}/approvals/${approvalId}/decide`,
        decision,
      )
    );
  }

  /** Get diff artifacts for a task (for Monaco diff viewer). */
  getTaskDiff(taskId: string): Promise<DiffArtifact[]> {
    return firstValueFrom(
      this.http.get<DiffArtifact[]>(`${this.apiBase.baseUrl}/tasks/${taskId}/diff`)
    );
  }
}
