import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';
import { Observable } from 'rxjs';
import { ApiBaseService } from './api-base.service';

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

const ACCESS_TOKEN_KEY = 'fp_access_token';
const REFRESH_TOKEN_KEY = 'fp_refresh_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly apiBase = inject(ApiBaseService);

  private readonly _currentUser = signal<User | null>(null);
  readonly currentUser = this._currentUser.asReadonly();
  readonly isLoggedIn = computed(() => this._currentUser() !== null);

  accessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  }

  refreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  private storeTokens(tokens: TokenResponse): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  }

  private clearTokens(): void {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
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

  loadProfile(): void {
    const token = this.accessToken();
    if (!token) return;
    this.http.get<User>(`${this.apiBase.baseUrl}/auth/me`).subscribe({
      next: (user) => this._currentUser.set(user),
      error: () => {
        this.clearTokens();
        this._currentUser.set(null);
      },
    });
  }

  logout(): void {
    this.clearTokens();
    this._currentUser.set(null);
    this.router.navigate(['/login']);
  }
}
