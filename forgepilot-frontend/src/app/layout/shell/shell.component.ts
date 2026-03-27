import { Component, OnDestroy, OnInit, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { EventStreamService } from '../../core/services/event-stream.service';
import { NotificationStore } from '../../core/store/notification.store';
import { AuthService } from '../../core/services/auth.service';
import { ThemeService } from '../../core/services/theme.service';

@Component({
  selector: 'fp-shell',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss'
})
export class ShellComponent implements OnInit, OnDestroy {
  private readonly eventStream = inject(EventStreamService);
  readonly notifications = inject(NotificationStore);
  readonly auth = inject(AuthService);
  readonly theme = inject(ThemeService);

  readonly unreadCount = computed(() => this.notifications.items().filter((item) => !item.read).length);
  readonly currentUser = this.auth.currentUser;

  private disconnectEvents?: () => void;

  ngOnInit(): void {
    // Ensure profile is loaded (e.g. on page refresh)
    if (!this.currentUser()) {
      this.auth.loadProfile();
    }

    this.disconnectEvents = this.eventStream.connect(
      (event) => {
        if (event.type === 'task.waiting_approval') {
          this.notifications.push({
            title: 'Task requires approval',
            detail: `Task ${String(event.payload['task_id'] ?? '')} is waiting for approval.`,
            level: 'warning',
          });
        }

        if (event.type === 'task.failed') {
          this.notifications.push({
            title: 'Task failed',
            detail: `Task ${String(event.payload['task_id'] ?? '')} failed to complete.`,
            level: 'error',
          });
        }

        if (event.type === 'task.completed') {
          this.notifications.push({
            title: 'Task completed',
            detail: `Task ${String(event.payload['task_id'] ?? '')} completed successfully.`,
            level: 'success',
          });
        }
      },
      () => undefined,
    );
  }

  ngOnDestroy(): void {
    this.disconnectEvents?.();
  }

  logout(): void {
    this.auth.logout();
  }
}
