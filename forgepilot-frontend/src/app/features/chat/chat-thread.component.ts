import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatStore } from '../../core/store/chat.store';
import { TaskRunner } from '../../core/models/task.model';
import { StreamStatus } from '../../core/models/event.model';
import { EventStreamService } from '../../core/services/event-stream.service';
import { ChatService } from '../../core/services/chat.service';
import { TypingIndicatorComponent } from '../../shared/components/typing-indicator/typing-indicator.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'fp-chat-thread',
  standalone: true,
  imports: [CommonModule, FormsModule, TypingIndicatorComponent, StatusBadgeComponent],
  templateUrl: './chat-thread.component.html',
  styleUrl: './chat-thread.component.scss'
})
export class ChatThreadComponent implements OnInit, OnDestroy {
  private readonly chatStore = inject(ChatStore);
  private readonly chatService = inject(ChatService);
  private readonly eventStreamService = inject(EventStreamService);

  readonly conversations = this.chatStore.conversations;
  readonly activeConversation = this.chatStore.activeConversation;
  readonly hasMessages = computed(() => (this.activeConversation()?.messages.length ?? 0) > 0);

  readonly streamStatus = signal<StreamStatus>('CONNECTING');
  readonly streamStatusText = computed(() => {
    const status = this.streamStatus();
    if (status === 'CONNECTED') return 'Connected';
    if (status === 'RECONNECTING') return 'Reconnecting...';
    if (status === 'DISCONNECTED') return 'Disconnected';
    return 'Connecting...';
  });

  prompt = '';
  selectedRunner: TaskRunner = 'opensandbox';
  selectedApprovalMode = 'yolo';
  isSending = false;
  loadError = '';

  readonly taskLogsMap = signal<Record<string, string[]>>({});
  readonly activeLogs = computed(() => {
    const taskId = this.activeConversation()?.latestTaskId;
    return taskId ? (this.taskLogsMap()[taskId] ?? []) : [];
  });
  readonly logsExpanded = signal(true);

  private disconnectEvents?: () => void;
  private isRefreshingConversation = false;
  private pollingIntervalId?: number;

  ngOnInit(): void {
    void this.initializeConversations();

    this.disconnectEvents = this.eventStreamService.connect(
      (event) => {
        this.handleStreamEvent(event.type, event.payload);
      },
      (status) => this.streamStatus.set(status)
    );
  }

  ngOnDestroy(): void {
    this.disconnectEvents?.();
    this.stopPolling();
    this.streamStatus.set('DISCONNECTED');
  }

  async newChat(): Promise<void> {
    this.loadError = '';
    try {
      const conversation = await this.chatService.createConversation('New Chat');
      this.chatStore.upsertConversation(conversation);
      this.chatStore.setActiveConversation(conversation.id);
    } catch (error) {
      this.loadError = error instanceof Error ? error.message : 'Failed to create conversation';
    }
  }

  async openConversation(id: string): Promise<void> {
    this.chatStore.setActiveConversation(id);
    this.loadError = '';
    try {
      const conversation = await this.chatService.getConversation(id);
      this.chatStore.upsertConversation(conversation);
    } catch (error) {
      this.loadError = error instanceof Error ? error.message : 'Failed to load conversation';
    }
  }

  async send(): Promise<void> {
    const userPrompt = this.prompt.trim();
    if (!userPrompt || this.isSending) {
      return;
    }

    const activeConversationId = this.chatStore.getActiveConversationId();
    if (!activeConversationId) {
      return;
    }

    this.isSending = true;
    this.prompt = '';
    this.loadError = '';

    // Clear logs for fresh run
    const prevTaskId = this.chatStore.getActiveConversationId();
    if (prevTaskId) {
      this.taskLogsMap.update(m => ({ ...m, [prevTaskId]: [] }));
    }

    try {
      const response = await this.chatService.sendMessage(
        activeConversationId, userPrompt, this.selectedRunner, this.selectedApprovalMode
      );
      this.chatStore.upsertConversation(response.conversation);
      this.chatStore.setActiveConversation(response.conversation.id);
      if (response.taskId && response.taskStatus) {
        this.chatStore.updateActiveTaskStatus(response.taskStatus, response.taskId);
        this.syncPollingWithActiveTask();
      }
    } catch (error) {
      this.loadError = error instanceof Error ? error.message : 'Task execution failed';
    } finally {
      this.isSending = false;
    }
  }

  private async initializeConversations(): Promise<void> {
    this.loadError = '';
    try {
      const list = await this.chatService.listConversations();
      if (list.length === 0) {
        const first = await this.chatService.createConversation('New Chat');
        this.chatStore.replaceConversations([first]);
        this.chatStore.setActiveConversation(first.id);
        return;
      }

      this.chatStore.replaceConversations(list);
      const activeId = this.chatStore.getActiveConversationId();
      if (activeId) {
        const detailed = await this.chatService.getConversation(activeId);
        this.chatStore.upsertConversation(detailed);
      }
    } catch (error) {
      this.loadError = error instanceof Error ? error.message : 'Failed to initialize conversations';
    }
  }

  private handleStreamEvent(eventType: string, payload: Record<string, unknown>): void {
    const activeTaskId = this.activeConversation()?.latestTaskId;
    if (!activeTaskId) {
      return;
    }

    const eventTaskId = String(payload['task_id'] ?? '');
    if (!eventTaskId || eventTaskId !== activeTaskId) {
      return;
    }

    if (eventType === 'task.log') {
      const text = String(payload['text'] ?? '');
      if (text) {
        this.taskLogsMap.update(m => ({
          ...m,
          [eventTaskId]: [...(m[eventTaskId] ?? []), text],
        }));
      }
      return;
    }

    if (eventType === 'sandbox.exec') {
      const stdout = String(payload['stdout'] ?? '');
      if (stdout.trim()) {
        this.chatStore.appendMessage('assistant', `\`sandbox.exec\`\n\n${stdout}`, activeTaskId);
      }
      return;
    }

    if (eventType === 'task.created') {
      this.chatStore.updateActiveTaskStatus('CREATED', activeTaskId);
      this.syncPollingWithActiveTask();
      return;
    }

    if (eventType === 'task.running') {
      this.chatStore.updateActiveTaskStatus('RUNNING', activeTaskId);
      this.chatStore.appendMessage('system', `Task running: ${activeTaskId}`, activeTaskId);
      this.syncPollingWithActiveTask();
      return;
    }

    if (eventType === 'task.waiting_approval') {
      const risk = String(payload['risk'] ?? 'UNKNOWN');
      this.chatStore.updateActiveTaskStatus('WAITING_APPROVAL', activeTaskId);
      this.chatStore.appendMessage('system', `Task waiting approval (risk=${risk})`, activeTaskId);
      this.syncPollingWithActiveTask();
      return;
    }

    if (eventType === 'task.completed') {
      this.chatStore.updateActiveTaskStatus('COMPLETED', activeTaskId);
      this.syncPollingWithActiveTask();
      void this.refreshActiveConversation();
      return;
    }

    if (eventType === 'task.failed') {
      this.chatStore.updateActiveTaskStatus('FAILED', activeTaskId);
      this.syncPollingWithActiveTask();
      void this.refreshActiveConversation();
      return;
    }

    // ── Phase 2 agent pipeline events ────────────────
    if (eventType === 'task.agent_start') {
      this.chatStore.updateActiveTaskStatus('PLANNING', activeTaskId);
      this.chatStore.appendMessage('system', '🤖 Agent pipeline started — Maestro is planning…', activeTaskId);
      this.syncPollingWithActiveTask();
      return;
    }

    if (eventType === 'task.planned') {
      const title = String(payload['title'] ?? '');
      const count = Number(payload['step_count'] ?? 0);
      this.chatStore.updateActiveTaskStatus('RUNNING', activeTaskId);
      this.chatStore.appendMessage('system', `📋 Plan ready: "${title}" — ${count} step(s)`, activeTaskId);
      this.syncPollingWithActiveTask();
      return;
    }

    if (eventType === 'step.running') {
      const idx = Number(payload['step_index'] ?? 0);
      const agent = String(payload['agent'] ?? '');
      const desc = String(payload['description'] ?? '');
      this.chatStore.appendMessage('system', `▶ Step ${idx} [${agent}]: ${desc}`, activeTaskId);
      return;
    }

    if (eventType === 'step.completed') {
      const idx = Number(payload['step_index'] ?? 0);
      const agent = String(payload['agent'] ?? '');
      const ok = Boolean(payload['success']);
      this.chatStore.appendMessage('system', `${ok ? '✅' : '❌'} Step ${idx} [${agent}] ${ok ? 'done' : 'failed'}`, activeTaskId);
      return;
    }

    if (eventType === 'task.waiting_approval') {
      const risk = String(payload['risk_level'] ?? payload['risk'] ?? 'UNKNOWN');
      const reason = String(payload['reason'] ?? '');
      const approvalId = String(payload['approval_id'] ?? '');
      this.chatStore.updateActiveTaskStatus('WAITING_APPROVAL', activeTaskId);
      this.chatStore.appendMessage('system',
        `⚠️ Approval required (risk=${risk})${reason ? ': ' + reason : ''}${approvalId ? ' — ID: ' + approvalId : ''}`,
        activeTaskId
      );
      this.syncPollingWithActiveTask();
      return;
    }

    if (eventType === 'task.agent_done') {
      const status = String(payload['status'] ?? 'unknown');
      const steps = Number(payload['step_count'] ?? 0);
      this.chatStore.updateActiveTaskStatus(status === 'completed' ? 'COMPLETED' : 'FAILED', activeTaskId);
      this.chatStore.appendMessage('system', `🏁 Agent pipeline ${status} — ${steps} step(s) run`, activeTaskId);
      this.syncPollingWithActiveTask();
      void this.refreshActiveConversation();
      return;
    }

    if (eventType === 'task.agent_error') {
      const error = String(payload['error'] ?? 'Unknown error');
      this.chatStore.updateActiveTaskStatus('FAILED', activeTaskId);
      this.chatStore.appendMessage('system', `💥 Agent pipeline error: ${error}`, activeTaskId);
      this.syncPollingWithActiveTask();
      void this.refreshActiveConversation();
    }
  }

  private async refreshActiveConversation(): Promise<void> {
    const activeConversationId = this.chatStore.getActiveConversationId();
    if (!activeConversationId || this.isRefreshingConversation) {
      return;
    }

    this.isRefreshingConversation = true;
    try {
      const conversation = await this.chatService.getConversation(activeConversationId);
      this.chatStore.upsertConversation(conversation);
      this.chatStore.setActiveConversation(conversation.id);
      this.syncPollingWithActiveTask();
    } catch {
      // best-effort refresh; keep UI responsive even if sync fails transiently
    } finally {
      this.isRefreshingConversation = false;
    }
  }

  private syncPollingWithActiveTask(): void {
    const status = this.activeConversation()?.latestTaskStatus;
    const activeStatuses: (typeof status)[] = ['RUNNING', 'PLANNING', 'VALIDATING', 'WAITING_APPROVAL'];
    if (status && activeStatuses.includes(status)) {
      this.startPolling();
      return;
    }
    this.stopPolling();
  }

  private startPolling(): void {
    if (this.pollingIntervalId) {
      return;
    }

    this.pollingIntervalId = window.setInterval(() => {
      const status = this.activeConversation()?.latestTaskStatus;
      const activeStatuses: (typeof status)[] = ['RUNNING', 'PLANNING', 'VALIDATING', 'WAITING_APPROVAL'];
      if (!status || !activeStatuses.includes(status)) {
        this.stopPolling();
        return;
      }
      void this.refreshActiveConversation();
    }, 2500);
  }

  private stopPolling(): void {
    if (!this.pollingIntervalId) {
      return;
    }
    window.clearInterval(this.pollingIntervalId);
    this.pollingIntervalId = undefined;
  }
}
