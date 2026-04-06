import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ApprovalService } from '../../core/services/approval.service';
import { ApprovalRequest } from '../../core/models/approval.model';

@Component({
  selector: 'fp-approval-queue',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="aq-page">
      <header class="aq-header">
        <h2 class="aq-title">Pending Approvals</h2>
        <button type="button" class="aq-refresh" (click)="load()">Refresh</button>
      </header>

      <div class="aq-error" *ngIf="error()">{{ error() }}</div>

      <div class="aq-empty" *ngIf="!loading() && approvals().length === 0 && !error()">
        <p>No pending approvals.</p>
      </div>

      <div class="aq-list" *ngIf="approvals().length > 0">
        <div
          class="aq-card"
          *ngFor="let a of approvals()"
          [routerLink]="['/tasks', a.task_id]"
          [queryParams]="{approval: a.id}">
          <div class="aq-card-top">
            <span class="aq-risk" [attr.data-risk]="a.risk_level">{{ a.risk_level | uppercase }}</span>
            <span class="aq-op">{{ a.operation_type || 'Action' }}</span>
            <time class="aq-time">{{ a.requested_at | date:'short' }}</time>
          </div>
          <p class="aq-reason" *ngIf="a.reason">{{ a.reason }}</p>
          <div class="aq-meta">
            <span class="aq-task-id">Task: {{ a.task_id | slice:0:8 }}…</span>
            <span class="aq-step" *ngIf="a.paused_step_index !== null">Step {{ a.paused_step_index }}</span>
          </div>
        </div>
      </div>

      <div class="aq-loading" *ngIf="loading()">Loading…</div>
    </div>
  `,
  styles: [`
    .aq-page {
      padding: 20px 24px;
      max-width: 800px;
    }
    .aq-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
    }
    .aq-title {
      font-size: 18px;
      font-weight: 600;
      color: var(--c-text);
      margin: 0;
    }
    .aq-refresh {
      padding: 4px 12px;
      border: 1px solid var(--c-border-muted);
      border-radius: 6px;
      background: transparent;
      color: var(--c-text-muted);
      font-size: 12px;
      cursor: pointer;
    }
    .aq-refresh:hover {
      background: var(--c-elevated);
      color: var(--c-text);
    }
    .aq-error {
      padding: 8px 12px;
      border: 1px solid #da3633;
      border-radius: 6px;
      background: rgba(218,54,51,0.1);
      color: #f85149;
      font-size: 12px;
      margin-bottom: 12px;
    }
    .aq-empty {
      text-align: center;
      color: var(--c-text-muted);
      padding: 40px 0;
      font-size: 13px;
    }
    .aq-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .aq-card {
      padding: 12px 16px;
      border: 1px solid var(--c-border-muted);
      border-radius: 8px;
      background: var(--c-surface);
      cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
      text-decoration: none;
      color: inherit;
      display: block;
    }
    .aq-card:hover {
      border-color: rgba(56,139,253,0.4);
      background: rgba(56,139,253,0.04);
    }
    .aq-card-top {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 4px;
    }
    .aq-risk {
      font-size: 10px;
      font-weight: 700;
      padding: 1px 6px;
      border-radius: 4px;
      background: rgba(255,165,0,0.2);
      color: #ffa500;
    }
    .aq-risk[data-risk="critical"] {
      background: rgba(255,0,0,0.15);
      color: #f85149;
    }
    .aq-risk[data-risk="high"] {
      background: rgba(255,165,0,0.15);
      color: #ffa500;
    }
    .aq-risk[data-risk="medium"] {
      background: rgba(56,139,253,0.15);
      color: #58a6ff;
    }
    .aq-op {
      font-size: 13px;
      font-weight: 500;
      color: var(--c-text);
    }
    .aq-time {
      font-size: 11px;
      color: var(--c-text-muted);
      margin-left: auto;
    }
    .aq-reason {
      font-size: 12px;
      color: var(--c-text-muted);
      margin: 2px 0 6px;
    }
    .aq-meta {
      display: flex;
      gap: 12px;
      font-size: 11px;
      color: var(--c-text-muted);
    }
    .aq-loading {
      text-align: center;
      color: var(--c-text-muted);
      font-size: 12px;
      padding: 20px;
    }
  `]
})
export class ApprovalQueueComponent implements OnInit {
  private readonly approvalService = inject(ApprovalService);

  readonly approvals = signal<ApprovalRequest[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');

  ngOnInit(): void {
    this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const list = await this.approvalService.listPending();
      this.approvals.set(list);
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to load approvals');
    } finally {
      this.loading.set(false);
    }
  }
}
