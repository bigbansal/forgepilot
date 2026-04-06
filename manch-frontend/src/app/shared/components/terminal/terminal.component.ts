import {
  Component,
  AfterViewInit,
  OnDestroy,
  ElementRef,
  Input,
  ViewChild,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Terminal } from 'xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';

@Component({
  selector: 'fp-terminal',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="term-header">
      <span class="term-dot" [class.running]="running()"></span>
      <span class="term-label">{{ title }}</span>
      <span class="term-lines">{{ lineCount() }} lines</span>
      <button class="term-clear" (click)="clear()" title="Clear">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>
    <div class="term-container" #termContainer></div>
  `,
  styles: [`
    :host {
      display: flex;
      flex-direction: column;
      min-height: 180px;
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-md);
      overflow: hidden;
      background: #1a1a2e;
    }

    .term-header {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 5px 10px;
      background: var(--c-surface);
      border-bottom: 1px solid var(--c-border-muted);
      font-size: 11px;
      user-select: none;
    }

    .term-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--c-text-muted);
      transition: background 0.2s;
    }
    .term-dot.running { background: #4ec9b0; }

    .term-label {
      font-weight: 600;
      color: var(--c-text);
    }

    .term-lines {
      margin-left: auto;
      color: var(--c-text-muted);
    }

    .term-clear {
      border: none;
      background: transparent;
      color: var(--c-text-muted);
      cursor: pointer;
      padding: 2px;
      line-height: 1;
    }
    .term-clear:hover { color: var(--c-text); }

    .term-container {
      flex: 1;
      min-height: 0;
    }

    /* xterm.js base CSS */
    :host ::ng-deep .xterm {
      height: 100%;
      padding: 4px;
    }
    :host ::ng-deep .xterm-viewport {
      overflow-y: auto !important;
    }
  `],
})
export class TerminalComponent implements AfterViewInit, OnDestroy {
  @ViewChild('termContainer', { static: true }) termContainer!: ElementRef<HTMLDivElement>;

  @Input() title = 'Terminal';

  readonly running = signal(false);
  readonly lineCount = signal(0);

  private terminal!: Terminal;
  private fitAddon!: FitAddon;
  private resizeObserver?: ResizeObserver;
  private _lines = 0;

  ngAfterViewInit(): void {
    this.terminal = new Terminal({
      theme: {
        background: '#1a1a2e',
        foreground: '#e4e4e7',
        cursor: '#4ec9b0',
        selectionBackground: '#264f7844',
      },
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
      fontSize: 13,
      lineHeight: 1.35,
      cursorBlink: true,
      scrollback: 5000,
      convertEol: true,
      disableStdin: true,
    });

    this.fitAddon = new FitAddon();
    this.terminal.loadAddon(this.fitAddon);
    this.terminal.loadAddon(new WebLinksAddon());

    this.terminal.open(this.termContainer.nativeElement);

    // Fit on resize
    this.resizeObserver = new ResizeObserver(() => {
      try { this.fitAddon.fit(); } catch { /* noop */ }
    });
    this.resizeObserver.observe(this.termContainer.nativeElement);
    setTimeout(() => this.fitAddon.fit(), 50);
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
    this.terminal?.dispose();
  }

  /** Write a line to the terminal. Handles ANSI codes. */
  writeLine(text: string): void {
    this.terminal.writeln(text);
    this._lines++;
    this.lineCount.set(this._lines);
  }

  /** Write raw text (no newline appended). */
  write(text: string): void {
    this.terminal.write(text);
  }

  /** Clear the terminal. */
  clear(): void {
    this.terminal.clear();
    this._lines = 0;
    this.lineCount.set(0);
  }

  /** Set running state for the status dot. */
  setRunning(state: boolean): void {
    this.running.set(state);
  }
}
