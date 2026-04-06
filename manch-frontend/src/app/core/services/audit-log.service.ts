import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ApiBaseService } from './api-base.service';

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  detail: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

@Injectable({ providedIn: 'root' })
export class AuditLogService {
  private http = inject(HttpClient);
  private api = inject(ApiBaseService);

  list(opts: { page?: number; pageSize?: number; action?: string; resourceType?: string; userId?: string } = {}) {
    let params = new HttpParams();
    if (opts.page) params = params.set('page', opts.page);
    if (opts.pageSize) params = params.set('page_size', opts.pageSize);
    if (opts.action) params = params.set('action', opts.action);
    if (opts.resourceType) params = params.set('resource_type', opts.resourceType);
    if (opts.userId) params = params.set('user_id', opts.userId);
    return this.http.get<AuditLogListResponse>(`${this.api.baseUrl}/audit-log`, { params });
  }

  listActions() {
    return this.http.get<string[]>(`${this.api.baseUrl}/audit-log/actions`);
  }
}
