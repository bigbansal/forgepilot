import { Component, OnDestroy, OnInit, ViewChild, ElementRef, AfterViewChecked, computed, inject, signal } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatStore } from '../../core/store/chat.store';

// ── Slash command palette ─────────────────────────────
export interface SlashCommand {
  command: string;       // e.g. '/create-skill'
  label: string;         // short name to filter on
  description: string;   // one-liner shown in the palette
  usage: string;         // template inserted into the textarea on select
  args: boolean;         // true = expects arguments after the command
}

export const SLASH_COMMANDS: SlashCommand[] = [
  {
    command: '/create-skill',
    label: 'create-skill',
    description: 'Create and install a new Manch skill',
    usage: '/create-skill <name>: <description>',
    args: true,
  },
  {
    command: '/sync-skills',
    label: 'sync-skills',
    description: 'Sync all enabled skills to ~/.codex/skills and ~/.gemini/skills',
    usage: '/sync-skills',
    args: false,
  },
  {
    command: '/list-skills',
    label: 'list-skills',
    description: 'Show all installed skills and their status',
    usage: '/list-skills',
    args: false,
  },
  {
    command: '/help',
    label: 'help',
    description: 'Show all available slash commands',
    usage: '/help',
    args: false,
  },
];
import { TaskRunner } from '../../core/models/task.model';
import { StreamStatus } from '../../core/models/event.model';
import { ApprovalRequest } from '../../core/models/approval.model';
import { WebSocketService } from '../../core/services/websocket.service';
import { ChatService } from '../../core/services/chat.service';
import { ApprovalService } from '../../core/services/approval.service';
import { ApiBaseService } from '../../core/services/api-base.service';
import { AuthService } from '../../core/services/auth.service';
import { RepoService, RepoSummary } from '../../core/services/repo.service';
import { SkillService } from '../../core/services/skill.service';
import { TypingIndicatorComponent } from '../../shared/components/typing-indicator/typing-indicator.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { InlineApprovalComponent } from '../../shared/components/inline-approval/inline-approval.component';
import { ToastStore } from '../../shared/components/toast/toast.component';
import { firstValueFrom } from 'rxjs';

@Component({
  selector: 'fp-chat-thread',
  standalone: true,
  imports: [CommonModule, FormsModule, TypingIndicatorComponent, StatusBadgeComponent, InlineApprovalComponent],
  templateUrl: './chat-thread.component.html',
  styleUrl: './chat-thread.component.scss'
})
export class ChatThreadComponent implements OnInit, OnDestroy, AfterViewChecked {
  @ViewChild('messageList') private messageListEl?: ElementRef<HTMLElement>;

  private readonly chatStore = inject(ChatStore);
  private readonly chatService = inject(ChatService);
  private readonly wsService = inject(WebSocketService);
  private readonly approvalService = inject(ApprovalService);
  private readonly apiBase = inject(ApiBaseService);
  private readonly auth = inject(AuthService);
  private readonly repoService = inject(RepoService);
  private readonly skillService = inject(SkillService);
  private readonly toasts = inject(ToastStore);

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

  /** Pending approval for the active task (if any). */
  readonly pendingApproval = signal<ApprovalRequest | null>(null);

  prompt = '';
  selectedRunner: TaskRunner = 'opensandbox';
  selectedApprovalMode = 'yolo';
  selectedRepoId = '';
  isSending = false;
  loadError = '';

  // ── Command palette ─────────────────────────────────
  readonly showCommandMenu = signal(false);
  readonly commandMenuIndex = signal(0);
  private _commandFilter = '';
  readonly filteredCommands = signal<SlashCommand[]>([]);
  readonly SLASH_COMMANDS = SLASH_COMMANDS;

  readonly repos = signal<RepoSummary[]>([]);

  readonly taskLogsMap = signal<Record<string, string[]>>({});
  readonly activeLogs = computed(() => {
    const taskId = this.activeConversation()?.latestTaskId;
    return taskId ? (this.taskLogsMap()[taskId] ?? []) : [];
  });
  readonly logsExpanded = signal(true);

  private disconnectEvents?: () => void;
  private isRefreshingConversation = false;
  private pollingIntervalId?: number;
  private shouldScrollToBottom = false;
  private currentSubscribedTaskId: string | null = null;

  assistantMessageHtml(content: string): string {
    const escaped = this.escapeHtml(content);
    const linked = escaped.replace(/https?:\/\/[^\s<]+/g, (rawUrl) => {
      const href = this.decoratePreviewUrl(rawUrl);
      return `<a href="${href}" target="_blank" rel="noopener noreferrer">${rawUrl}</a>`;
    });
    return linked.replace(/\n/g, '<br>');
  }

  private decoratePreviewUrl(url: string): string {
    const normalizedUrl = url.replace(
      /^http:\/\/localhost:8080\/api\/v1\/preview\//,
      `${this.apiBase.baseUrl}/preview/`,
    );
    if (!normalizedUrl.startsWith(`${this.apiBase.baseUrl}/preview/`)) {
      return normalizedUrl;
    }
    const token = this.auth.accessToken();
    if (!token) {
      return normalizedUrl;
    }
    const separator = normalizedUrl.includes('?') ? '&' : '?';
    return `${normalizedUrl}${separator}token=${encodeURIComponent(token)}`;
  }

  private escapeHtml(value: string): string {
    return value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  ngOnInit(): void {
    void this.initializeConversations();
    void this.loadRepos();

    this.disconnectEvents = this.wsService.connect(
      (event) => {
        this.handleStreamEvent(event.type, event.payload);
      },
      (status) => this.streamStatus.set(status)
    );
  }

  ngOnDestroy(): void {
    this.unsubscribeCurrentTask();
    this.disconnectEvents?.();
    this.stopPolling();
    this.streamStatus.set('DISCONNECTED');
  }

  ngAfterViewChecked(): void {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom();
      this.shouldScrollToBottom = false;
    }
  }

  private scrollToBottom(): void {
    const el = this.messageListEl?.nativeElement;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
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
      // Subscribe to the task's WS events if one exists
      if (conversation.latestTaskId) {
        this.subscribeToTask(conversation.latestTaskId);
      }
    } catch (error) {
      this.loadError = error instanceof Error ? error.message : 'Failed to load conversation';
    }
  }

  async send(): Promise<void> {
    const userPrompt = this.prompt.trim();
    if (!userPrompt || this.isSending) {
      return;
    }

    // ── Close command menu on send ───────────────────────────────────────────
    this.showCommandMenu.set(false);

    // ── Slash command: /sync-skills ──────────────────────────────────────────
    if (userPrompt === '/sync-skills') {
      this.prompt = '';
      this.isSending = true;
      try {
        const result = await this.skillService.syncAllSkillsLocal();
        this.loadError = '';
        this.toasts.success(`${result.count} skill(s) synced to local CLI directories`);
      } catch (err: any) {
        const msg = err?.error?.detail || 'Failed to sync skills';
        this.toasts.error(msg);
        this.loadError = msg;
      } finally {
        this.isSending = false;
      }
      return;
    }

    // ── Slash command: /list-skills ──────────────────────────────────────────
    if (userPrompt === '/list-skills') {
      this.prompt = '';
      this.isSending = true;
      try {
        const skills = await this.skillService.listSkills();
        const lines = skills.map(s =>
          `  ${s.enabled ? '●' : '○'} ${s.name} (v${s.version}) — ${s.description || 'no description'}`
        );
        const text = `Installed skills (${skills.length}):\n${lines.join('\n')}`;
        this.chatStore.appendMessage('system', text, this.activeConversation()?.latestTaskId ?? '');
        this.loadError = '';
      } catch (err: any) {
        const msg = err?.error?.detail || 'Failed to list skills';
        this.toasts.error(msg);
        this.loadError = msg;
      } finally {
        this.isSending = false;
      }
      return;
    }

    // ── Slash command: /help ─────────────────────────────────────────────────
    if (userPrompt === '/help') {
      this.prompt = '';
      const lines = SLASH_COMMANDS.map(c => `  ${c.usage.padEnd(42)} ${c.description}`);
      const text = `Available commands:\n${lines.join('\n')}`;
      this.chatStore.appendMessage('system', text, this.activeConversation()?.latestTaskId ?? '');
      return;
    }

    // ── Slash command: /create-skill <name>: <description> ──────────────────
    // Syntax: /create-skill my-skill-name: A description of what this skill does
    const createSkillMatch = userPrompt.match(/^\/create-skill\s+([a-z0-9-]+)(?:\s*:\s*(.+))?$/i);
    if (createSkillMatch) {
      const skillName = createSkillMatch[1].toLowerCase();
      const skillDescription = (createSkillMatch[2] || `Custom skill: ${skillName}`).trim();
      this.prompt = '';
      this.isSending = true;
      try {
        const result = await this.skillService.createSkill({ name: skillName, description: skillDescription });
        this.toasts.success(`Skill "${result.name}" created! Available at: ${result.local_paths.join(', ')}`);
        this.loadError = '';
      } catch (err: any) {
        const msg = err?.error?.detail || `Failed to create skill "${skillName}"`;
        this.toasts.error(msg);
        this.loadError = msg;
      } finally {
        this.isSending = false;
      }
      return;
    }
    // ──────────────────────────────────────────────────────────────────────────

    const activeConversationId = this.chatStore.getActiveConversationId();
    if (!activeConversationId) {
      return;
    }

    this.isSending = true;
    this.prompt = '';
    this.loadError = '';

    // Clear logs for fresh run
    const prevTaskId = this.activeConversation()?.latestTaskId;
    if (prevTaskId) {
      this.taskLogsMap.update(m => ({ ...m, [prevTaskId]: [] }));
    }

    try {
      const response = await this.chatService.sendMessage(
        activeConversationId, userPrompt, this.selectedRunner, this.selectedApprovalMode,
        this.selectedRepoId || undefined
      );
      this.chatStore.upsertConversation(response.conversation);
      this.chatStore.setActiveConversation(response.conversation.id);
      this.shouldScrollToBottom = true;
      if (response.taskId && response.taskStatus) {
        this.chatStore.updateActiveTaskStatus(response.taskStatus, response.taskId);
        this.subscribeToTask(response.taskId);
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

  private async loadRepos(): Promise<void> {
    try {
      const repos = await firstValueFrom(this.repoService.list());
      this.repos.set(repos);
    } catch {
      // best-effort — selector will just show "No repo"
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
      void this.loadPendingApproval();
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

    // Auto-scroll on any event that produces messages
    this.shouldScrollToBottom = true;
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

  // ── WS task subscription ──────────────────────────

  /** Subscribe the WS connection to events for a specific task. */
  private subscribeToTask(taskId: string): void {
    if (this.currentSubscribedTaskId === taskId) return;
    this.unsubscribeCurrentTask();
    this.currentSubscribedTaskId = taskId;
    this.wsService.subscribeToTasks([taskId]);
  }

  /** Unsubscribe from the currently tracked task. */
  private unsubscribeCurrentTask(): void {
    if (this.currentSubscribedTaskId) {
      this.wsService.unsubscribeFromTasks([this.currentSubscribedTaskId]);
      this.currentSubscribedTaskId = null;
    }
  }

  // ── Approval handling ────────────────────────────

  /** Load the pending approval for the active task (if WAITING_APPROVAL). */
  async loadPendingApproval(): Promise<void> {
    const taskId = this.activeConversation()?.latestTaskId;
    const status = this.activeConversation()?.latestTaskStatus;
    if (!taskId || status !== 'WAITING_APPROVAL') {
      this.pendingApproval.set(null);
      return;
    }
    try {
      const approvals = await this.approvalService.listForTask(taskId);
      const pending = approvals.find(a => a.decision === null);
      this.pendingApproval.set(pending ?? null);
    } catch {
      // best-effort
    }
  }

  // ── Command palette handlers ──────────────────────────────────────────────

  onPromptInput(): void {
    const val = this.prompt;
    if (val.startsWith('/') && !val.includes('\n')) {
      const filter = val.toLowerCase();
      const matches = SLASH_COMMANDS.filter(c =>
        c.command.startsWith(filter) || filter === '/'
      );
      this.filteredCommands.set(matches);
      this.showCommandMenu.set(matches.length > 0);
      this.commandMenuIndex.set(0);
    } else {
      this.showCommandMenu.set(false);
    }
  }

  onPromptKeydown(event: KeyboardEvent): void {
    if (!this.showCommandMenu()) return;
    const cmds = this.filteredCommands();
    if (!cmds.length) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      this.commandMenuIndex.update(i => (i + 1) % cmds.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      this.commandMenuIndex.update(i => (i - 1 + cmds.length) % cmds.length);
    } else if (event.key === 'Enter' || event.key === 'Tab') {
      // Only intercept plain Enter/Tab — Ctrl+Enter still goes to send()
      if (event.key === 'Tab' || (event.key === 'Enter' && !event.ctrlKey && !event.metaKey)) {
        event.preventDefault();
        this.selectCommand(cmds[this.commandMenuIndex()]);
      }
    } else if (event.key === 'Escape') {
      event.preventDefault();
      this.showCommandMenu.set(false);
    }
  }

  selectCommand(cmd: SlashCommand): void {
    this.showCommandMenu.set(false);
    if (cmd.args) {
      // Insert usage template so the user can fill in the args
      this.prompt = cmd.usage;
    } else {
      // No args needed — put the exact command in the box ready to send
      this.prompt = cmd.command;
    }
    // Re-focus the textarea after selection
    setTimeout(() => {
      const ta = document.querySelector<HTMLTextAreaElement>('textarea');
      ta?.focus();
      // Position cursor at end
      if (ta) ta.selectionStart = ta.selectionEnd = this.prompt.length;
    }, 0);
  }

  /** Enter → send, Shift+Enter → newline. */
  onEnterKey(event: Event): void {
    const ke = event as KeyboardEvent;
    // If command palette already intercepted the Enter, do nothing
    if (event.defaultPrevented) return;
    if (ke.shiftKey) return; // allow newline
    event.preventDefault();
    this.send();
  }

  /** Auto-grow textarea height to fit content. */
  autoGrow(event: Event): void {
    const ta = event.target as HTMLTextAreaElement;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }

  async handleApprove(event: { approvalId: string }): Promise<void> {
    const taskId = this.activeConversation()?.latestTaskId;
    if (!taskId) return;
    try {
      await this.approvalService.decide(taskId, event.approvalId, { decision: 'approve' });
      this.chatStore.appendMessage('system', 'Approval granted — pipeline resuming…', taskId);
      this.pendingApproval.set(null);
    } catch (err) {
      this.loadError = err instanceof Error ? err.message : 'Failed to approve';
    }
  }

  async handleReject(event: { approvalId: string; reason: string }): Promise<void> {
    const taskId = this.activeConversation()?.latestTaskId;
    if (!taskId) return;
    try {
      await this.approvalService.decide(taskId, event.approvalId, {
        decision: 'reject',
        reason: event.reason || undefined,
      });
      this.chatStore.appendMessage('system', 'Approval rejected — task cancelled.', taskId);
      this.chatStore.updateActiveTaskStatus('CANCELLED', taskId);
      this.pendingApproval.set(null);
    } catch (err) {
      this.loadError = err instanceof Error ? err.message : 'Failed to reject';
    }
  }
}
