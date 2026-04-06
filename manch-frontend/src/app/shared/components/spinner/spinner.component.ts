import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'fp-spinner',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="spinner-wrap" [class.inline]="inline">
      <svg class="spin" [attr.width]="size" [attr.height]="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <circle cx="12" cy="12" r="10" opacity=".15"/>
        <path d="M22 12a10 10 0 0 0-10-10"/>
      </svg>
      <span class="spinner-text" *ngIf="label">{{ label }}</span>
    </div>
  `,
  styles: [`
    :host { display: block; }
    .spinner-wrap {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 24px 0;
      color: var(--c-text-muted);
    }
    .spinner-wrap.inline {
      flex-direction: row;
      padding: 0;
      gap: 6px;
    }
    .spin {
      animation: rotate 0.8s linear infinite;
      color: var(--c-accent);
    }
    @keyframes rotate {
      to { transform: rotate(360deg); }
    }
    .spinner-text {
      font-size: 12px;
      color: var(--c-text-muted);
    }
  `],
})
export class SpinnerComponent {
  @Input() label = '';
  @Input() size = 18;
  @Input() inline = false;
}
