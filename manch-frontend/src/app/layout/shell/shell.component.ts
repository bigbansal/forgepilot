import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { WebSocketService } from '../../core/services/websocket.service';
import { NotificationStore } from '../../core/store/notification.store';
import { EventStore } from '../../core/store/event.store';
import { AuthService } from '../../core/services/auth.service';
import { ThemeService } from '../../core/services/theme.service';
import { ApprovalService } from '../../core/services/approval.service';
import { TeamService } from '../../core/services/team.service';
import { UiStore } from '../../core/store/ui.store';
import { ToastContainerComponent, ToastStore } from '../../shared/components/toast/toast.component';
import { ConfirmDialogComponent, ConfirmService } from '../../shared/components/confirm-dialog/confirm-dialog.component';

@Component({
  selector: 'fp-shell',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, RouterOutlet, ToastContainerComponent, ConfirmDialogComponent],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss'
})
export class ShellComponent implements OnInit, OnDestroy {
  private readonly wsService = inject(WebSocketService);
  private readonly eventStore = inject(EventStore);
  readonly notifications = inject(NotificationStore);
  readonly auth = inject(AuthService);
  readonly theme = inject(ThemeService);
  readonly ui = inject(UiStore);
  private readonly approvalService = inject(ApprovalService);
  private readonly teamService = inject(TeamService);
  private readonly toasts = inject(ToastStore);
  private readonly confirm = inject(ConfirmService);

  readonly unreadCount = computed(() => this.notifications.items().filter((item) => !item.read).length);
  readonly currentUser = this.auth.currentUser;
  readonly teams = this.auth.teams;
  readonly activeTeam = this.auth.activeTeam;
  readonly pendingApprovalCount = signal(0);
  readonly teamDropdownOpen = signal(false);

  private disconnectEvents?: () => void;
  private approvalPollId?: number;

  ngOnInit(): void {
    // Ensure profile is loaded (e.g. on page refresh)
    if (!this.currentUser()) {
      this.auth.loadProfile();
    }

    // Poll pending approval count for sidebar badge
    this.refreshApprovalCount();
    this.approvalPollId = window.setInterval(() => this.refreshApprovalCount(), 15_000);

    this.disconnectEvents = this.wsService.connect(
      (event) => {
        // Push every event to the shared store
        this.eventStore.push(event);

        const taskSlice = String(event.payload['task_id'] ?? '').slice(0, 8);

        if (event.type === 'task.waiting_approval') {
          this.notifications.push({
            title: 'Task requires approval',
            detail: `Task ${taskSlice} is waiting for approval.`,
            level: 'warning',
          });
          this.toasts.warn(`Task ${taskSlice} needs approval`);
          this.refreshApprovalCount();
        }

        if (event.type === 'task.failed') {
          this.notifications.push({
            title: 'Task failed',
            detail: `Task ${taskSlice} failed to complete.`,
            level: 'error',
          });
          this.toasts.error(`Task ${taskSlice} failed`);
        }

        if (event.type === 'task.completed') {
          this.notifications.push({
            title: 'Task completed',
            detail: `Task ${taskSlice} completed successfully.`,
            level: 'success',
          });
          this.toasts.success(`Task ${taskSlice} completed`);
        }

        if (event.type === 'task.agent_error') {
          this.notifications.push({
            title: 'Agent error',
            detail: `Task ${taskSlice}: ${String(event.payload['error'] ?? 'unknown error')}`,
            level: 'error',
          });
          this.toasts.error(`Agent error on ${taskSlice}`);
        }

        // Phase 3: agent pipeline resume/cancel clear the badge
        if (event.type === 'task.agent_resume' || event.type === 'task.agent_done') {
          this.refreshApprovalCount();
        }
      },
      () => undefined,
    );
  }

  ngOnDestroy(): void {
    this.disconnectEvents?.();
    if (this.approvalPollId) {
      window.clearInterval(this.approvalPollId);
    }
  }

  async logout(): Promise<void> {
    const confirmed = await this.confirm.confirm({
      title: 'Sign out',
      message: 'Are you sure you want to sign out?',
      confirmLabel: 'Sign out',
      danger: true,
    });
    if (confirmed) {
      this.auth.logout();
    }
  }

  async switchTeam(teamId: string): Promise<void> {
    this.teamDropdownOpen.set(false);
    if (teamId === this.auth.activeTeamId()) return;
    try {
      const tokens = await this.teamService.switchTeam(teamId);
      await this.auth.switchTeam(teamId, tokens);
      this.toasts.success('Switched team');
      // Reload to get team-scoped data
      window.location.reload();
    } catch {
      this.toasts.error('Failed to switch team');
    }
  }

  toggleTeamDropdown(): void {
    this.teamDropdownOpen.update((v) => !v);
  }

  private refreshApprovalCount(): void {
    this.approvalService.pendingCount().then(
      (res) => this.pendingApprovalCount.set(res.count),
      () => { /* best-effort */ },
    );
  }
}
