import { Component } from '@angular/core';

@Component({
  selector: 'fp-typing-indicator',
  standalone: true,
  template: `
    <div class="typing">
      <span></span>
      <span></span>
      <span></span>
    </div>
  `,
  styles: [
    `
      .typing {
        display: inline-flex;
        gap: 3px;
        align-items: center;
        padding: 6px 10px;
        background: var(--c-elevated, #21262d);
        border: 1px solid var(--c-border-muted, #21262d);
        border-radius: 10px;
        border-bottom-left-radius: 3px;
      }

      span {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--c-text-faint, #484f58);
        animation: bounce 1.1s ease-in-out infinite;
      }

      span:nth-child(2) { animation-delay: 0.15s; }
      span:nth-child(3) { animation-delay: 0.3s; }

      @keyframes bounce {
        0%, 60%, 100% { transform: translateY(0); }
        30%            { transform: translateY(-4px); background: var(--c-accent, #388bfd); }
      }
    `,
  ],
})
export class TypingIndicatorComponent {}

