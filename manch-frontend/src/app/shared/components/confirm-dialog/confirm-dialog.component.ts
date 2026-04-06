import { Component, Injectable, signal } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

@Injectable({ providedIn: 'root' })
export class ConfirmService {
  readonly visible = signal(false);
  readonly options = signal<ConfirmOptions>({ title: '', message: '' });

  private _resolve?: (confirmed: boolean) => void;

  /** Opens the confirm dialog and returns a Promise<boolean>. */
  confirm(opts: ConfirmOptions): Promise<boolean> {
    this.options.set(opts);
    this.visible.set(true);
    return new Promise<boolean>((resolve) => {
      this._resolve = resolve;
    });
  }

  /** @internal — called by the component */
  _respond(confirmed: boolean): void {
    this.visible.set(false);
    this._resolve?.(confirmed);
    this._resolve = undefined;
  }
}

@Component({
  selector: 'fp-confirm-dialog',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="backdrop" *ngIf="svc.visible()" (click)="svc._respond(false)">
      <div class="dialog" (click)="$event.stopPropagation()">
        <h3>{{ svc.options().title }}</h3>
        <p>{{ svc.options().message }}</p>
        <div class="actions">
          <button class="btn-cancel" (click)="svc._respond(false)">
            {{ svc.options().cancelLabel || 'Cancel' }}
          </button>
          <button
            class="btn-confirm"
            [class.danger]="svc.options().danger"
            (click)="svc._respond(true)">
            {{ svc.options().confirmLabel || 'Confirm' }}
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.55);
      z-index: 10000;
      display: flex;
      align-items: center;
      justify-content: center;
      animation: fade-in 0.15s ease-out;
    }

    .dialog {
      background: var(--c-surface);
      border: 1px solid var(--c-border);
      border-radius: var(--r-lg);
      padding: 20px 24px;
      min-width: 320px;
      max-width: 440px;
      box-shadow: var(--c-shadow);
      animation: dialog-in 0.15s ease-out;
    }

    h3 {
      margin: 0 0 8px;
      font-size: 14px;
      font-weight: 600;
      color: var(--c-text);
    }

    p {
      margin: 0 0 16px;
      font-size: 12.5px;
      color: var(--c-text-muted);
      line-height: 1.5;
    }

    .actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
    }

    .btn-cancel, .btn-confirm {
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-sm);
      padding: 5px 14px;
      cursor: pointer;
      font-size: 12px;
      font-family: inherit;
      transition: background 0.1s, color 0.1s, border-color 0.1s;
    }

    .btn-cancel {
      background: transparent;
      color: var(--c-text-muted);

      &:hover { background: var(--c-elevated); color: var(--c-text); }
    }

    .btn-confirm {
      background: var(--c-accent-emphasis);
      border-color: var(--c-accent-emphasis);
      color: #fff;

      &:hover { background: var(--c-accent); }

      &.danger {
        background: var(--c-danger);
        border-color: var(--c-danger);

        &:hover { background: #dc2626; }
      }
    }

    @keyframes fade-in {
      from { opacity: 0; }
      to   { opacity: 1; }
    }
    @keyframes dialog-in {
      from { transform: scale(0.95); opacity: 0; }
      to   { transform: scale(1); opacity: 1; }
    }
  `],
})
export class ConfirmDialogComponent {
  constructor(public readonly svc: ConfirmService) {}
}
