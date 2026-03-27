import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { EventStreamService } from '../../core/services/event-stream.service';
import { TaskService } from '../../core/services/task.service';
import { StreamEvent } from '../../core/models/event.model';
import { SessionRecord, Task, TaskMessage } from '../../core/models/task.model';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';

type DetailTab = 'overview' | 'plan' | 'output' | 'events';
type PlanStepState = 'done' | 'active' | 'pending';

@Component({
  selector: 'fp-task-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, StatusBadgeComponent, EmptyStateComponent],
  template: `
    <section class="panel" *ngIf="task(); else missing">
      <header class="header">
        <div>
          <h1>Task {{ task()!.id }}</h1>
          <p>{{ task()!.prompt }}</p>
        </div>
        <a routerLink="/tasks">Back to Tasks</a>
      </header>

      <div class="meta">
        <span class="chip">Status: <fp-status-badge [label]="task()!.status" /></span>
        <span class="chip">Created: {{ task()!.created_at | date: 'short' }}</span>
        <span class="chip">Updated: {{ task()!.updated_at | date: 'short' }}</span>
      </div>

      <nav class="tabs">
        <button [class.active]="activeTab() === 'overview'" (click)="activeTab.set('overview')">Overview</button>
        <button [class.active]="activeTab() === 'plan'" (click)="activeTab.set('plan')">Plan</button>
        <button [class.active]="activeTab() === 'output'" (click)="activeTab.set('output')">Output</button>
        <button [class.active]="activeTab() === 'events'" (click)="activeTab.set('events')">Events</button>
      </nav>

      <section *ngIf="activeTab() === 'overview'" class="tab-content">
        <h3>Linked Sessions</h3>
        <ul *ngIf="taskSessions().length; else noSessions">
          <li *ngFor="let session of taskSessions()">
            {{ session.id }} • {{ session.status }} • {{ session.created_at | date: 'short' }}
          </li>
        </ul>
        <ng-template #noSessions>
          <fp-empty-state title="No sessions yet" description="Sessions will appear once runtime execution starts." />
        </ng-template>
      </section>

      <section *ngIf="activeTab() === 'plan'" class="tab-content">
        <h3>Execution Plan</h3>
        <ul class="plan-list">
          <li *ngFor="let step of planSteps()" [class.done]="step.state === 'done'" [class.active]="step.state === 'active'">
            <span class="dot"></span>
            <div>
              <strong>{{ step.title }}</strong>
              <p>{{ step.detail }}</p>
            </div>
          </li>
        </ul>
      </section>

      <section *ngIf="activeTab() === 'output'" class="tab-content">
        <h3>Task Output</h3>
        <div class="message" *ngFor="let message of taskMessages()">
          <div class="message-meta">{{ message.role }} • {{ message.created_at | date: 'shortTime' }}</div>
          <pre>{{ message.content }}</pre>
        </div>
        <fp-empty-state
          *ngIf="!taskMessages().length"
          title="No persisted output yet"
          description="Output messages are stored after task execution progresses."
        />
      </section>

      <section *ngIf="activeTab() === 'events'" class="tab-content">
        <h3>Live Task Events</h3>
        <div class="event" *ngFor="let event of taskEvents()">
          <div class="message-meta">{{ event.type }} • {{ event.timestamp | date: 'shortTime' }}</div>
          <pre>{{ event.payload | json }}</pre>
        </div>
        <fp-empty-state
          *ngIf="!taskEvents().length"
          title="No events yet"
          description="Live task events will appear here while execution is active."
        />
      </section>

      <p class="error" *ngIf="error()">{{ error() }}</p>
    </section>

    <ng-template #missing>
      <section class="panel">
        <h1>Task Detail</h1>
        <p class="hint">Task not loaded.</p>
        <p class="error" *ngIf="error()">{{ error() }}</p>
      </section>
    </ng-template>
  `,
  styles: [
    `
      .panel {
        border: 1px solid #1f2937;
        border-radius: 12px;
        padding: 1rem;
        background: #0f172a;
      }

      .header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
      }

      .header h1 {
        margin: 0;
      }

      .header p {
        margin: 0.3rem 0 0;
        color: #93c5fd;
      }

      .header a {
        color: #93c5fd;
        text-decoration: none;
      }

      .meta {
        margin-top: 0.8rem;
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
      }

      .chip {
        border: 1px solid #334155;
        border-radius: 999px;
        padding: 0.2rem 0.55rem;
        font-size: 0.8rem;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
      }

      .tabs {
        margin-top: 1rem;
        display: flex;
        gap: 0.45rem;
      }

      .tabs button {
        border: 1px solid #334155;
        background: #111827;
        color: #e5e7eb;
        border-radius: 8px;
        padding: 0.35rem 0.65rem;
        cursor: pointer;
      }

      .tabs button.active {
        border-color: #2563eb;
        background: #1d4ed8;
      }

      .tab-content {
        margin-top: 1rem;
      }

      .tab-content h3 {
        margin: 0 0 0.55rem;
      }

      .plan-list {
        margin: 0;
        padding: 0;
        list-style: none;
        display: grid;
        gap: 0.6rem;
      }

      .plan-list li {
        display: flex;
        gap: 0.5rem;
        align-items: flex-start;
        border: 1px solid #1f2937;
        border-radius: 8px;
        background: #111827;
        padding: 0.6rem;
      }

      .plan-list li.done {
        border-color: #15803d;
      }

      .plan-list li.active {
        border-color: #2563eb;
      }

      .plan-list .dot {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        margin-top: 0.25rem;
        background: #334155;
      }

      .plan-list li.done .dot {
        background: #22c55e;
      }

      .plan-list li.active .dot {
        background: #60a5fa;
      }

      .plan-list strong {
        display: block;
        margin-bottom: 0.2rem;
      }

      .plan-list p {
        margin: 0;
        color: #94a3b8;
        font-size: 0.85rem;
      }

      .message,
      .event {
        border: 1px solid #1f2937;
        border-radius: 8px;
        background: #111827;
        padding: 0.55rem;
        margin-bottom: 0.55rem;
      }

      .message-meta {
        color: #94a3b8;
        font-size: 0.8rem;
        margin-bottom: 0.35rem;
      }

      pre {
        margin: 0;
        white-space: pre-wrap;
        word-break: break-word;
        background: #0b1325;
        border: 1px solid #243044;
        border-radius: 8px;
        padding: 0.6rem;
      }

      .hint {
        color: #94a3b8;
      }

      .error {
        color: #fca5a5;
        margin-top: 0.65rem;
      }
    `
  ]
})
export class TaskDetailComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly taskService = inject(TaskService);
  private readonly eventStream = inject(EventStreamService);

  readonly activeTab = signal<DetailTab>('overview');
  readonly task = signal<Task | null>(null);
  readonly taskMessages = signal<TaskMessage[]>([]);
  readonly sessions = signal<SessionRecord[]>([]);
  readonly taskEvents = signal<StreamEvent[]>([]);
  readonly error = signal('');

  readonly taskSessions = computed(() => {
    const taskId = this.task()?.id;
    if (!taskId) {
      return [];
    }
    return this.sessions().filter((session) => session.task_id === taskId);
  });

  readonly planSteps = computed(() => {
    const status = this.task()?.status;
    const currentIndex =
      status === 'CREATED' ? 0 :
      status === 'PLANNING' ? 1 :
      status === 'RUNNING' ? 2 :
      status === 'WAITING_APPROVAL' ? 3 :
      status === 'VALIDATING' ? 4 :
      status === 'COMPLETED' ? 5 :
      status === 'FAILED' || status === 'CANCELLED' ? 4 :
      0;

    const base = [
      { title: 'Task created', detail: 'Prompt accepted and task created in backend.' },
      { title: 'Plan generated', detail: 'System prepares implementation approach and workflow.' },
      { title: 'Execution running', detail: 'Runtime executes task actions and tools.' },
      { title: 'Approval check', detail: 'High-risk operations wait for explicit approval if needed.' },
      { title: 'Validation', detail: 'Result is validated with output and event checks.' },
      { title: 'Completed', detail: 'Task finished and final output persisted.' },
    ];

    return base.map((step, index): { title: string; detail: string; state: PlanStepState } => {
      if (index < currentIndex) {
        return { ...step, state: 'done' };
      }
      if (index === currentIndex) {
        return { ...step, state: 'active' };
      }
      return { ...step, state: 'pending' };
    });
  });

  private taskId = '';
  private disconnectEvents?: () => void;

  async ngOnInit(): Promise<void> {
    this.taskId = String(this.route.snapshot.paramMap.get('id') || '').trim();
    if (!this.taskId) {
      this.error.set('Task id is missing.');
      return;
    }

    await this.load();
    this.disconnectEvents = this.eventStream.connect(
      (event) => this.onEvent(event),
      () => undefined
    );
  }

  ngOnDestroy(): void {
    this.disconnectEvents?.();
  }

  private async load(): Promise<void> {
    this.error.set('');
    try {
      const [task, messages, sessions] = await Promise.all([
        this.taskService.getTask(this.taskId),
        this.taskService.getTaskMessages(this.taskId),
        this.taskService.listSessions(),
      ]);
      this.task.set(task);
      this.taskMessages.set(messages);
      this.sessions.set(sessions);
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Failed to load task detail');
    }
  }

  private onEvent(event: StreamEvent): void {
    const eventTaskId = String(event.payload['task_id'] ?? '');
    if (!eventTaskId || eventTaskId !== this.taskId) {
      return;
    }

    this.taskEvents.update((list) => [event, ...list].slice(0, 60));

    if (event.type === 'task.completed' || event.type === 'task.running' || event.type === 'task.waiting_approval') {
      void this.load();
    }
  }
}
