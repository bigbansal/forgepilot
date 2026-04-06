import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MemoryService, MemoryEntry, MemoryStats } from '../../core/services/memory.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';

@Component({
  selector: 'fp-memory',
  standalone: true,
  imports: [CommonModule, FormsModule, EmptyStateComponent],
  template: `
    <section class="panel">
      <div class="header">
        <h1>Knowledge Base</h1>
        <div class="header-actions">
          <select [(ngModel)]="filterCategory" (ngModelChange)="refresh()">
            <option value="">All categories</option>
            <option *ngFor="let c of categories()" [value]="c">{{ c }}</option>
          </select>
          <button (click)="refresh()" [disabled]="loading()">Refresh</button>
        </div>
      </div>

      <!-- Stats bar -->
      <div class="stats-bar" *ngIf="stats()">
        <div class="stat">
          <span class="stat-value">{{ stats()!.total_entries }}</span>
          <span class="stat-label">Entries</span>
        </div>
        <div class="stat">
          <span class="stat-value">{{ stats()!.avg_confidence | number:'1.0-2' }}</span>
          <span class="stat-label">Avg Confidence</span>
        </div>
        <div class="stat" *ngFor="let pair of categoryPairs()">
          <span class="stat-value">{{ pair[1] }}</span>
          <span class="stat-label">{{ pair[0] }}</span>
        </div>
      </div>

      <p class="hint" *ngIf="error()">{{ error() }}</p>
      <p class="hint" *ngIf="loading()">Loading knowledge base...</p>

      <div class="entry-list" *ngIf="!loading() && entries().length">
        <div class="entry-card" *ngFor="let e of entries()">
          <div class="entry-header">
            <span class="entry-key">{{ e.key }}</span>
            <span class="entry-category cat-tag">{{ e.category }}</span>
          </div>
          <p class="entry-content">{{ e.content }}</p>
          <div class="entry-meta">
            <span class="meta-chip" *ngFor="let t of e.tags">{{ t }}</span>
            <span class="meta-chip confidence">⬤ {{ (e.confidence * 100) | number:'1.0-0' }}%</span>
            <span class="meta-chip retention">{{ e.retention_value }}</span>
            <span class="meta-chip">{{ e.created_at | date:'short' }}</span>
          </div>
          <div class="entry-actions">
            <button class="btn-sm btn-danger" (click)="deleteEntry(e)">Delete</button>
          </div>
        </div>
      </div>

      <div class="pagination" *ngIf="totalPages() > 1">
        <button [disabled]="page() <= 1" (click)="goPage(page() - 1)">← Prev</button>
        <span class="page-info">Page {{ page() }} / {{ totalPages() }}</span>
        <button [disabled]="page() >= totalPages()" (click)="goPage(page() + 1)">Next →</button>
      </div>

      <fp-empty-state
        *ngIf="!loading() && !entries().length"
        title="No knowledge captured yet"
        description="The Memory agent will store proven conventions and patterns as tasks are completed."
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

    .stats-bar {
      display: flex; gap: 16px; margin-bottom: 14px; padding: 10px 14px;
      background: var(--c-elevated); border-radius: var(--r-md);
      border: 1px solid var(--c-border-muted);
    }
    .stat { display: flex; flex-direction: column; align-items: center; }
    .stat-value { font-size: 16px; font-weight: 700; color: var(--c-text); }
    .stat-label { font-size: 10px; color: var(--c-text-muted); text-transform: capitalize; }

    .entry-list { display: flex; flex-direction: column; gap: 8px; }
    .entry-card {
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-md);
      padding: 10px 14px;
      background: var(--c-elevated);
      transition: border-color 0.15s;
    }
    .entry-card:hover { border-color: var(--c-accent); }
    .entry-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
    .entry-key { font-size: 13px; font-weight: 600; color: var(--c-text); font-family: var(--f-mono, monospace); }
    .cat-tag {
      font-size: 10.5px; background: var(--c-accent); color: #fff;
      border-radius: var(--r-sm); padding: 1px 6px;
    }
    .entry-content { font-size: 12px; color: var(--c-text-muted); line-height: 1.5; margin: 4px 0 8px; }
    .entry-meta { display: flex; gap: 6px; flex-wrap: wrap; }
    .meta-chip {
      font-size: 10.5px;
      background: var(--c-surface);
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-sm);
      padding: 2px 7px;
      color: var(--c-text-muted);
    }
    .confidence { color: #4ec9b0; }
    .retention { color: var(--c-accent); }
    .entry-actions { margin-top: 6px; }
    .btn-sm { padding: 2px 8px; font-size: 11px; }
    .btn-danger { color: #f44; border-color: #f443; }
    .btn-danger:hover { background: #f441; }

    .pagination { display: flex; justify-content: center; gap: 12px; align-items: center; margin-top: 12px; }
    .page-info { font-size: 12px; color: var(--c-text-muted); }
  `],
})
export class MemoryComponent implements OnInit {
  private readonly svc: MemoryService;

  readonly entries = signal<MemoryEntry[]>([]);
  readonly categories = signal<string[]>([]);
  readonly stats = signal<MemoryStats | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly page = signal(1);
  readonly total = signal(0);
  readonly pageSize = 50;

  filterCategory = '';

  constructor(svc: MemoryService) {
    this.svc = svc;
  }

  totalPages() { return Math.max(1, Math.ceil(this.total() / this.pageSize)); }

  categoryPairs(): [string, number][] {
    const s = this.stats();
    return s ? Object.entries(s.categories) : [];
  }

  ngOnInit(): void {
    this.svc.categories().subscribe(c => this.categories.set(c));
    this.svc.stats().subscribe(s => this.stats.set(s));
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.error.set('');
    this.svc.list({ page: this.page(), pageSize: this.pageSize, category: this.filterCategory || undefined }).subscribe({
      next: res => { this.entries.set(res.items); this.total.set(res.total); },
      error: err => this.error.set(err?.message || 'Failed to load knowledge base'),
      complete: () => this.loading.set(false),
    });
  }

  goPage(p: number): void {
    this.page.set(p);
    this.refresh();
  }

  deleteEntry(e: MemoryEntry): void {
    this.svc.delete(e.id).subscribe({ next: () => this.refresh() });
  }
}
