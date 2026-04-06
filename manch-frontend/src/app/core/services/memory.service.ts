import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ApiBaseService } from './api-base.service';

export interface MemoryEntry {
  id: string;
  key: string;
  category: string;
  content: string;
  tags: string[];
  confidence: number;
  retention_value: string;
  source_task_id: string | null;
  created_at: string;
}

export interface MemoryListResponse {
  items: MemoryEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface MemoryStats {
  total_entries: number;
  categories: Record<string, number>;
  avg_confidence: number;
}

@Injectable({ providedIn: 'root' })
export class MemoryService {
  private http = inject(HttpClient);
  private api = inject(ApiBaseService);

  list(opts: { page?: number; pageSize?: number; category?: string; tag?: string; minConfidence?: number } = {}) {
    let params = new HttpParams();
    if (opts.page) params = params.set('page', opts.page);
    if (opts.pageSize) params = params.set('page_size', opts.pageSize);
    if (opts.category) params = params.set('category', opts.category);
    if (opts.tag) params = params.set('tag', opts.tag);
    if (opts.minConfidence) params = params.set('min_confidence', opts.minConfidence);
    return this.http.get<MemoryListResponse>(`${this.api.baseUrl}/memory`, { params });
  }

  stats() {
    return this.http.get<MemoryStats>(`${this.api.baseUrl}/memory/stats`);
  }

  categories() {
    return this.http.get<string[]>(`${this.api.baseUrl}/memory/categories`);
  }

  delete(id: string) {
    return this.http.delete<void>(`${this.api.baseUrl}/memory/${id}`);
  }
}
