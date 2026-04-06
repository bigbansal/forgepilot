import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'fp-empty-state',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="empty">
      <p class="empty-title">{{ title }}</p>
      <p class="empty-desc">{{ description }}</p>
      <a *ngIf="actionLabel && actionLink" [routerLink]="actionLink" class="empty-action">{{ actionLabel }}</a>
    </div>
  `,
  styles: [
    `
      .empty {
        border: 1px dashed var(--c-border, #30363d);
        border-radius: var(--r-lg, 10px);
        padding: 24px 20px;
        text-align: center;
        background: transparent;
      }

      .empty-title {
        margin: 0 0 4px;
        font-size: 13px;
        font-weight: 600;
        color: var(--c-text-muted, #8b949e);
      }

      .empty-desc {
        margin: 0;
        font-size: 12px;
        color: var(--c-text-faint, #484f58);
      }

      .empty-action {
        display: inline-block;
        margin-top: 12px;
        padding: 5px 12px;
        border: 1px solid var(--c-border, #30363d);
        border-radius: var(--r, 6px);
        font-size: 12px;
        color: var(--c-accent, #388bfd);
        text-decoration: none;
        transition: background 0.1s;

        &:hover {
          background: rgba(56,139,253,0.08);
          text-decoration: none;
        }
      }
    `,
  ],
})
export class EmptyStateComponent {
  @Input({ required: true }) title = '';
  @Input({ required: true }) description = '';
  @Input() actionLabel = '';
  @Input() actionLink = '';
}

