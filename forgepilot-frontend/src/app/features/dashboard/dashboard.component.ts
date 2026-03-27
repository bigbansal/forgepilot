import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { TaskService } from '../../core/services/task.service';
import { ChatService } from '../../core/services/chat.service';
import { ApiBaseService } from '../../core/services/api-base.service';
import { Task } from '../../core/models/task.model';

@Component({
  selector: 'fp-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="page">
      <div class="header">
        <h1>Dashboard</h1>
        <button (click)="refresh()" [disabled]="loading()">Refresh</button>
      </div>

      <p class="error" *ngIf="error()">{{ error() }}</p>

      <div class="grid">
        <article class="stat-card">
          <h3>API Health</h3>
          <p class="stat">
            <span class="state-dot" [class.ok]="backendHealthy()" [class.bad]="!backendHealthy()"></span>
            {{ backendHealthy() ? 'Healthy' : 'Down' }}
          </p>
        </article>

        <article class="stat-card">
          <h3>Total tasks</h3>
          <p class="stat">{{ tasks().length }}</p>
        </article>

        <article class="stat-card">
          <h3>Completed</h3>
          <p class="stat" style="color: var(--c-success)">{{ completedCount() }}</p>
        </article>

        <article class="stat-card">
          <h3>Running</h3>
          <p class="stat" style="color: var(--c-running)">{{ runningCount() }}</p>
        </article>

        <article class="stat-card">
          <h3>Failed</h3>
          <p class="stat" style="color: var(--c-danger)">{{ failedCount() }}</p>
        </article>

        <article class="stat-card">
          <h3>Chats</h3>
          <p class="stat">{{ conversationCount() }}</p>
          <p><a routerLink="/chat">Open chat &rarr;</a></p>
        </article>
      </div>

      <article class="panel recent">
        <h3>Recent Tasks</h3>
        <table *ngIf="recentTasks().length">
          <thead>
            <tr>
              <th>ID</th>
              <th>Status</th>
              <th>Prompt</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let task of recentTasks()">
              <td style="font-family: var(--font-mono); font-size: 11px; color: var(--c-text-faint)">{{ task.id.slice(0, 8) }}&hellip;</td>
              <td>{{ task.status }}</td>
              <td>{{ trimPrompt(task.prompt) }}</td>
              <td><a [routerLink]="['/tasks', task.id]">View</a></td>
            </tr>
          </tbody>
        </table>
        <p class="hint" *ngIf="!recentTasks().length">No tasks yet.</p>
      </article>
    </section>
  `,
  styles: [
    `
      .page {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }

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
        margin-bottom: 12px;
      }

      h1 { margin: 0; font-size: 15px; font-weight: 600; }

      h3 {
        margin: 0 0 10px;
        font-size: 11.5px;
        font-weight: 600;
        color: var(--c-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }

      .stat {
        font-size: 22px;
        font-weight: 700;
        color: var(--c-text);
        margin: 0;
        line-height: 1.2;
      }

      .stat-label {
        font-size: 11.5px;
        color: var(--c-text-muted);
        margin: 2px 0 0;
      }

      p { margin: 3px 0; font-size: 12.5px; color: var(--c-text-muted); }

      .error { color: var(--c-danger); margin: 0; font-size: 12px; }

      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 8px;
      }

      .stat-card {
        border: 1px solid var(--c-border-muted);
        border-radius: var(--r);
        padding: 12px 14px;
        background: var(--c-elevated);
      }

      .state-dot {
        display: inline-block;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        margin-right: 5px;
      }
      .state-dot.ok  { background: var(--c-success); }
      .state-dot.bad { background: var(--c-danger); }

      .recent table {
        width: 100%;
        border-collapse: collapse;
      }

      .recent th {
        border-bottom: 1px solid var(--c-border-muted);
        text-align: left;
        padding: 4px 6px;
        font-size: 10.5px;
        font-weight: 600;
        color: var(--c-text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }

      .recent td {
        border-bottom: 1px solid var(--c-border-muted);
        text-align: left;
        padding: 6px 6px;
        font-size: 12px;
        color: var(--c-text-muted);
      }

      .recent tr:last-child td { border-bottom: none; }

      .recent tr:hover td { background: rgba(255,255,255,0.02); }

      .hint { margin: 8px 0 0; color: var(--c-text-faint); font-size: 12px; }

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

      button:hover { background: var(--c-elevated); color: var(--c-text); }

      a {
        color: var(--c-accent);
        text-decoration: none;
        font-size: 12px;
      }

      a:hover { text-decoration: underline; }
    `
  ]
})
export class DashboardComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly apiBase = inject(ApiBaseService);
  private readonly taskService = inject(TaskService);
  private readonly chatService = inject(ChatService);

  readonly loading = signal(false);
  readonly error = signal('');
  readonly backendHealthy = signal(false);
  readonly tasks = signal<Task[]>([]);
  readonly conversationCount = signal(0);

  readonly runningCount = computed(() => this.tasks().filter((task) => task.status === 'RUNNING').length);
  readonly completedCount = computed(() => this.tasks().filter((task) => task.status === 'COMPLETED').length);
  readonly failedCount = computed(() => this.tasks().filter((task) => task.status === 'FAILED').length);
  readonly recentTasks = computed(() => this.tasks().slice(0, 5));

  ngOnInit(): void {
    void this.refresh();
  }

  async refresh(): Promise<void> {
    this.loading.set(true);
    this.error.set('');

    try {
      const [healthResponse, tasks, conversations] = await Promise.all([
        firstValueFrom(this.http.get<{ status?: string }>(`${this.apiBase.baseUrl}/health`)),
        this.taskService.listTasks(),
        this.chatService.listConversations(),
      ]);

      this.backendHealthy.set(healthResponse.status === 'ok');
      this.tasks.set(tasks);
      this.conversationCount.set(conversations.length);
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Failed to load dashboard');
      this.backendHealthy.set(false);
    } finally {
      this.loading.set(false);
    }
  }

  trimPrompt(prompt: string): string {
    const clean = prompt.trim();
    if (clean.length <= 72) {
      return clean;
    }
    return `${clean.slice(0, 72)}...`;
  }
}
