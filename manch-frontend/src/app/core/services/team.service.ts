import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ApiBaseService } from './api-base.service';
import { Team, TeamMember, TeamSummary } from '../models/team.model';

@Injectable({ providedIn: 'root' })
export class TeamService {
  private readonly http = inject(HttpClient);
  private readonly apiBase = inject(ApiBaseService);

  /** List all teams the current user is a member of. */
  listMyTeams(): Promise<TeamSummary[]> {
    return firstValueFrom(
      this.http.get<TeamSummary[]>(`${this.apiBase.baseUrl}/auth/teams`),
    );
  }

  /** Create a new team. */
  createTeam(name: string): Promise<Team> {
    return firstValueFrom(
      this.http.post<Team>(`${this.apiBase.baseUrl}/auth/teams`, { name }),
    );
  }

  /** List members of a team. */
  listMembers(teamId: string): Promise<TeamMember[]> {
    return firstValueFrom(
      this.http.get<TeamMember[]>(`${this.apiBase.baseUrl}/auth/teams/${teamId}/members`),
    );
  }

  /** Invite a user to a team. */
  inviteMember(teamId: string, email: string, role: string = 'member'): Promise<TeamMember> {
    return firstValueFrom(
      this.http.post<TeamMember>(`${this.apiBase.baseUrl}/auth/teams/${teamId}/members`, { email, role }),
    );
  }

  /** Remove a member from a team. */
  removeMember(teamId: string, userId: string): Promise<void> {
    return firstValueFrom(
      this.http.delete<void>(`${this.apiBase.baseUrl}/auth/teams/${teamId}/members/${userId}`),
    );
  }

  /** Switch active team (gets new tokens). */
  switchTeam(teamId: string): Promise<{ access_token: string; refresh_token: string; token_type: string; team_id: string }> {
    return firstValueFrom(
      this.http.post<{ access_token: string; refresh_token: string; token_type: string; team_id: string }>(
        `${this.apiBase.baseUrl}/auth/switch-team`,
        { team_id: teamId },
      ),
    );
  }
}
