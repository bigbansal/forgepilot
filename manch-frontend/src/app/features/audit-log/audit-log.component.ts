import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuditLogService, AuditLogEntry } from '../../core/services/audit-log.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';

@Component({
  selector: 'fp-audit-log',
  standalone: true,
  imports: [CommonModule, FormsModule, EmptyStateComponent],
  template: `
    <section class="panel">
      <div class="header">
        <h1>Audit Log</h1>
        <div class="header-actions">
          <select [(ngModel)]="filterAction" (ngModelChange)="refresh()">
            <option value="">All actions</option>
            <option *ngFor="let a of actions()" [value]="a">{{ a }}</option>
          </select>
          <button (click)="refresh()" [disabled]="loading()">Refresh</button>
        </div>
      </div>

      <p class="hint" *ngIf="error()">{{ error() }}</p>
      <p class="hint" *ngIf="loading()">Loading audit log...</p>

      <div class="log-table" *ngIf="!loading() && entries().length">
        <div class="log-header">
          <span class="col-time">Time</span>
          <span class="col-action">Action</span>
          <span class="col-resource">Resource</span>
          <span class="col-detail">Detail</span>
        </div>
        <div class="log-row" *ngFor="let e of entries()">
          <span class="col-time">{{ e.created_at | date:'short' }}</span>
          <span class="col-action action-tag">{{ e.action }}</span>
          <span class="col-resource">{{ e.resource_type || '—' }}<span class="res-id" *ngIf="e.resource_id"> #{{ e.resource_id | slice:0:8 }}</span></span>
          <span class="col-detail">{{ e.detail || '—' }}</span>
        </div>
      </div>

      <div class="pagination" *ngIf="totalPages() > 1">
        <button [disabled]="page() <= 1" (click)="goPage(page() - 1)">← Prev</button>
        <span class="page-info">Page {{ page() }} / {{ totalPages() }}</span>
        <button [disabled]="page() >= totalPages()" (click)="goPage(page() + 1)">Next →</button>
      </div>

      <fp-empty-state
        *ngIf="!loading() && !entries().length"
        title="No audit events recorded"
        description="Audit events will appear here as the system is used."
      />
    </section>
  `,
  styles: [`
    .panel {
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-lg);
      padding: 14px 16px;
      background: var(--c-surface);
    }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
    h1 { margin: 0; font-size: 15px; font-weight: 600; }
    .header-actions { display: flex; gap: 8px; align-items: center; }
    select, button {
      border: 1px solid var(--c-border-muted);
      background: transparent;
      color: var(--c-text-muted);
      border-radius: var(--r-sm);
      padding: 4px 10px;
      cursor: pointer;
      font-size: 12px;
    }
    select:focus, button:hover { background: var(--c-elevated); color: var(--c-text); }
    .hint { font-size: 12px; color: var(--c-text-muted); margin: 8px 0; }

    .log-table { font-size: 12px; }
    .log-header, .log-row { display: grid; grid-template-columns: 130px 160px 160px 1fr; gap: 8px; padding: 6px 0; align-items: baseline; }
    .log-header { font-weight: 600; color: var(--c-text-muted); border-bottom: 1px solid var(--c-border-muted); margin-bottom: 2px; }
    .log-row { border-bottom: 1px solid var(--c-border-muted); }
    .log-row:hover { background: var(--c-elevated); }

    .action-tag { font-family: var(--f-mono, monospace); color: var(--c-accent); font-size: 11.5px; }
    .res-id { color: var(--c-text-muted); font-size: 10.5px; margin-left: 4px; }
    .col-detail { color: var(--c-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    .pagination { display: flex; justify-content: center; gap: 12px; align-items: center; margin-top: 12px; }
    .page-info { font-size: 12px; color: var(--c-text-muted); }
  `],
})
export class AuditLogComponent implements OnInit {
  private readonly svc: AuditLogService;

  readonly entries = signal<AuditLogEntry[]>([]);
  readonly actions = signal<string[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly page = signal(1);
  readonly total = signal(0);
  readonly pageSize = 50;

  filterAction = '';

  constructor(svc: AuditLogService) {
    this.svc = svc;
  }

  totalPages() { return Math.max(1, Math.ceil(this.total() / this.pageSize)); }

  ngOnInit(): void {
    this.svc.listActions().subscribe(a => this.actions.set(a));
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.error.set('');
    this.svc.list({ page: this.page(), pageSize: this.pageSize, action: this.filterAction || undefined }).subscribe({
      next: res => { this.entries.set(res.items); this.total.set(res.total); },
      error: err => this.error.set(err?.message || 'Failed to load audit log'),
      complete: () => this.loading.set(false),
    });
  }

  goPage(p: number): void {
    this.page.set(p);
    this.refresh();
  }
}
