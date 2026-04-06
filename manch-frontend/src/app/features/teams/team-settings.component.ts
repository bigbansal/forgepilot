import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { TeamService } from '../../core/services/team.service';
import { TeamSummary, TeamMember } from '../../core/models/team.model';
import { ToastStore } from '../../shared/components/toast/toast.component';

@Component({
  selector: 'fp-team-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="page">
      <div class="page-header">
        <h1>Teams</h1>
        <button class="btn btn-primary" (click)="showCreateForm.set(!showCreateForm())">
          {{ showCreateForm() ? 'Cancel' : '+ New Team' }}
        </button>
      </div>

      <!-- Create team form -->
      @if (showCreateForm()) {
        <div class="card create-form">
          <input type="text" [(ngModel)]="newTeamName" placeholder="Team name" class="input" />
          <button class="btn btn-primary" [disabled]="!newTeamName.trim()" (click)="createTeam()">Create</button>
        </div>
      }

      <!-- Team list -->
      <div class="team-grid">
        @for (team of teams(); track team.id) {
          <div class="card team-card" [class.active]="team.id === auth.activeTeamId()" (click)="selectTeam(team)">
            <div class="team-card-header">
              <h3>{{ team.name }}</h3>
              <span class="badge">{{ team.role }}</span>
            </div>
            <small class="slug">/{{ team.slug }}</small>
          </div>
        }
      </div>

      <!-- Selected team members -->
      @if (selectedTeam()) {
        <div class="card members-section">
          <h2>Members — {{ selectedTeam()!.name }}</h2>

          @if (selectedTeam()!.role === 'owner' || selectedTeam()!.role === 'admin') {
            <div class="invite-row">
              <input type="email" [(ngModel)]="inviteEmail" placeholder="Email address" class="input" />
              <select [(ngModel)]="inviteRole" class="input select">
                <option value="member">Member</option>
                <option value="admin">Admin</option>
                <option value="viewer">Viewer</option>
              </select>
              <button class="btn btn-primary" [disabled]="!inviteEmail.trim()" (click)="inviteMember()">Invite</button>
            </div>
          }

          <table class="members-table" *ngIf="members().length > 0">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Joined</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (m of members(); track m.id) {
                <tr>
                  <td>{{ m.full_name ?? '—' }}</td>
                  <td>{{ m.email }}</td>
                  <td><span class="badge">{{ m.role }}</span></td>
                  <td>{{ m.joined_at | date: 'mediumDate' }}</td>
                  <td>
                    @if ((selectedTeam()!.role === 'owner' || selectedTeam()!.role === 'admin') && m.role !== 'owner') {
                      <button class="btn btn-danger btn-sm" (click)="removeMember(m)">Remove</button>
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table>

          <p *ngIf="members().length === 0" class="empty-msg">No members loaded.</p>
        </div>
      }
    </div>
  `,
  styles: [`
    .page { padding: 20px 24px; max-width: 900px; }
    .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
    .page-header h1 { font-size: 18px; font-weight: 600; }

    .card { background: var(--c-elevated); border: 1px solid var(--c-border-muted); border-radius: var(--r-md, 8px); padding: 14px; margin-bottom: 12px; }
    .create-form { display: flex; gap: 8px; align-items: center; }

    .team-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin-bottom: 20px; }
    .team-card { cursor: pointer; transition: border-color 0.15s; }
    .team-card:hover { border-color: var(--c-accent-emphasis); }
    .team-card.active { border-color: var(--c-accent-emphasis); box-shadow: 0 0 0 1px var(--c-accent-emphasis); }
    .team-card-header { display: flex; align-items: center; justify-content: space-between; }
    .team-card-header h3 { font-size: 14px; font-weight: 600; margin: 0; }
    .slug { color: var(--c-text-faint); font-size: 11px; }

    .badge { font-size: 10px; padding: 2px 6px; border-radius: 3px; background: var(--c-surface-hover, rgba(0,0,0,0.06)); text-transform: uppercase; color: var(--c-text-muted); }

    .members-section h2 { font-size: 15px; font-weight: 600; margin-bottom: 12px; }
    .invite-row { display: flex; gap: 8px; margin-bottom: 12px; }
    .input { font-size: 12px; padding: 6px 8px; border: 1px solid var(--c-border); border-radius: var(--r-sm, 4px); background: var(--c-canvas); color: var(--c-text); outline: none; }
    .input:focus { border-color: var(--c-accent-emphasis); }
    .select { min-width: 100px; }

    .members-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .members-table th { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--c-border-muted); color: var(--c-text-muted); font-weight: 500; }
    .members-table td { padding: 6px 8px; border-bottom: 1px solid var(--c-border-muted); }

    .btn { font-size: 12px; padding: 6px 12px; border: none; border-radius: var(--r-sm, 4px); cursor: pointer; font-weight: 500; }
    .btn-primary { background: var(--c-accent-emphasis); color: #fff; }
    .btn-primary:disabled { opacity: 0.5; cursor: default; }
    .btn-danger { background: #d1242f; color: #fff; }
    .btn-sm { padding: 3px 8px; font-size: 11px; }
    .empty-msg { color: var(--c-text-faint); font-size: 12px; }
  `],
})
export class TeamSettingsComponent implements OnInit {
  readonly auth = inject(AuthService);
  private readonly teamService = inject(TeamService);
  private readonly toasts = inject(ToastStore);

  readonly teams = this.auth.teams;
  readonly selectedTeam = signal<TeamSummary | null>(null);
  readonly members = signal<TeamMember[]>([]);
  readonly showCreateForm = signal(false);

  newTeamName = '';
  inviteEmail = '';
  inviteRole = 'member';

  ngOnInit(): void {
    // Select active team by default
    const active = this.auth.activeTeam();
    if (active) {
      this.selectTeam(active);
    }
  }

  async selectTeam(team: TeamSummary): Promise<void> {
    this.selectedTeam.set(team);
    try {
      const m = await this.teamService.listMembers(team.id);
      this.members.set(m);
    } catch {
      this.members.set([]);
    }
  }

  async createTeam(): Promise<void> {
    const name = this.newTeamName.trim();
    if (!name) return;
    try {
      await this.teamService.createTeam(name);
      this.newTeamName = '';
      this.showCreateForm.set(false);
      this.toasts.success('Team created');
      // Reload profile to refresh teams list
      await this.auth.loadProfile();
    } catch {
      this.toasts.error('Failed to create team');
    }
  }

  async inviteMember(): Promise<void> {
    const team = this.selectedTeam();
    if (!team || !this.inviteEmail.trim()) return;
    try {
      await this.teamService.inviteMember(team.id, this.inviteEmail.trim(), this.inviteRole);
      this.inviteEmail = '';
      this.toasts.success('Member invited');
      await this.selectTeam(team); // refresh members
    } catch {
      this.toasts.error('Failed to invite member');
    }
  }

  async removeMember(member: TeamMember): Promise<void> {
    const team = this.selectedTeam();
    if (!team) return;
    try {
      await this.teamService.removeMember(team.id, member.user_id);
      this.toasts.success('Member removed');
      await this.selectTeam(team);
    } catch {
      this.toasts.error('Failed to remove member');
    }
  }
}
