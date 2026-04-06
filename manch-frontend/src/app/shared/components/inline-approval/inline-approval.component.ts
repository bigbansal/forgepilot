import { Component, EventEmitter, Input, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'fp-inline-approval',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="ia-wrap" [class.resolved]="isResolved">

      <!-- Risk badge row -->
      <div class="ia-header">
        <div class="ia-icon-wrap" [attr.data-risk]="riskLevel">
          <!-- shield icon -->
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        </div>
        <div class="ia-title-block">
          <span class="ia-title">Approval Required</span>
          <span class="ia-risk" [attr.data-risk]="riskLevel">{{ riskLevel | uppercase }} RISK</span>
        </div>
      </div>

      <!-- Reason -->
      <p class="ia-reason" *ngIf="reason">{{ reason }}</p>

      <!-- Actions -->
      <ng-container *ngIf="!isResolved">
        <div class="ia-reject-input" *ngIf="showRejectInput()">
          <textarea
            [(ngModel)]="rejectReason"
            rows="2"
            placeholder="Reason for rejection (optional)">
          </textarea>
        </div>
        <div class="ia-actions">
          <button type="button" class="ia-btn ia-approve"
            (click)="onApprove()" [disabled]="deciding()">
            <svg *ngIf="!deciding()" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            <svg *ngIf="deciding()" class="spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10" opacity=".25"/><path d="M22 12a10 10 0 0 0-10-10"/></svg>
            {{ deciding() ? 'Processing…' : 'Approve' }}
          </button>
          <button type="button" class="ia-btn ia-reject"
            (click)="toggleReject()" [disabled]="deciding()">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            Reject
          </button>
          <button type="button" class="ia-btn ia-confirm-reject"
            *ngIf="showRejectInput()" (click)="onReject()" [disabled]="deciding()">
            Confirm Reject
          </button>
        </div>
      </ng-container>

      <!-- Resolved state -->
      <div class="ia-resolved" *ngIf="isResolved">
        <svg *ngIf="decision === 'approve'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
        <svg *ngIf="decision !== 'approve'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        <span class="ia-decision" [class.approved]="decision === 'approve'" [class.rejected]="decision === 'reject'">
          {{ decision === 'approve' ? 'Approved — task is running' : 'Rejected' }}
        </span>
      </div>

    </div>
  `,
  styles: [`
    :host { display: block; padding: 0 16px 4px; }

    .ia-wrap {
      border: 1px solid rgba(210, 153, 34, 0.35);
      border-left: 3px solid #d29922;
      border-radius: 6px;
      background: rgba(210, 153, 34, 0.06);
      padding: 12px 14px 14px;
      transition: opacity 0.2s;
    }
    .ia-wrap.resolved {
      opacity: 0.65;
      border-color: var(--c-border-muted);
      border-left-color: var(--c-border-muted);
      background: transparent;
    }

    /* Header */
    .ia-header {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      margin-bottom: 8px;
    }
    .ia-icon-wrap {
      width: 28px;
      height: 28px;
      border-radius: 6px;
      background: rgba(210,153,34,0.15);
      color: #d29922;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .ia-icon-wrap[data-risk="critical"] {
      background: rgba(248,81,73,0.12);
      color: #f85149;
    }
    .ia-icon-wrap[data-risk="low"],
    .ia-icon-wrap[data-risk="medium"] {
      background: rgba(56,139,253,0.12);
      color: #58a6ff;
    }
    .ia-title-block {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .ia-title {
      font-size: 12.5px;
      font-weight: 600;
      color: var(--c-text);
    }
    .ia-risk {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: #d29922;
    }
    .ia-risk[data-risk="critical"] { color: #f85149; }
    .ia-risk[data-risk="low"],
    .ia-risk[data-risk="medium"]    { color: #58a6ff; }

    /* Reason */
    .ia-reason {
      font-size: 12px;
      color: var(--c-text-muted);
      margin: 0 0 12px;
      line-height: 1.5;
      padding-left: 38px;
    }

    /* Actions */
    .ia-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      padding-left: 38px;
    }
    .ia-btn {
      display: flex;
      align-items: center;
      gap: 5px;
      padding: 5px 12px;
      border-radius: 5px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s, opacity 0.15s;
      border: 1px solid transparent;
      background: transparent;
    }
    .ia-btn:disabled { opacity: 0.45; cursor: not-allowed; }

    .ia-approve {
      background: rgba(35,134,54,0.18);
      border-color: rgba(35,134,54,0.45);
      color: #3fb950;
    }
    .ia-approve:hover:not(:disabled) {
      background: rgba(35,134,54,0.3);
      border-color: #238636;
    }
    .ia-reject {
      border-color: rgba(218,54,51,0.3);
      color: #f85149;
    }
    .ia-reject:hover:not(:disabled) {
      background: rgba(218,54,51,0.1);
      border-color: rgba(218,54,51,0.5);
    }
    .ia-confirm-reject {
      background: rgba(218,54,51,0.15);
      border-color: rgba(218,54,51,0.4);
      color: #f85149;
    }
    .ia-confirm-reject:hover:not(:disabled) {
      background: rgba(218,54,51,0.25);
    }

    /* Reject textarea */
    .ia-reject-input {
      margin-bottom: 10px;
      padding-left: 38px;
    }
    .ia-reject-input textarea {
      width: 100%;
      padding: 6px 10px;
      border: 1px solid var(--c-border-muted);
      border-radius: 6px;
      background: var(--c-elevated);
      color: var(--c-text);
      font-size: 12px;
      resize: vertical;
      outline: none;
      box-sizing: border-box;
    }
    .ia-reject-input textarea:focus {
      border-color: rgba(56,139,253,0.5);
    }

    /* Resolved */
    .ia-resolved {
      display: flex;
      align-items: center;
      gap: 7px;
      padding-left: 38px;
    }
    .ia-decision {
      font-size: 12px;
      font-weight: 600;
    }
    .ia-decision.approved { color: #3fb950; }
    .ia-decision.rejected { color: #f85149; }

    /* Spinner */
    .spin { animation: spin 0.8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
  `]
})
export class InlineApprovalComponent {
  @Input() approvalId = '';
  @Input() taskId = '';
  @Input() riskLevel = 'high';
  @Input() reason = '';
  @Input() isResolved = false;
  @Input() decision: string | null = null;

  @Output() approved = new EventEmitter<{ approvalId: string }>();
  @Output() rejected = new EventEmitter<{ approvalId: string; reason: string }>();

  readonly deciding = signal(false);
  readonly showRejectInput = signal(false);
  rejectReason = '';

  onApprove(): void {
    this.deciding.set(true);
    this.approved.emit({ approvalId: this.approvalId });
  }

  toggleReject(): void {
    this.showRejectInput.set(!this.showRejectInput());
  }

  onReject(): void {
    this.deciding.set(true);
    this.rejected.emit({ approvalId: this.approvalId, reason: this.rejectReason });
  }

  /** Called by parent after the API call completes. */
  markDone(): void {
    this.deciding.set(false);
  }
}
