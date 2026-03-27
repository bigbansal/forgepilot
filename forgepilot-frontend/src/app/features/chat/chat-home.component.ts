import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'fp-chat-home',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="home">
      <div class="home-inner">
        <div class="home-mark">FP</div>
        <h1 class="home-title">ForgePilot</h1>
        <p class="home-sub">AI-powered engineering execution platform</p>
        <a routerLink="/chat/thread" class="btn-start">
          Open Chat
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        </a>
      </div>
    </div>
  `,
  styles: [
    `
      .home {
        height: calc(100vh - 64px);
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .home-inner {
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
      }

      .home-mark {
        width: 44px;
        height: 44px;
        border-radius: var(--r);
        background: var(--c-accent-emphasis);
        color: #fff;
        font-size: 16px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 4px;
      }

      .home-title {
        margin: 0;
        font-size: 20px;
        font-weight: 700;
        color: var(--c-text);
      }

      .home-sub {
        margin: 0;
        font-size: 13px;
        color: var(--c-text-muted);
      }

      .btn-start {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        margin-top: 8px;
        padding: 8px 18px;
        background: var(--c-accent-emphasis);
        border: 1px solid var(--c-accent-emphasis);
        border-radius: var(--r);
        color: #fff;
        font-size: 13px;
        font-weight: 600;
        text-decoration: none;
        transition: background 0.15s;

        &:hover { background: #1a5cc5; text-decoration: none; }
      }
    `
  ]
})
export class ChatHomeComponent {}

