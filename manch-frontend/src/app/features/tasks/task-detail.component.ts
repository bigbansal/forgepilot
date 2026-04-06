import { Component, OnDestroy, OnInit, ViewChild, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { EventStreamService } from '../../core/services/event-stream.service';
import { TaskService, PlanStep } from '../../core/services/task.service';
import { ApprovalService } from '../../core/services/approval.service';
import { StreamEvent } from '../../core/models/event.model';
import { DiffArtifact } from '../../core/models/approval.model';
import { SessionRecord, Task, TaskMessage } from '../../core/models/task.model';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { DiffViewerComponent, DiffEntry } from '../../shared/components/diff-viewer/diff-viewer.component';
import { TerminalComponent } from '../../shared/components/terminal/terminal.component';

type DetailTab = 'overview' | 'plan' | 'output' | 'diff' | 'terminal' | 'events';

@Component({
  selector: 'fp-task-detail',
  standalone: true,
  imports: [
    CommonModule, RouterLink, StatusBadgeComponent, EmptyStateComponent,
    DiffViewerComponent, TerminalComponent,
  ],
  template: `
    <section class="panel" *ngIf="task(); else missing">
      <!-- ── Header ── -->
      <header class="header">
        <div class="header-left">
          <a routerLink="/tasks" class="back-link">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
          </a>
          <div>
            <h1>Task {{ task()!.id.slice(0, 8) }}</h1>
            <p class="prompt-text">{{ task()!.prompt }}</p>
          </div>
        </div>
        <fp-status-badge [label]="task()!.status" />
      </header>

      <!-- ── Meta chips ── -->
      <div class="meta">
        <span class="chip">Created {{ task()!.created_at | date: 'short' }}</span>
        <span class="chip">Updated {{ task()!.updated_at | date: 'short' }}</span>
        <span class="chip" *ngIf="taskSessions().length">Sessions: {{ taskSessions().length }}</span>
      </div>

      <!-- ── Tabs ── -->
      <nav class="tabs">
        <button [class.active]="activeTab() === 'overview'" (click)="activeTab.set('overview')">Overview</button>
        <button [class.active]="activeTab() === 'plan'" (click)="switchToPlan()">
          Plan
          <span class="tab-count" *ngIf="planSteps().length">({{ planSteps().length }})</span>
        </button>
        <button [class.active]="activeTab() === 'output'" (click)="activeTab.set('output')">Output</button>
        <button [class.active]="activeTab() === 'diff'" (click)="loadDiffTab()">Diff</button>
        <button [class.active]="activeTab() === 'terminal'" (click)="activeTab.set('terminal')">Terminal</button>
        <button [class.active]="activeTab() === 'events'" (click)="activeTab.set('events')">
          Events
          <span class="tab-count" *ngIf="taskEvents().length">({{ taskEvents().length }})</span>
        </button>
      </nav>

      <!-- ════════════ OVERVIEW TAB ════════════ -->
      <section *ngIf="activeTab() === 'overview'" class="tab-content">
        <h3>Linked Sessions</h3>
        <div class="session-grid" *ngIf="taskSessions().length; else noSessions">
          <div class="session-card" *ngFor="let s of taskSessions()">
            <div class="session-id">{{ s.id.slice(0, 8) }}</div>
            <fp-status-badge [label]="s.status" />
            <span class="session-date">{{ s.created_at | date: 'short' }}</span>
          </div>
        </div>
        <ng-template #noSessions>
          <fp-empty-state title="No sessions yet" description="Sessions will appear once runtime execution starts." />
        </ng-template>
      </section>

      <!-- ════════════ PLAN TAB ════════════ -->
      <section *ngIf="activeTab() === 'plan'" class="tab-content">
        <h3>Execution Plan</h3>
        <div class="plan-timeline" *ngIf="planSteps().length; else noPlan">
          <div
            class="plan-step"
            *ngFor="let step of planSteps(); let i = index"
            [attr.data-status]="step.status">
            <div class="step-indicator">
              <span class="step-num">{{ i + 1 }}</span>
              <span class="step-line" *ngIf="i < planSteps().length - 1"></span>
            </div>
            <div class="step-body">
              <div class="step-header">
                <span class="agent-chip">{{ step.agent_name }}</span>
                <fp-status-badge [label]="step.status" />
                <span class="step-time" *ngIf="step.started_at">{{ step.started_at | date: 'shortTime' }}</span>
              </div>
              <p class="step-desc">{{ step.description }}</p>
              <pre class="step-output" *ngIf="step.output_summary">{{ step.output_summary }}</pre>
            </div>
          </div>
        </div>
        <ng-template #noPlan>
          <fp-empty-state title="No plan steps yet" description="Plan steps appear after the Maestro agent generates a plan." />
        </ng-template>
      </section>

      <!-- ════════════ OUTPUT TAB ════════════ -->
      <section *ngIf="activeTab() === 'output'" class="tab-content">
        <h3>Task Output</h3>
        <div class="message" *ngFor="let msg of taskMessages()">
          <div class="message-meta">{{ msg.role }} &bull; {{ msg.created_at | date: 'shortTime' }}</div>
          <pre>{{ msg.content }}</pre>
        </div>
        <fp-empty-state
          *ngIf="!taskMessages().length"
          title="No persisted output yet"
          description="Output messages are stored after task execution progresses."
        />
      </section>

      <!-- ════════════ DIFF TAB (Monaco) ════════════ -->
      <section *ngIf="activeTab() === 'diff'" class="tab-content diff-tab">
        <h3>Code Changes</h3>
        <fp-diff-viewer
          *ngIf="diffEntries().length"
          [entries]="diffEntries()"
        />
        <fp-empty-state
          *ngIf="!diffEntries().length && !diffLoading()"
          title="No diff artifacts"
          description="Diff artifacts are captured after code changes in the sandbox."
        />
        <p *ngIf="diffLoading()" class="hint">Loading diffs…</p>
      </section>

      <!-- ════════════ TERMINAL TAB (xterm) ════════════ -->
      <section *ngIf="activeTab() === 'terminal'" class="tab-content terminal-tab">
        <fp-terminal
          #taskTerminal
          title="Task Output"
        />
      </section>

      <!-- ════════════ EVENTS TAB ════════════ -->
      <section *ngIf="activeTab() === 'events'" class="tab-content">
        <h3>Live Events</h3>
        <div class="event" *ngFor="let event of taskEvents()">
          <div class="event-header">
            <span class="event-type">{{ event.type }}</span>
            <span class="event-time">{{ event.timestamp | date: 'shortTime' }}</span>
          </div>
          <pre class="event-payload">{{ event.payload | json }}</pre>
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
        <p class="hint" *ngIf="!error()">Loading task…</p>
        <p class="error" *ngIf="error()">{{ error() }}</p>
      </section>
    </ng-template>
  `,
  styles: [`
    .panel {
      border: 1px solid #1f2937;
      border-radius: 12px;
      padding: 1.2rem;
      background: #0f172a;
    }

    /* ── Header ── */
    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
    }
    .header-left {
      display: flex;
      gap: 0.75rem;
      align-items: flex-start;
    }
    .back-link {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 28px; height: 28px;
      border: 1px solid #334155;
      border-radius: 6px;
      color: #93c5fd;
      text-decoration: none;
      flex-shrink: 0;
      margin-top: 2px;
    }
    .back-link:hover { border-color: #60a5fa; }
    .header h1 { margin: 0; font-size: 1.15rem; }
    .prompt-text { margin: 0.25rem 0 0; color: #94a3b8; font-size: 0.88rem; }

    /* ── Meta ── */
    .meta {
      margin-top: 0.8rem;
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .chip {
      border: 1px solid #334155;
      border-radius: 999px;
      padding: 0.15rem 0.55rem;
      font-size: 0.78rem;
      color: #cbd5e1;
    }

    /* ── Tabs ── */
    .tabs {
      margin-top: 1rem;
      display: flex;
      gap: 0.4rem;
      border-bottom: 1px solid #1e293b;
      padding-bottom: 0;
    }
    .tabs button {
      border: 1px solid transparent;
      border-bottom: 2px solid transparent;
      background: none;
      color: #94a3b8;
      border-radius: 6px 6px 0 0;
      padding: 0.4rem 0.7rem;
      cursor: pointer;
      font-size: 0.85rem;
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
    }
    .tabs button:hover { color: #e2e8f0; }
    .tabs button.active {
      border-bottom-color: #3b82f6;
      color: #e2e8f0;
      background: #111827;
    }
    .tab-count {
      font-size: 0.72rem;
      color: #64748b;
    }

    /* ── Tab content ── */
    .tab-content { margin-top: 1rem; }
    .tab-content h3 { margin: 0 0 0.6rem; font-size: 0.95rem; }

    /* ── Session grid ── */
    .session-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 0.6rem;
    }
    .session-card {
      border: 1px solid #1f2937;
      border-radius: 8px;
      background: #111827;
      padding: 0.6rem 0.75rem;
      display: flex; flex-direction: column; gap: 0.3rem;
    }
    .session-id { font-family: monospace; color: #93c5fd; font-size: 0.85rem; }
    .session-date { color: #64748b; font-size: 0.75rem; }

    /* ── Plan timeline ── */
    .plan-timeline { display: flex; flex-direction: column; gap: 0; }
    .plan-step {
      display: flex;
      gap: 0.75rem;
    }
    .step-indicator {
      display: flex;
      flex-direction: column;
      align-items: center;
      flex-shrink: 0;
    }
    .step-num {
      width: 26px; height: 26px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 0.75rem; font-weight: 600;
      background: #1e293b; color: #64748b;
      border: 2px solid #334155;
    }
    .step-line {
      width: 2px; flex: 1; min-height: 18px;
      background: #334155;
    }

    /* status colouring */
    .plan-step[data-status="running"] .step-num,
    .plan-step[data-status="RUNNING"] .step-num {
      border-color: #3b82f6; color: #93c5fd; background: #1e3a5f;
    }
    .plan-step[data-status="completed"] .step-num,
    .plan-step[data-status="COMPLETED"] .step-num,
    .plan-step[data-status="done"] .step-num {
      border-color: #22c55e; color: #22c55e; background: #14532d;
    }
    .plan-step[data-status="failed"] .step-num,
    .plan-step[data-status="FAILED"] .step-num {
      border-color: #ef4444; color: #fca5a5; background: #450a0a;
    }

    .step-body {
      flex: 1;
      border: 1px solid #1f2937;
      border-radius: 8px;
      background: #111827;
      padding: 0.6rem 0.75rem;
      margin-bottom: 0.6rem;
    }
    .plan-step[data-status="running"] .step-body,
    .plan-step[data-status="RUNNING"] .step-body { border-color: #1d4ed8; }
    .plan-step[data-status="completed"] .step-body,
    .plan-step[data-status="COMPLETED"] .step-body,
    .plan-step[data-status="done"] .step-body { border-color: #15803d; }

    .step-header {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.3rem;
    }
    .agent-chip {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 4px;
      padding: 0.1rem 0.45rem;
      font-size: 0.75rem;
      font-family: monospace;
      color: #93c5fd;
    }
    .step-time { color: #64748b; font-size: 0.75rem; margin-left: auto; }
    .step-desc { margin: 0; color: #94a3b8; font-size: 0.85rem; }
    .step-output {
      margin: 0.4rem 0 0;
      font-size: 0.78rem;
      background: #0b1325;
      border: 1px solid #1e293b;
      border-radius: 6px;
      padding: 0.5rem;
      max-height: 150px;
      overflow-y: auto;
      color: #cbd5e1;
    }

    /* ── Messages ── */
    .message {
      border: 1px solid #1f2937;
      border-radius: 8px;
      background: #111827;
      padding: 0.55rem;
      margin-bottom: 0.55rem;
    }
    .message-meta {
      color: #94a3b8;
      font-size: 0.78rem;
      margin-bottom: 0.3rem;
      text-transform: capitalize;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: #0b1325;
      border: 1px solid #243044;
      border-radius: 8px;
      padding: 0.6rem;
      font-size: 0.82rem;
    }

    /* ── Diff tab ── */
    .diff-tab fp-diff-viewer { display: block; min-height: 400px; }

    /* ── Terminal tab ── */
    .terminal-tab fp-terminal { display: block; min-height: 350px; }

    /* ── Events ── */
    .event {
      border: 1px solid #1f2937;
      border-radius: 8px;
      background: #111827;
      padding: 0.55rem;
      margin-bottom: 0.55rem;
    }
    .event-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 0.3rem;
    }
    .event-type {
      font-family: monospace;
      font-size: 0.78rem;
      color: #93c5fd;
    }
    .event-time {
      font-size: 0.75rem;
      color: #64748b;
    }
    .event-payload {
      font-size: 0.78rem;
      max-height: 120px;
      overflow-y: auto;
    }

    .hint { color: #94a3b8; }
    .error { color: #fca5a5; margin-top: 0.65rem; }
  `]
})
export class TaskDetailComponent implements OnInit, OnDestroy {
  @ViewChild('taskTerminal') private terminalEl?: TerminalComponent;

  private readonly route = inject(ActivatedRoute);
  private readonly taskService = inject(TaskService);
  private readonly eventStream = inject(EventStreamService);
  private readonly approvalService = inject(ApprovalService);

  readonly activeTab = signal<DetailTab>('overview');
  readonly task = signal<Task | null>(null);
  readonly taskMessages = signal<TaskMessage[]>([]);
  readonly sessions = signal<SessionRecord[]>([]);
  readonly taskEvents = signal<StreamEvent[]>([]);
  readonly planSteps = signal<PlanStep[]>([]);
  readonly diffEntries = signal<DiffEntry[]>([]);
  readonly diffLoading = signal(false);
  readonly error = signal('');

  readonly taskSessions = computed(() => {
    const taskId = this.task()?.id;
    if (!taskId) return [];
    return this.sessions().filter((s) => s.task_id === taskId);
  });

  private taskId = '';
  private disconnectEvents?: () => void;

  /* ─── Lifecycle ─── */

  async ngOnInit(): Promise<void> {
    this.taskId = String(this.route.snapshot.paramMap.get('id') || '').trim();
    if (!this.taskId) {
      this.error.set('Task id is missing.');
      return;
    }

    await this.load();
    this.disconnectEvents = this.eventStream.connect(
      (event) => this.onEvent(event),
      () => undefined,
    );
  }

  ngOnDestroy(): void {
    this.disconnectEvents?.();
  }

  /* ─── Tab helpers ─── */

  async switchToPlan(): Promise<void> {
    this.activeTab.set('plan');
    if (!this.planSteps().length) {
      await this.loadPlanSteps();
    }
  }

  async loadDiffTab(): Promise<void> {
    this.activeTab.set('diff');
    if (this.diffEntries().length || !this.taskId) return;
    this.diffLoading.set(true);
    try {
      const diffs = await this.approvalService.getTaskDiff(this.taskId);
      this.diffEntries.set(diffs.map((d) => this.parseDiffArtifact(d)));
    } catch {
      // best-effort
    } finally {
      this.diffLoading.set(false);
    }
  }

  /* ─── Data loading ─── */

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
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Failed to load task detail');
    }
  }

  private async loadPlanSteps(): Promise<void> {
    try {
      const steps = await this.taskService.getPlanSteps(this.taskId);
      this.planSteps.set(steps);
    } catch {
      // plan not generated yet — that's okay
    }
  }

  /* ─── SSE handler ─── */

  private onEvent(event: StreamEvent): void {
    const eventTaskId = String(event.payload['task_id'] ?? '');
    if (!eventTaskId || eventTaskId !== this.taskId) return;

    // Keep event log (newest first, max 200)
    this.taskEvents.update((list) => [event, ...list].slice(0, 200));

    // Feed terminal with log lines
    if (event.type === 'task.log') {
      const msg = String(event.payload['message'] ?? event.payload['line'] ?? '');
      if (msg) this.terminalEl?.writeLine(msg);
    }

    // Live plan step updates
    if (event.type === 'step.running' || event.type === 'step.completed') {
      const stepId = String(event.payload['step_id'] ?? '');
      const newStatus = event.type === 'step.running' ? 'running' : 'completed';
      this.planSteps.update((steps) =>
        steps.map((s) => s.id === stepId ? { ...s, status: newStatus } : s),
      );
    }

    // Refresh plan on task.planned
    if (event.type === 'task.planned') {
      void this.loadPlanSteps();
    }

    // Reload full task on major transitions
    if (
      event.type === 'task.completed' ||
      event.type === 'task.running' ||
      event.type === 'task.waiting_approval' ||
      event.type === 'task.failed'
    ) {
      void this.load();
    }

    // Terminal running indicator
    if (event.type === 'task.agent_start') {
      this.terminalEl?.setRunning(true);
    }
    if (event.type === 'task.agent_done' || event.type === 'task.agent_error') {
      this.terminalEl?.setRunning(false);
    }
  }

  /* ─── Diff parsing ─── */

  /**
   * Parses a DiffArtifact's unified-diff content into a DiffEntry
   * for the Monaco diff viewer. Splits hunks into original/modified.
   */
  private parseDiffArtifact(artifact: DiffArtifact): DiffEntry {
    const content = artifact.content || '';
    const lines = content.split('\n');

    // Try to extract filename from diff header
    let filename = `step-${artifact.step_id || 'unknown'}`;
    for (const line of lines) {
      if (line.startsWith('+++ b/') || line.startsWith('+++ ')) {
        filename = line.replace(/^\+\+\+ [ab]\//, '').trim();
        break;
      }
      if (line.startsWith('diff --git')) {
        const match = line.match(/b\/(.+)$/);
        if (match) filename = match[1];
        break;
      }
    }

    // Split into original / modified
    const original: string[] = [];
    const modified: string[] = [];
    let inHunk = false;

    for (const line of lines) {
      if (line.startsWith('@@')) {
        inHunk = true;
        continue;
      }
      if (!inHunk) continue;

      if (line.startsWith('-')) {
        original.push(line.slice(1));
      } else if (line.startsWith('+')) {
        modified.push(line.slice(1));
      } else {
        // context line (both sides)
        const ctx = line.startsWith(' ') ? line.slice(1) : line;
        original.push(ctx);
        modified.push(ctx);
      }
    }

    return {
      filename,
      original: original.join('\n'),
      modified: modified.join('\n'),
    };
  }
}
