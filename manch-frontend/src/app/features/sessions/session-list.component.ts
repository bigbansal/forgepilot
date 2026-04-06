import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { SessionRecord } from '../../core/models/task.model';
import { SessionService } from '../../core/services/session.service';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';

@Component({
  selector: 'fp-session-list',
  standalone: true,
  imports: [CommonModule, RouterLink, StatusBadgeComponent, EmptyStateComponent],
  template: `
    <section class="panel">
      <div class="header">
        <h1>Sandbox Sessions</h1>
        <button (click)="refresh()" [disabled]="loading()">Refresh</button>
      </div>

      <p class="hint" *ngIf="error()">{{ error() }}</p>
      <p class="hint" *ngIf="loading()">Loading sessions...</p>

      <table *ngIf="!loading() && sessions().length">
        <thead>
          <tr>
            <th>ID</th>
            <th>Task</th>
            <th>Sandbox Session</th>
            <th>Status</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let s of sessions()">
            <td class="mono">{{ s.id | slice:0:8 }}…</td>
            <td>
              <a [routerLink]="['/tasks', s.task_id]" class="cell-link">
                {{ s.task_id | slice:0:8 }}…
              </a>
            </td>
            <td class="mono">{{ (s.sandbox_session_id || '–') | slice:0:12 }}{{ s.sandbox_session_id && s.sandbox_session_id.length > 12 ? '…' : '' }}</td>
            <td><fp-status-badge [label]="s.status" /></td>
            <td>{{ s.created_at | date: 'short' }}</td>
          </tr>
        </tbody>
      </table>

      <fp-empty-state
        *ngIf="!loading() && !sessions().length"
        title="No sandbox sessions"
        description="Sessions are created when tasks execute inside sandboxes."
        actionLabel="Start Chat"
        actionLink="/chat/thread"
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

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }

    h1 { margin: 0; font-size: 15px; font-weight: 600; }

    button {
      border: 1px solid var(--c-border-muted);
      background: transparent;
      color: var(--c-text-muted);
      border-radius: var(--r-sm);
      padding: 4px 10px;
      cursor: pointer;
      font-size: 12px;
      transition: background 0.1s, color 0.1s;
    }
    button:hover {
      background: var(--c-elevated);
      color: var(--c-text);
    }

    .hint {
      font-size: 12px;
      color: var(--c-text-muted);
      margin: 8px 0;
    }

    table {
      width: 100%;
      border-collapse: collapse;
    }

    th {
      border-bottom: 1px solid var(--c-border-muted);
      text-align: left;
      padding: 4px 8px;
      font-size: 10.5px;
      font-weight: 600;
      color: var(--c-text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    td {
      border-bottom: 1px solid var(--c-border-muted);
      padding: 7px 8px;
      font-size: 12px;
      color: var(--c-text-muted);
    }

    .mono { font-family: var(--font-mono, monospace); font-size: 11px; }

    .cell-link {
      color: var(--c-accent);
      text-decoration: none;
    }
    .cell-link:hover { text-decoration: underline; }
  `],
})
export class SessionListComponent implements OnInit {
  private readonly sessionService: SessionService;

  readonly sessions = signal<SessionRecord[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');

  constructor(sessionService: SessionService) {
    this.sessionService = sessionService;
  }

  ngOnInit(): void {
    this.refresh();
  }

  async refresh(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const list = await this.sessionService.listSessions();
      this.sessions.set(list);
    } catch (err: any) {
      this.error.set(err?.message || 'Failed to load sessions');
    } finally {
      this.loading.set(false);
    }
  }
}
