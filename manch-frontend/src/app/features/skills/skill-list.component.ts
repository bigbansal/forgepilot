import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SkillService, SkillSummary, MarketplaceItem, MarketplaceCategory } from '../../core/services/skill.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { SpinnerComponent } from '../../shared/components/spinner/spinner.component';
import { ConfirmService } from '../../shared/components/confirm-dialog/confirm-dialog.component';
import { ToastStore } from '../../shared/components/toast/toast.component';

type Tab = 'installed' | 'marketplace' | 'create';

@Component({
  selector: 'fp-skill-list',
  standalone: true,
  imports: [CommonModule, FormsModule, EmptyStateComponent, StatusBadgeComponent, SpinnerComponent],
  template: `
    <section class="panel">
      <div class="header">
        <h1>Skills &amp; Plugins</h1>
        <div class="header-actions">
          <div class="tab-bar">
            <button class="tab-btn" [class.active]="activeTab() === 'installed'" (click)="switchTab('installed')">
              Installed ({{ skills().length }})
            </button>
            <button class="tab-btn" [class.active]="activeTab() === 'marketplace'" (click)="switchTab('marketplace')">
              Marketplace
            </button>
            <button class="tab-btn create-tab" [class.active]="activeTab() === 'create'" (click)="switchTab('create')">
              + Create Skill
            </button>
          </div>
          <button class="btn" (click)="syncAll()" [disabled]="syncing() !== false" title="Write SKILL.md for all enabled skills to ~/.codex/skills and ~/.gemini/skills">
            {{ syncing() === '__all__' ? 'Syncing…' : 'Sync All Local' }}
          </button>
          <button class="btn" (click)="refresh()" [disabled]="loading()">Refresh</button>
        </div>
      </div>

      <p class="hint" *ngIf="error()">{{ error() }}</p>
      <fp-spinner *ngIf="loading()" label="Loading skills…" />

      <!-- ── Installed Tab ─────────────────────── -->
      <ng-container *ngIf="activeTab() === 'installed' && !loading()">
        <div class="skill-grid" *ngIf="skills().length">
          <div class="skill-card" *ngFor="let s of skills()" [class.disabled]="!s.enabled">
            <div class="skill-header">
              <span class="skill-name">{{ s.name }}</span>
              <fp-status-badge [label]="s.kind" />
            </div>
            <p class="skill-desc">{{ s.description || '—' }}</p>

            <div class="skill-meta">
              <span class="meta-chip">v{{ s.version }}</span>
              <span class="meta-chip risk" [attr.data-risk]="s.risk_level">{{ s.risk_level }}</span>
              <span class="meta-chip" *ngIf="s.author">{{ s.author }}</span>
              <span class="meta-chip tag" *ngFor="let t of s.tags">{{ t }}</span>
            </div>

            <div class="skill-actions">
              <button
                *ngIf="!isBuiltin(s)"
                class="uninstall-btn"
                (click)="uninstallSkill(s)"
                [disabled]="installing()">
                Uninstall
              </button>
              <button
                class="sync-btn"
                [disabled]="syncing() === s.name || !s.enabled"
                (click)="syncLocal(s)"
                [title]="s.enabled ? 'Write SKILL.md to ~/.codex/skills and ~/.gemini/skills' : 'Enable skill first'">
                {{ syncing() === s.name ? 'Syncing…' : 'Sync Local' }}
              </button>
              <button
                class="toggle-btn"
                [class.enabled]="s.enabled"
                (click)="toggleSkill(s)">
                {{ s.enabled ? 'Disable' : 'Enable' }}
              </button>
            </div>
          </div>
        </div>

        <fp-empty-state
          *ngIf="!skills().length"
          title="No skills installed"
          description="Built-in skills load automatically. Browse the marketplace to install more."
        />
      </ng-container>

      <!-- ── Create Skill Tab ──────────────────── -->
      <ng-container *ngIf="activeTab() === 'create' && !loading()">
        <div class="create-form">
          <p class="create-hint">
            Create a custom skill and have it available immediately in
            <code>~/.codex/skills</code> and <code>~/.gemini/skills</code>.
            You can also type <code>/create-skill &lt;name&gt;: &lt;description&gt;</code> in the chat.
          </p>
          <div class="form-row">
            <label>Skill name <span class="required">*</span></label>
            <input class="form-input" placeholder="e.g. angular-testing"
              [ngModel]="createName()" (ngModelChange)="createName.set($event)" />
            <span class="form-hint">Lowercase, letters and hyphens only</span>
          </div>
          <div class="form-row">
            <label>Description <span class="required">*</span></label>
            <textarea class="form-input form-textarea" rows="3"
              placeholder="What does this skill do? When should an AI use it?"
              [ngModel]="createDescription()" (ngModelChange)="createDescription.set($event)"></textarea>
          </div>
          <div class="form-row">
            <label>Tags <span class="form-hint">(comma-separated)</span></label>
            <input class="form-input" placeholder="e.g. testing, angular, jest"
              [ngModel]="createTags()" (ngModelChange)="createTags.set($event)" />
          </div>
          <div class="form-row">
            <label>Risk level</label>
            <select class="form-input form-select"
              [ngModel]="createRisk()" (ngModelChange)="createRisk.set($event)">
              <option value="LOW">LOW</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="HIGH">HIGH</option>
            </select>
          </div>
          <div *ngIf="createResult()" class="create-result">
            <span class="result-ok">✓ Skill <strong>{{ createResult()!.name }}</strong> created!</span>
            <div class="result-paths">
              <span *ngFor="let p of createResult()!.local_paths" class="path-chip">{{ p }}</span>
            </div>
          </div>
          <div class="form-actions">
            <button class="install-btn"
              (click)="submitCreateSkill()"
              [disabled]="creating() || !createName() || !createDescription()">
              {{ creating() ? 'Creating…' : 'Create & Sync to Local' }}
            </button>
          </div>
        </div>
      </ng-container>

      <!-- ── Marketplace Tab ───────────────────── -->
      <ng-container *ngIf="activeTab() === 'marketplace' && !loading()">
        <div class="marketplace-controls">
          <input
            type="text"
            class="search-input"
            placeholder="Search skills…"
            [ngModel]="searchQuery()"
            (ngModelChange)="onSearchChange($event)"
          />
          <div class="category-chips">
            <button
              class="cat-chip"
              [class.active]="!selectedCategory()"
              (click)="selectCategory(null)">
              All
            </button>
            <button
              class="cat-chip"
              *ngFor="let c of categories()"
              [class.active]="selectedCategory() === c.name"
              (click)="selectCategory(c.name)">
              {{ c.name }} ({{ c.count }})
            </button>
          </div>
        </div>

        <div class="skill-grid" *ngIf="marketplaceItems().length">
          <div class="skill-card marketplace-card" *ngFor="let m of marketplaceItems()">
            <div class="skill-header">
              <span class="skill-name">{{ m.name }}</span>
              <span class="download-count">{{ m.downloads | number }} installs</span>
            </div>
            <p class="skill-desc">{{ m.description }}</p>

            <div class="skill-meta">
              <span class="meta-chip">v{{ m.version }}</span>
              <span class="meta-chip risk" [attr.data-risk]="m.risk_level">{{ m.risk_level }}</span>
              <span class="meta-chip" *ngIf="m.author">{{ m.author }}</span>
              <span class="meta-chip category-chip">{{ m.category }}</span>
              <span class="meta-chip tag" *ngFor="let t of m.tags">{{ t }}</span>
            </div>

            <div class="skill-actions">
              <button
                class="install-btn"
                (click)="installSkill(m)"
                [disabled]="installing()">
                {{ installing() === m.name ? 'Installing…' : 'Install' }}
              </button>
            </div>
          </div>
        </div>

        <fp-empty-state
          *ngIf="!marketplaceItems().length"
          title="No skills found"
          [description]="searchQuery() ? 'Try a different search term.' : 'All marketplace skills are already installed!'"
        />
      </ng-container>
    </section>
  `,
  styles: [`
    .panel {
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-lg);
      padding: 14px 16px;
      background: var(--c-surface);
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
      flex-wrap: wrap;
      gap: 8px;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    h1 { margin: 0; font-size: 15px; font-weight: 600; }

    /* Tab bar */
    .tab-bar {
      display: flex;
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-sm);
      overflow: hidden;
    }
    .tab-btn {
      border: none;
      background: transparent;
      color: var(--c-text-muted);
      padding: 4px 12px;
      font-size: 12px;
      cursor: pointer;
      transition: background 0.15s, color 0.15s;
    }
    .tab-btn:hover { background: var(--c-elevated); }
    .tab-btn.active {
      background: var(--c-accent);
      color: #fff;
    }

    button.btn {
      border: 1px solid var(--c-border-muted);
      background: transparent;
      color: var(--c-text-muted);
      border-radius: var(--r-sm);
      padding: 4px 10px;
      cursor: pointer;
      font-size: 12px;
      transition: background 0.1s, color 0.1s;
    }
    button.btn:hover {
      background: var(--c-elevated);
      color: var(--c-text);
    }

    .hint {
      font-size: 12px;
      color: #f14c4c;
      margin: 8px 0;
    }

    /* Marketplace controls */
    .marketplace-controls {
      margin-bottom: 12px;
    }
    .search-input {
      width: 100%;
      padding: 7px 12px;
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-sm);
      background: var(--c-elevated);
      color: var(--c-text);
      font-size: 12px;
      outline: none;
      margin-bottom: 8px;
      transition: border-color 0.15s;
    }
    .search-input:focus { border-color: var(--c-accent); }
    .search-input::placeholder { color: var(--c-text-muted); }

    .category-chips {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .cat-chip {
      font-size: 11px;
      padding: 3px 10px;
      border: 1px solid var(--c-border-muted);
      border-radius: 100px;
      background: transparent;
      color: var(--c-text-muted);
      cursor: pointer;
      transition: all 0.15s;
      text-transform: capitalize;
    }
    .cat-chip:hover { background: var(--c-elevated); color: var(--c-text); }
    .cat-chip.active {
      background: var(--c-accent);
      color: #fff;
      border-color: var(--c-accent);
    }

    /* Skill grid */
    .skill-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 10px;
    }

    .skill-card {
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-md);
      padding: 12px 14px;
      background: var(--c-elevated);
      transition: border-color 0.15s, opacity 0.2s;
    }
    .skill-card:hover { border-color: var(--c-accent); }
    .skill-card.disabled { opacity: 0.55; }
    .marketplace-card { border-left: 3px solid var(--c-accent); }

    .skill-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }

    .skill-name {
      font-size: 13px;
      font-weight: 600;
      color: var(--c-text);
    }

    .download-count {
      font-size: 10.5px;
      color: var(--c-text-muted);
    }

    .skill-desc {
      font-size: 11.5px;
      color: var(--c-text-muted);
      line-height: 1.4;
      margin: 0 0 8px;
    }

    .skill-meta { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }

    .meta-chip {
      font-size: 10.5px;
      background: var(--c-surface);
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-sm);
      padding: 2px 7px;
      color: var(--c-text-muted);
    }
    .meta-chip.risk[data-risk="HIGH"],
    .meta-chip.risk[data-risk="high"] { color: #f14c4c; border-color: #f14c4c33; }
    .meta-chip.risk[data-risk="CRITICAL"],
    .meta-chip.risk[data-risk="critical"] { color: #f14c4c; border-color: #f14c4c55; font-weight: 600; }
    .meta-chip.risk[data-risk="MEDIUM"],
    .meta-chip.risk[data-risk="medium"] { color: #cca700; border-color: #cca70033; }
    .meta-chip.risk[data-risk="LOW"],
    .meta-chip.risk[data-risk="low"] { color: #4ec9b0; border-color: #4ec9b033; }
    .meta-chip.tag { color: var(--c-accent); border-color: var(--c-accent-muted, #264f78); }
    .meta-chip.category-chip {
      text-transform: capitalize;
      color: #dcdcaa;
      border-color: #dcdcaa33;
    }

    .skill-actions { display: flex; justify-content: flex-end; gap: 6px; }

    .toggle-btn {
      font-size: 11px;
      padding: 3px 10px;
      border-radius: var(--r-sm);
      border: 1px solid var(--c-border-muted);
      background: transparent;
      color: var(--c-text-muted);
      cursor: pointer;
      transition: all 0.15s;
    }
    .toggle-btn.enabled {
      border-color: #f14c4c44;
      color: #f14c4c;
    }
    .toggle-btn.enabled:hover {
      background: #f14c4c18;
    }
    .toggle-btn:not(.enabled) {
      border-color: #4ec9b044;
      color: #4ec9b0;
    }
    .toggle-btn:not(.enabled):hover {
      background: #4ec9b018;
    }

    .install-btn {
      font-size: 11px;
      padding: 3px 12px;
      border-radius: var(--r-sm);
      border: 1px solid var(--c-accent);
      background: var(--c-accent);
      color: #fff;
      cursor: pointer;
      transition: opacity 0.15s;
    }
    .install-btn:hover { opacity: 0.85; }
    .install-btn:disabled { opacity: 0.5; cursor: default; }

    .uninstall-btn {
      font-size: 11px;
      padding: 3px 10px;
      border-radius: var(--r-sm);
      border: 1px solid var(--c-border-muted);
      background: transparent;
      color: var(--c-text-muted);
      cursor: pointer;
      transition: all 0.15s;
    }
    .uninstall-btn:hover {
      border-color: #f14c4c44;
      color: #f14c4c;
      background: #f14c4c12;
    }
    .uninstall-btn:disabled { opacity: 0.5; cursor: default; }

    .sync-btn {
      font-size: 11px;
      padding: 3px 10px;
      border-radius: var(--r-sm);
      border: 1px solid #264f78;
      background: transparent;
      color: var(--c-accent);
      cursor: pointer;
      transition: all 0.15s;
    }
    .sync-btn:hover:not(:disabled) { background: #264f7820; }
    .sync-btn:disabled { opacity: 0.4; cursor: default; }

    .create-tab { border-left: 1px solid var(--c-border-muted) !important; }

    /* Create form */
    .create-form {
      max-width: 560px;
    }
    .create-hint {
      font-size: 12px;
      color: var(--c-text-muted);
      margin: 0 0 14px;
      line-height: 1.5;
    }
    .create-hint code {
      background: var(--c-elevated);
      border: 1px solid var(--c-border-muted);
      border-radius: 3px;
      padding: 1px 5px;
      font-size: 11px;
    }
    .form-row { margin-bottom: 12px; }
    .form-row label {
      display: block;
      font-size: 12px;
      font-weight: 500;
      color: var(--c-text);
      margin-bottom: 4px;
    }
    .required { color: #f14c4c; margin-left: 2px; }
    .form-hint { font-size: 10.5px; color: var(--c-text-muted); margin-left: 6px; }
    .form-input {
      width: 100%;
      box-sizing: border-box;
      padding: 7px 10px;
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-sm);
      background: var(--c-elevated);
      color: var(--c-text);
      font-size: 12px;
      outline: none;
      transition: border-color 0.15s;
      font-family: inherit;
    }
    .form-input:focus { border-color: var(--c-accent); }
    .form-input::placeholder { color: var(--c-text-muted); }
    .form-textarea { resize: vertical; min-height: 60px; }
    .form-select { cursor: pointer; }
    .form-actions { margin-top: 16px; }
    .create-result {
      margin-top: 10px;
      padding: 8px 12px;
      border: 1px solid #4ec9b044;
      border-radius: var(--r-sm);
      background: #4ec9b010;
    }
    .result-ok { font-size: 12px; color: #4ec9b0; display: block; margin-bottom: 6px; }
    .result-paths { display: flex; flex-wrap: wrap; gap: 5px; }
    .path-chip {
      font-size: 10.5px;
      background: var(--c-elevated);
      border: 1px solid var(--c-border-muted);
      border-radius: var(--r-sm);
      padding: 2px 7px;
      color: var(--c-text-muted);
      font-family: monospace;
    }
  `],
})
export class SkillListComponent implements OnInit {
  private readonly skillService = inject(SkillService);
  private readonly confirm = inject(ConfirmService);
  private readonly toasts = inject(ToastStore);

  readonly skills = signal<SkillSummary[]>([]);
  readonly marketplaceItems = signal<MarketplaceItem[]>([]);
  readonly categories = signal<MarketplaceCategory[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly activeTab = signal<Tab>('installed');
  readonly searchQuery = signal('');
  readonly selectedCategory = signal<string | null>(null);
  readonly installing = signal<string | false>(false);

  // Sync-to-local state
  readonly syncing = signal<string | false>(false);

  // Create-skill form state
  readonly createName = signal('');
  readonly createDescription = signal('');
  readonly createTags = signal('');
  readonly createRisk = signal('LOW');
  readonly creating = signal(false);
  readonly createResult = signal<{ name: string; local_paths: string[] } | null>(null);

  ngOnInit(): void {
    this.refresh();
  }

  switchTab(tab: Tab): void {
    this.activeTab.set(tab);
    if (tab === 'marketplace' && !this.marketplaceItems().length) {
      this.loadMarketplace();
    }
    if (tab === 'create') {
      this.createResult.set(null);
    }
  }

  async refresh(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const list = await this.skillService.listSkills();
      this.skills.set(list);
      if (this.activeTab() === 'marketplace') {
        await this.loadMarketplace();
      }
    } catch (err: any) {
      this.error.set(err?.message || 'Failed to load skills');
    } finally {
      this.loading.set(false);
    }
  }

  async loadMarketplace(): Promise<void> {
    try {
      const [items, cats] = await Promise.all([
        this.skillService.listMarketplace(
          this.selectedCategory() ?? undefined,
          this.searchQuery() || undefined,
        ),
        this.skillService.getMarketplaceCategories(),
      ]);
      this.marketplaceItems.set(items);
      this.categories.set(cats);
    } catch (err: any) {
      this.error.set(err?.message || 'Failed to load marketplace');
    }
  }

  onSearchChange(value: string): void {
    this.searchQuery.set(value);
    this.loadMarketplace();
  }

  selectCategory(cat: string | null): void {
    this.selectedCategory.set(cat);
    this.loadMarketplace();
  }

  isBuiltin(s: SkillSummary): boolean {
    return s.tags?.includes('builtin') ?? false;
  }

  async toggleSkill(s: SkillSummary): Promise<void> {
    if (s.enabled) {
      const ok = await this.confirm.confirm({
        title: `Disable ${s.name}?`,
        message: `This will deactivate the "${s.name}" skill. You can re-enable it later.`,
        confirmLabel: 'Disable',
        danger: true,
      });
      if (!ok) return;
    }

    try {
      if (s.enabled) {
        await this.skillService.disableSkill(s.name);
        this.toasts.info(`${s.name} disabled`);
      } else {
        await this.skillService.enableSkill(s.name);
        this.toasts.success(`${s.name} enabled`);
      }
      await this.refresh();
    } catch (err: any) {
      this.error.set(err?.message || 'Failed to toggle skill');
      this.toasts.error(`Failed to toggle ${s.name}`);
    }
  }

  async installSkill(m: MarketplaceItem): Promise<void> {
    this.installing.set(m.name);
    try {
      await this.skillService.installSkill(m.name);
      this.toasts.success(`${m.name} installed successfully`);
      await this.refresh();
      // Reload marketplace to reflect the install
      await this.loadMarketplace();
    } catch (err: any) {
      this.toasts.error(err?.error?.detail || `Failed to install ${m.name}`);
    } finally {
      this.installing.set(false);
    }
  }

  async uninstallSkill(s: SkillSummary): Promise<void> {
    const ok = await this.confirm.confirm({
      title: `Uninstall ${s.name}?`,
      message: `This will remove the "${s.name}" skill completely. You can reinstall it from the marketplace.`,
      confirmLabel: 'Uninstall',
      danger: true,
    });
    if (!ok) return;

    this.installing.set(s.name);
    try {
      await this.skillService.uninstallSkill(s.name);
      this.toasts.info(`${s.name} uninstalled`);
      await this.refresh();
    } catch (err: any) {
      this.toasts.error(err?.error?.detail || `Failed to uninstall ${s.name}`);
    } finally {
      this.installing.set(false);
    }
  }

  // ── Local sync ───────────────────────────────────

  async syncLocal(s: SkillSummary): Promise<void> {
    this.syncing.set(s.name);
    try {
      const result = await this.skillService.syncSkillLocal(s.name);
      this.toasts.success(`${s.name} synced to local CLI skills`);
    } catch (err: any) {
      this.toasts.error(err?.error?.detail || `Failed to sync ${s.name} locally`);
    } finally {
      this.syncing.set(false);
    }
  }

  async syncAll(): Promise<void> {
    this.syncing.set('__all__');
    try {
      const result = await this.skillService.syncAllSkillsLocal();
      this.toasts.success(`${result.count} skill(s) synced to local CLI directories`);
    } catch (err: any) {
      this.toasts.error(err?.error?.detail || 'Failed to sync skills locally');
    } finally {
      this.syncing.set(false);
    }
  }

  // ── Skill creation ────────────────────────────────

  async submitCreateSkill(): Promise<void> {
    const name = this.createName().trim();
    const description = this.createDescription().trim();
    if (!name || !description) return;

    const tags = this.createTags()
      .split(',')
      .map(t => t.trim())
      .filter(Boolean);

    this.creating.set(true);
    this.createResult.set(null);
    try {
      const result = await this.skillService.createSkill({
        name,
        description,
        tags,
        risk_level: this.createRisk(),
      });
      this.createResult.set({ name: result.name, local_paths: result.local_paths });
      this.toasts.success(`Skill "${result.name}" created & synced to local`);
      // Refresh installed list so the new skill appears
      await this.refresh();
      // Reset form
      this.createName.set('');
      this.createDescription.set('');
      this.createTags.set('');
      this.createRisk.set('LOW');
    } catch (err: any) {
      this.toasts.error(err?.error?.detail || `Failed to create skill "${name}"`);
    } finally {
      this.creating.set(false);
    }
  }
}
