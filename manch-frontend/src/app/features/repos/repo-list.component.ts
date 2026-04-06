import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RepoService, RepoSummary, RepoCreate, RepoCloneResponse } from '../../core/services/repo.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'fp-repo-list',
  standalone: true,
  imports: [CommonModule, FormsModule, EmptyStateComponent, StatusBadgeComponent],
  template: `
    <section class="panel">
      <div class="header">
        <h1>Repositories</h1>
        <div class="header-actions">
          <button class="btn-add" (click)="showForm = !showForm; showCloneForm = false">{{ showForm ? 'Cancel' : '+ Add Repo' }}</button>
          <button class="btn-clone-action" (click)="showCloneForm = !showCloneForm; showForm = false">{{ showCloneForm ? 'Cancel' : '⤓ Clone URL' }}</button>
          <button (click)="refresh()" [disabled]="loading()">Refresh</button>
        </div>
      </div>

      <!-- Add Form -->
      <div class="add-form" *ngIf="showForm">
        <input [(ngModel)]="newName" placeholder="Repository name" />
        <input [(ngModel)]="newUrl" placeholder="Git URL (https://...)" />
        <input [(ngModel)]="newBranch" placeholder="Default branch" />
        <button [disabled]="!newName || !newUrl" (click)="addRepo()">Register</button>
      </div>

      <!-- Quick Clone Form -->
      <div class="clone-form" *ngIf="showCloneForm">
        <div class="clone-form-row">
          <input [(ngModel)]="cloneUrl" placeholder="Git URL to clone (https://github.com/...)" class="clone-input" />
          <input [(ngModel)]="cloneBranch" placeholder="Branch (main)" class="clone-branch" />
          <button class="btn-clone" [disabled]="!cloneUrl || cloning()" (click)="quickClone()">
            {{ cloning() ? 'Cloning...' : 'Clone' }}
          </button>
        </div>
        <p class="clone-hint">Clones the repo into a sandbox and auto-registers it. Shallow clone (depth 1) by default.</p>
      </div>

      <!-- Clone Result -->
      <div class="clone-result" *ngIf="cloneResult()">
        <div class="clone-result-header" [class.success]="cloneResult()!.exit_code === 0" [class.fail]="cloneResult()!.exit_code !== 0">
          {{ cloneResult()!.exit_code === 0 ? '✓ Cloned successfully' : '✗ Clone failed' }}
          — {{ cloneResult()!.repo_name }} ({{ cloneResult()!.branch }})
          <button class="btn-dismiss" (click)="cloneResult.set(null)">✕</button>
        </div>
        <pre class="clone-output">{{ cloneResult()!.stdout || cloneResult()!.stderr }}</pre>
        <div class="clone-meta" *ngIf="cloneResult()!.exit_code === 0">
          <span class="meta-chip">Sandbox: {{ cloneResult()!.sandbox_session_id | slice:0:12 }}…</span>
        </div>
      </div>

      <p class="hint" *ngIf="error()">{{ error() }}</p>
      <p class="hint" *ngIf="loading()">Loading repositories...</p>

      <div class="repo-grid" *ngIf="!loading() && repos().length">
        <div class="repo-card" *ngFor="let r of repos()">
          <div class="repo-header">
            <span class="repo-name">{{ r.name }}</span>
            <fp-status-badge [label]="r.is_active ? 'active' : 'inactive'" />
          </div>
          <p class="repo-url">{{ r.url }}</p>
          <div class="repo-meta">
            <span class="meta-chip">Branch: {{ r.default_branch }}</span>
            <span class="meta-chip" *ngIf="r.last_synced_at">Synced: {{ r.last_synced_at | date:'short' }}</span>
            <span class="meta-chip">Added: {{ r.created_at | date:'short' }}</span>
          </div>
          <p class="repo-desc" *ngIf="r.description">{{ r.description }}</p>
          <div class="repo-actions">
            <button class="btn-sm btn-clone" [disabled]="cloningId() === r.id" (click)="cloneRepo(r)">
              {{ cloningId() === r.id ? 'Cloning...' : '⤓ Clone' }}
            </button>
            <button class="btn-sm btn-danger" (click)="remove(r)">Remove</button>
          </div>
        </div>
      </div>

      <fp-empty-state
        *ngIf="!loading() && !repos().length && !showForm && !showCloneForm"
        title="No repositories registered"
        description="Add a repository or clone one from a URL."
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
    .header-actions { display: flex; gap: 8px; }
    button {
      border: 1px solid var(--c-border-muted);
      background: transparent;
      color: var(--c-text-muted);
      border-radius: var(--r-sm);
      padding: 4px 10px;
      cursor: pointer;
      font-size: 12px;
    }
    button:hover { background: var(--c-elevated); color: var(--c-text); }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-add { color: var(--c-accent); border-color: var(--c-accent); }
    .btn-clone-action { color: #4ecdc4; border-color: #4ecdc44a; }
    .btn-clone-action:hover { background: #4ecdc41a; }
    .hint { font-size: 12px; color: var(--c-text-muted); margin: 8px 0; }

    .add-form {
      display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap;
    }
    .add-form input, .clone-form input {
      border: 1px solid var(--c-border-muted);
      background: var(--c-elevated);
      color: var(--c-text);
      border-radius: var(--r-sm);
      padding: 6px 10px;
      font-size: 12px;
    }
    .add-form input { flex: 1; min-width: 150px; }

    /* Clone form */
    .clone-form { margin-bottom: 14px; }
    .clone-form-row { display: flex; gap: 8px; align-items: center; }
    .clone-input { flex: 3; min-width: 200px; }
    .clone-branch { flex: 1; min-width: 80px; max-width: 140px; }
    .clone-hint { font-size: 11px; color: var(--c-text-muted); margin: 4px 0 0; }
    .btn-clone { color: #4ecdc4; border-color: #4ecdc4; font-weight: 600; }
    .btn-clone:hover { background: #4ecdc41a; }

    /* Clone result */
    .clone-result {
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-md);
      padding: 10px 12px;
      margin-bottom: 14px;
      background: var(--c-elevated);
    }
    .clone-result-header {
      font-size: 12px; font-weight: 600; margin-bottom: 6px;
      display: flex; align-items: center; gap: 8px;
    }
    .clone-result-header.success { color: #4ecdc4; }
    .clone-result-header.fail { color: #f44; }
    .btn-dismiss {
      margin-left: auto; border: none; color: var(--c-text-muted);
      font-size: 14px; padding: 0 4px; background: transparent;
    }
    .clone-output {
      font-size: 11px; font-family: var(--f-mono, monospace);
      background: var(--c-surface); border-radius: var(--r-sm);
      padding: 8px 10px; margin: 0; max-height: 180px; overflow: auto;
      white-space: pre-wrap; word-break: break-all;
      color: var(--c-text-muted);
    }
    .clone-meta { display: flex; gap: 6px; margin-top: 6px; }

    .repo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 10px; }
    .repo-card {
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-md);
      padding: 12px 14px;
      background: var(--c-elevated);
      transition: border-color 0.15s;
    }
    .repo-card:hover { border-color: var(--c-accent); }
    .repo-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
    .repo-name { font-size: 13px; font-weight: 600; color: var(--c-text); }
    .repo-url { font-size: 11px; color: var(--c-accent); margin: 0 0 6px; font-family: var(--f-mono, monospace); word-break: break-all; }
    .repo-desc { font-size: 11.5px; color: var(--c-text-muted); margin: 6px 0 0; }
    .repo-meta { display: flex; gap: 6px; flex-wrap: wrap; }
    .meta-chip {
      font-size: 10.5px;
      background: var(--c-surface);
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-sm);
      padding: 2px 7px;
      color: var(--c-text-muted);
    }
    .repo-actions { margin-top: 8px; display: flex; gap: 6px; }
    .btn-sm { padding: 2px 8px; font-size: 11px; }
    .btn-danger { color: #f44; border-color: #f443; }
    .btn-danger:hover { background: #f441; }
  `],
})
export class RepoListComponent implements OnInit {
  private readonly svc: RepoService;

  readonly repos = signal<RepoSummary[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly cloning = signal(false);
  readonly cloningId = signal<string | null>(null);
  readonly cloneResult = signal<RepoCloneResponse | null>(null);

  showForm = false;
  showCloneForm = false;
  newName = '';
  newUrl = '';
  newBranch = 'main';
  cloneUrl = '';
  cloneBranch = 'main';

  constructor(svc: RepoService) {
    this.svc = svc;
  }

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.error.set('');
    this.svc.list(false).subscribe({
      next: list => this.repos.set(list),
      error: err => this.error.set(err?.message || 'Failed to load repos'),
      complete: () => this.loading.set(false),
    });
  }

  addRepo(): void {
    const body: RepoCreate = { name: this.newName, url: this.newUrl, default_branch: this.newBranch || 'main' };
    this.svc.create(body).subscribe({
      next: () => { this.showForm = false; this.newName = ''; this.newUrl = ''; this.newBranch = 'main'; this.refresh(); },
      error: err => this.error.set(err?.message || 'Failed to add repo'),
    });
  }

  remove(r: RepoSummary): void {
    this.svc.delete(r.id).subscribe({ next: () => this.refresh() });
  }

  /** Clone a registered repo */
  cloneRepo(r: RepoSummary): void {
    this.cloningId.set(r.id);
    this.cloneResult.set(null);
    this.svc.clone(r.id).subscribe({
      next: res => {
        this.cloneResult.set(res);
        this.cloningId.set(null);
        this.refresh();
      },
      error: err => {
        this.error.set(err?.error?.detail || err?.message || 'Clone failed');
        this.cloningId.set(null);
      },
    });
  }

  /** Quick clone from URL */
  quickClone(): void {
    this.cloning.set(true);
    this.cloneResult.set(null);
    this.svc.quickClone(this.cloneUrl, { branch: this.cloneBranch || 'main' }).subscribe({
      next: res => {
        this.cloneResult.set(res);
        this.cloning.set(false);
        this.showCloneForm = false;
        this.cloneUrl = '';
        this.cloneBranch = 'main';
        this.refresh();
      },
      error: err => {
        this.error.set(err?.error?.detail || err?.message || 'Clone failed');
        this.cloning.set(false);
      },
    });
  }
}
