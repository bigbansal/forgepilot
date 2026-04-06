import {
  Component,
  Input,
  OnChanges,
  SimpleChanges,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { DiffEditorComponent as MonacoDiffEditor, DiffEditorModel } from 'ngx-monaco-editor-v2';

export interface DiffEntry {
  filename: string;
  original: string;
  modified: string;
  language?: string;
}

@Component({
  selector: 'fp-diff-viewer',
  standalone: true,
  imports: [CommonModule, MonacoDiffEditor],
  template: `
    <!-- File tabs -->
    <div class="diff-files" *ngIf="entries.length > 1">
      <button
        *ngFor="let entry of entries; let i = index"
        class="file-tab"
        [class.active]="activeIndex() === i"
        (click)="selectFile(i)">
        {{ entry.filename }}
      </button>
    </div>

    <!-- Single file name when only one -->
    <div class="diff-single" *ngIf="entries.length === 1">
      <span class="file-name">{{ entries[0].filename }}</span>
    </div>

    <!-- Monaco diff editor -->
    <div class="editor-wrap" *ngIf="entries.length">
      <ngx-monaco-diff-editor
        [options]="editorOptions"
        [originalModel]="originalModel()"
        [modifiedModel]="modifiedModel()"
        style="height: 100%; width: 100%;"
      />
    </div>

    <div class="empty" *ngIf="!entries.length">
      <p>No diff available.</p>
    </div>
  `,
  styles: [`
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
      min-height: 320px;
    }

    .diff-files {
      display: flex;
      gap: 2px;
      padding: 4px 4px 0;
      overflow-x: auto;
      border-bottom: 1px solid var(--c-border-muted);
      background: var(--c-surface);
    }

    .file-tab {
      border: none;
      background: transparent;
      color: var(--c-text-muted);
      font-size: 11.5px;
      padding: 5px 10px;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      white-space: nowrap;
      transition: color 0.1s, border-color 0.1s;
    }
    .file-tab:hover { color: var(--c-text); }
    .file-tab.active {
      color: var(--c-text);
      border-bottom-color: var(--c-accent);
    }

    .diff-single {
      padding: 5px 8px;
      border-bottom: 1px solid var(--c-border-muted);
    }
    .file-name {
      font-size: 11.5px;
      font-weight: 600;
      color: var(--c-text);
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
    }

    .editor-wrap {
      flex: 1;
      min-height: 0;
    }

    .empty {
      padding: 24px;
      text-align: center;
      color: var(--c-text-muted);
      font-size: 12px;
    }
  `],
})
export class DiffViewerComponent implements OnChanges {
  @Input() entries: DiffEntry[] = [];

  readonly activeIndex = signal(0);

  readonly originalModel = signal<DiffEditorModel>({
    code: '',
    language: 'plaintext',
  });

  readonly modifiedModel = signal<DiffEditorModel>({
    code: '',
    language: 'plaintext',
  });

  readonly editorOptions = {
    theme: 'vs-dark',
    readOnly: true,
    renderSideBySide: true,
    automaticLayout: true,
    scrollBeyondLastLine: false,
    fontSize: 13,
    minimap: { enabled: false },
  };

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['entries']) {
      this.activeIndex.set(0);
      this.updateModels();
    }
  }

  selectFile(index: number): void {
    this.activeIndex.set(index);
    this.updateModels();
  }

  private updateModels(): void {
    const entry = this.entries[this.activeIndex()];
    if (!entry) return;

    const lang = entry.language || this.guessLanguage(entry.filename);

    this.originalModel.set({ code: entry.original, language: lang });
    this.modifiedModel.set({ code: entry.modified, language: lang });
  }

  private guessLanguage(filename: string): string {
    const ext = filename.split('.').pop()?.toLowerCase() ?? '';
    const map: Record<string, string> = {
      ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript',
      py: 'python', rs: 'rust', go: 'go', java: 'java', rb: 'ruby',
      html: 'html', css: 'css', scss: 'scss', json: 'json', md: 'markdown',
      yaml: 'yaml', yml: 'yaml', sh: 'shell', bash: 'shell',
      sql: 'sql', xml: 'xml', toml: 'ini', dockerfile: 'dockerfile',
    };
    return map[ext] || 'plaintext';
  }
}
