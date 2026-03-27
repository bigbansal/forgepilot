import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Task } from '../../core/models/task.model';
import { TaskService } from '../../core/services/task.service';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';

@Component({
  selector: 'fp-task-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, StatusBadgeComponent, EmptyStateComponent],
  template: `
    <section class="panel">
      <div class="header">
        <h1>Tasks</h1>
        <div class="header-actions">
          <button (click)="refresh()" [disabled]="loading()">Refresh</button>
          <a routerLink="/chat/thread" class="link-btn">New Chat</a>
        </div>
      </div>

      <div class="filters">
        <input
          [(ngModel)]="searchText"
          placeholder="Search prompt..."
          aria-label="Search tasks"
        />

        <select [(ngModel)]="statusFilter" aria-label="Filter status">
          <option value="ALL">All statuses</option>
          <option *ngFor="let status of statuses" [value]="status">{{ status }}</option>
        </select>

        <select [(ngModel)]="sortBy" aria-label="Sort tasks">
          <option value="updated_desc">Updated (newest)</option>
          <option value="updated_asc">Updated (oldest)</option>
          <option value="created_desc">Created (newest)</option>
          <option value="created_asc">Created (oldest)</option>
        </select>
      </div>

      <p class="hint" *ngIf="error()">{{ error() }}</p>
      <p class="hint" *ngIf="loading()">Loading tasks...</p>

      <table *ngIf="!loading() && filteredTasks().length">
        <thead>
          <tr>
            <th>ID</th>
            <th>Status</th>
            <th>Prompt</th>
            <th>Created</th>
            <th>Updated</th>
            <th>Open</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let task of filteredTasks()">
            <td>{{ task.id }}</td>
            <td><fp-status-badge [label]="task.status" /></td>
            <td>{{ trimPrompt(task.prompt) }}</td>
            <td>{{ task.created_at | date: 'short' }}</td>
            <td>{{ task.updated_at | date: 'short' }}</td>
            <td><a [routerLink]="['/tasks', task.id]">View</a></td>
          </tr>
        </tbody>
      </table>

      <fp-empty-state
        *ngIf="!loading() && !filteredTasks().length"
        title="No tasks match current filters"
        description="Try clearing filters or start a new chat to create a task."
        actionLabel="Start Chat"
        actionLink="/chat/thread"
      />
    </section>
  `,
  styles: [
    `
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

      .header-actions { display: flex; gap: 6px; }

      h1 { margin: 0; font-size: 15px; font-weight: 600; }

      button, .link-btn {
        border: 1px solid var(--c-border-muted);
        background: transparent;
        color: var(--c-text-muted);
        border-radius: var(--r-sm);
        padding: 4px 10px;
        cursor: pointer;
        text-decoration: none;
        font-size: 12px;
        transition: background 0.1s, color 0.1s;
      }

      button:hover, .link-btn:hover {
        background: var(--c-elevated);
        color: var(--c-text);
      }

      .filters {
        display: grid;
        grid-template-columns: 1fr 160px 170px;
        gap: 6px;
        margin-bottom: 10px;
      }

      .filters input, .filters select {
        background: var(--c-elevated);
        border: 1px solid var(--c-border-muted);
        color: var(--c-text);
        border-radius: var(--r-sm);
        padding: 5px 8px;
        font-size: 12px;
        outline: none;
      }

      .filters input:focus, .filters select:focus {
        border-color: var(--c-accent);
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
        text-align: left;
        padding: 7px 8px;
        font-size: 12px;
        color: var(--c-text-muted);
      }

      tr:last-child td { border-bottom: none; }
      tr:hover td { background: rgba(255,255,255,0.02); }

      .hint { color: var(--c-text-faint); font-size: 12px; margin: 6px 0; }

      a { color: var(--c-accent); text-decoration: none; font-size: 12px; }
      a:hover { text-decoration: underline; }

      @media (max-width: 900px) {
        .filters { grid-template-columns: 1fr; }
      }
    `
  ]
})
export class TaskListComponent implements OnInit {
  readonly tasks = signal<Task[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');

  searchText = '';
  statusFilter: 'ALL' | Task['status'] = 'ALL';
  sortBy: 'updated_desc' | 'updated_asc' | 'created_desc' | 'created_asc' = 'updated_desc';

  readonly statuses: Task['status'][] = [
    'CREATED',
    'PLANNING',
    'RUNNING',
    'WAITING_APPROVAL',
    'VALIDATING',
    'COMPLETED',
    'FAILED',
    'CANCELLED'
  ];

  readonly filteredTasks = computed(() => {
    let data = this.tasks();

    const search = this.searchText.trim().toLowerCase();
    if (search) {
      data = data.filter((task) =>
        task.prompt.toLowerCase().includes(search) || task.id.toLowerCase().includes(search)
      );
    }

    if (this.statusFilter !== 'ALL') {
      data = data.filter((task) => task.status === this.statusFilter);
    }

    const sorted = [...data];
    const createdSort = (a: Task, b: Task) => a.created_at.localeCompare(b.created_at);
    const updatedSort = (a: Task, b: Task) => a.updated_at.localeCompare(b.updated_at);

    if (this.sortBy === 'created_asc') sorted.sort(createdSort);
    if (this.sortBy === 'created_desc') sorted.sort((a, b) => createdSort(b, a));
    if (this.sortBy === 'updated_asc') sorted.sort(updatedSort);
    if (this.sortBy === 'updated_desc') sorted.sort((a, b) => updatedSort(b, a));

    return sorted;
  });

  constructor(private readonly taskService: TaskService) {}

  ngOnInit(): void {
    void this.refresh();
  }

  async refresh(): Promise<void> {
    this.loading.set(true);
    this.error.set('');

    try {
      const tasks = await this.taskService.listTasks();
      this.tasks.set(tasks);
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Failed to load tasks');
    } finally {
      this.loading.set(false);
    }
  }

  trimPrompt(prompt: string): string {
    const clean = prompt.trim();
    if (clean.length <= 80) {
      return clean;
    }
    return `${clean.slice(0, 80)}...`;
  }
}
