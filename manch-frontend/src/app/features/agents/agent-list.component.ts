import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AgentService, RegisteredAgent } from '../../core/services/agent.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'fp-agent-list',
  standalone: true,
  imports: [CommonModule, EmptyStateComponent, StatusBadgeComponent],
  template: `
    <section class="panel">
      <div class="header">
        <h1>Agents</h1>
        <button (click)="refresh()" [disabled]="loading()">Refresh</button>
      </div>

      <p class="hint" *ngIf="error()">{{ error() }}</p>
      <p class="hint" *ngIf="loading()">Loading agents...</p>

      <div class="agent-grid" *ngIf="!loading() && agents().length">
        <div class="agent-card" *ngFor="let agent of agents()">
          <div class="agent-header">
            <span class="agent-name">{{ agent.name }}</span>
            <fp-status-badge [label]="agent.tier" />
          </div>
          <p class="agent-purpose">{{ agent.purpose }}</p>
          <div class="agent-meta">
            <span class="meta-chip">Model: {{ agent.model_class }}</span>
            <span class="meta-chip" [class.parallel-ok]="agent.parallel_safe">
              {{ agent.parallel_safe ? 'Parallel ✓' : 'Sequential' }}
            </span>
          </div>
        </div>
      </div>

      <fp-empty-state
        *ngIf="!loading() && !agents().length"
        title="No agents registered"
        description="Check the agent registry in the backend configuration."
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
      margin-bottom: 14px;
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

    .agent-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 10px;
    }

    .agent-card {
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-md);
      padding: 12px 14px;
      background: var(--c-elevated);
      transition: border-color 0.15s;
    }
    .agent-card:hover { border-color: var(--c-accent); }

    .agent-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }

    .agent-name {
      font-size: 13px;
      font-weight: 600;
      color: var(--c-text);
      text-transform: capitalize;
    }

    .agent-purpose {
      font-size: 11.5px;
      color: var(--c-text-muted);
      line-height: 1.4;
      margin: 0 0 8px;
    }

    .agent-meta { display: flex; gap: 6px; flex-wrap: wrap; }

    .meta-chip {
      font-size: 10.5px;
      background: var(--c-surface);
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-sm);
      padding: 2px 7px;
      color: var(--c-text-muted);
    }
    .meta-chip.parallel-ok { color: #4ec9b0; border-color: #4ec9b033; }
  `],
})
export class AgentListComponent implements OnInit {
  private readonly agentService: AgentService;

  readonly agents = signal<RegisteredAgent[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');

  constructor(agentService: AgentService) {
    this.agentService = agentService;
  }

  ngOnInit(): void {
    this.refresh();
  }

  async refresh(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const list = await this.agentService.listRegistryAgents();
      this.agents.set(list);
    } catch (err: any) {
      this.error.set(err?.message || 'Failed to load agents');
    } finally {
      this.loading.set(false);
    }
  }
}
