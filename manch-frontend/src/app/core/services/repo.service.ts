import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ApiBaseService } from './api-base.service';

export interface RepoSummary {
  id: string;
  name: string;
  url: string;
  default_branch: string;
  description: string | null;
  is_active: boolean;
  last_synced_at: string | null;
  created_at: string;
}

export interface RepoCreate {
  name: string;
  url: string;
  default_branch?: string;
  description?: string;
}

export interface RepoCloneResponse {
  status: string;
  repo_id: string;
  repo_name: string;
  clone_url: string;
  branch: string;
  sandbox_session_id: string;
  stdout: string;
  stderr: string;
  exit_code: number;
}

@Injectable({ providedIn: 'root' })
export class RepoService {
  private http = inject(HttpClient);
  private api = inject(ApiBaseService);

  list(activeOnly = true) {
    const params = new HttpParams().set('active_only', activeOnly);
    return this.http.get<RepoSummary[]>(`${this.api.baseUrl}/repos`, { params });
  }

  get(id: string) {
    return this.http.get<RepoSummary>(`${this.api.baseUrl}/repos/${id}`);
  }

  create(body: RepoCreate) {
    return this.http.post<RepoSummary>(`${this.api.baseUrl}/repos`, body);
  }

  update(id: string, body: Partial<RepoCreate & { is_active: boolean }>) {
    return this.http.patch<RepoSummary>(`${this.api.baseUrl}/repos/${id}`, body);
  }

  delete(id: string) {
    return this.http.delete<void>(`${this.api.baseUrl}/repos/${id}`);
  }

  /** Clone a registered repo into a sandbox */
  clone(repoId: string, opts?: { branch?: string; depth?: number }) {
    return this.http.post<RepoCloneResponse>(`${this.api.baseUrl}/repos/${repoId}/clone`, opts ?? {});
  }

  /** Quick clone any git URL (auto-registers the repo) */
  quickClone(url: string, opts?: { branch?: string; depth?: number; name?: string }) {
    return this.http.post<RepoCloneResponse>(`${this.api.baseUrl}/repos/clone`, { url, ...opts });
  }
}
