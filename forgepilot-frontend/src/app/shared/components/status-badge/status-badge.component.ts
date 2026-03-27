import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

@Component({
  selector: 'fp-status-badge',
  standalone: true,
  imports: [CommonModule],
  template: `<span class="badge" [class.success]="isSuccess" [class.warning]="isWarning" [class.error]="isError" [class.running]="isRunning">{{ label }}</span>`,
  styles: [
    `
      .badge {
        display: inline-flex;
        align-items: center;
        border: 1px solid var(--c-border-muted, #21262d);
        border-radius: 999px;
        padding: 1px 7px;
        font-size: 10.5px;
        font-weight: 500;
        background: var(--c-elevated, #21262d);
        color: var(--c-text-muted, #8b949e);
        line-height: 1.6;
        white-space: nowrap;
      }

      .badge.success {
        background: rgba(63,185,80,0.1);
        border-color: rgba(63,185,80,0.3);
        color: var(--c-success, #3fb950);
      }

      .badge.running {
        background: rgba(88,166,255,0.1);
        border-color: rgba(88,166,255,0.3);
        color: var(--c-running, #58a6ff);
      }

      .badge.warning {
        background: rgba(210,153,34,0.1);
        border-color: rgba(210,153,34,0.3);
        color: var(--c-warning, #d29922);
      }

      .badge.error {
        background: rgba(248,81,73,0.1);
        border-color: rgba(248,81,73,0.3);
        color: var(--c-danger, #f85149);
      }
    `,
  ],
})
export class StatusBadgeComponent {
  @Input({ required: true }) label = '';

  get isSuccess(): boolean {
    return this.label === 'COMPLETED' || this.label === 'CONNECTED';
  }

  get isRunning(): boolean {
    return this.label === 'RUNNING';
  }

  get isWarning(): boolean {
    return this.label === 'WAITING_APPROVAL' || this.label === 'PLANNING' || this.label === 'VALIDATING';
  }

  get isError(): boolean {
    return this.label === 'FAILED' || this.label === 'DISCONNECTED' || this.label === 'CANCELLED';
  }
}

