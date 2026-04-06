import { Component, inject, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { signalStore, withMethods, withState, patchState } from '@ngrx/signals';

/* ── Toast state ── */

export interface ToastItem {
  id: string;
  message: string;
  level: 'info' | 'success' | 'warning' | 'error';
  ttl: number; // ms before auto-dismiss
}

type ToastState = { items: ToastItem[] };

export const ToastStore = signalStore(
  { providedIn: 'root' },
  withState<ToastState>({ items: [] }),
  withMethods((store) => {
    const timers = new Map<string, ReturnType<typeof setTimeout>>();

    return {
      show(message: string, level: ToastItem['level'] = 'info', ttl = 4000): void {
        const id = crypto.randomUUID();
        patchState(store, { items: [...store.items(), { id, message, level, ttl }] });

        const timer = setTimeout(() => this.dismiss(id), ttl);
        timers.set(id, timer);
      },

      dismiss(id: string): void {
        const timer = timers.get(id);
        if (timer) { clearTimeout(timer); timers.delete(id); }
        patchState(store, { items: store.items().filter((t) => t.id !== id) });
      },

      /** Convenience wrappers */
      success(msg: string): void { this.show(msg, 'success', 3500); },
      error(msg: string): void   { this.show(msg, 'error', 6000); },
      warn(msg: string): void    { this.show(msg, 'warning', 5000); },
      info(msg: string): void    { this.show(msg, 'info', 4000); },
    };
  }),
);

/* ── Toast container component ── */

@Component({
  selector: 'fp-toast-container',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="toast-stack">
      <div
        *ngFor="let t of toasts.items(); trackBy: trackById"
        class="toast"
        [attr.data-level]="t.level"
        (click)="toasts.dismiss(t.id)">
        <svg *ngIf="t.level === 'success'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
        <svg *ngIf="t.level === 'error'"   width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
        <svg *ngIf="t.level === 'warning'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        <svg *ngIf="t.level === 'info'"    width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span class="toast-msg">{{ t.message }}</span>
      </div>
    </div>
  `,
  styles: [`
    .toast-stack {
      position: fixed;
      top: 12px;
      right: 12px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 6px;
      pointer-events: none;
      max-width: 380px;
    }

    .toast {
      pointer-events: auto;
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 10px 14px;
      border-radius: var(--r);
      border: 1px solid var(--c-border);
      background: var(--c-elevated);
      color: var(--c-text);
      font-size: 12.5px;
      box-shadow: var(--c-shadow);
      cursor: pointer;
      animation: toast-in 0.25s ease-out;
      transition: opacity 0.2s;

      &:hover { opacity: 0.85; }
    }

    .toast[data-level="success"] { border-left: 3px solid var(--c-success); }
    .toast[data-level="success"] svg { color: var(--c-success); }

    .toast[data-level="error"] { border-left: 3px solid var(--c-danger); }
    .toast[data-level="error"] svg { color: var(--c-danger); }

    .toast[data-level="warning"] { border-left: 3px solid var(--c-warning); }
    .toast[data-level="warning"] svg { color: var(--c-warning); }

    .toast[data-level="info"] { border-left: 3px solid var(--c-accent); }
    .toast[data-level="info"] svg { color: var(--c-accent); }

    .toast-msg { flex: 1; line-height: 1.4; }

    svg { flex-shrink: 0; margin-top: 1px; }

    @keyframes toast-in {
      from { transform: translateX(20px); opacity: 0; }
      to   { transform: translateX(0); opacity: 1; }
    }
  `],
})
export class ToastContainerComponent {
  readonly toasts = inject(ToastStore);

  trackById(_: number, item: ToastItem): string {
    return item.id;
  }
}
