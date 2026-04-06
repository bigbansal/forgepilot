import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';
import { Observable } from 'rxjs';
import { ApiBaseService } from './api-base.service';
import { TeamSummary } from '../models/team.model';

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
  teams?: TeamSummary[];
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  team_id?: string;
}

const ACCESS_TOKEN_KEY = 'fp_access_token';
const REFRESH_TOKEN_KEY = 'fp_refresh_token';
const ACTIVE_TEAM_KEY = 'fp_active_team';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly apiBase = inject(ApiBaseService);

  private readonly _currentUser = signal<User | null>(null);
  readonly currentUser = this._currentUser.asReadonly();
  readonly isLoggedIn = computed(() => this._currentUser() !== null);

  private readonly _teams = signal<TeamSummary[]>([]);
  readonly teams = this._teams.asReadonly();

  private readonly _activeTeamId = signal<string | null>(localStorage.getItem(ACTIVE_TEAM_KEY));
  readonly activeTeamId = this._activeTeamId.asReadonly();
  readonly activeTeam = computed(() => this._teams().find((t) => t.id === this._activeTeamId()) ?? null);

  constructor() {
    // Bootstrap: restore user profile from stored token on page refresh
    if (this.accessToken()) {
      this.loadProfile();
    }
  }

  accessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  }

  refreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  private storeTokens(tokens: TokenResponse): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
    if (tokens.team_id) {
      localStorage.setItem(ACTIVE_TEAM_KEY, tokens.team_id);
      this._activeTeamId.set(tokens.team_id);
    }
  }

  private clearTokens(): void {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(ACTIVE_TEAM_KEY);
  }

  register(email: string, password: string, fullName?: string): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(`${this.apiBase.baseUrl}/auth/register`, {
        email,
        password,
        full_name: fullName ?? null,
      })
      .pipe(
        tap((tokens) => {
          this.storeTokens(tokens);
          this.loadProfile();
        }),
      );
  }

  login(email: string, password: string): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(`${this.apiBase.baseUrl}/auth/login`, { email, password })
      .pipe(
        tap((tokens) => {
          this.storeTokens(tokens);
          this.loadProfile();
        }),
      );
  }

  refresh(): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(`${this.apiBase.baseUrl}/auth/refresh`, {
        refresh_token: this.refreshToken(),
      })
      .pipe(
        tap((tokens) => {
          this.storeTokens(tokens);
        }),
      );
  }

  loadProfile(): Promise<User | null> {
    const token = this.accessToken();
    if (!token) return Promise.resolve(null);
    return new Promise((resolve) => {
      this.http.get<User>(`${this.apiBase.baseUrl}/auth/me`).subscribe({
        next: (user) => {
          this._currentUser.set(user);
          // Populate teams from profile if available
          if (user.teams) {
            this._teams.set(user.teams);
            // If no active team yet, pick the first one
            if (!this._activeTeamId() && user.teams.length > 0) {
              const firstTeam = user.teams[0];
              this._activeTeamId.set(firstTeam.id);
              localStorage.setItem(ACTIVE_TEAM_KEY, firstTeam.id);
            }
          }
          resolve(user);
        },
        error: () => {
          this.clearTokens();
          this._currentUser.set(null);
          resolve(null);
        },
      });
    });
  }

  /** Switch the active team, storing new tokens. */
  async switchTeam(teamId: string, newTokens: TokenResponse): Promise<void> {
    this.storeTokens(newTokens);
    this._activeTeamId.set(teamId);
    localStorage.setItem(ACTIVE_TEAM_KEY, teamId);
    await this.loadProfile();
  }

  logout(): void {
    this.clearTokens();
    this._currentUser.set(null);
    this._teams.set([]);
    this._activeTeamId.set(null);
    this.router.navigate(['/login']);
  }
}
