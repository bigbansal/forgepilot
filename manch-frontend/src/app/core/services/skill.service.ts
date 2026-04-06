import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { ApiBaseService } from './api-base.service';

export interface SkillSummary {
  name: string;
  version: string;
  description: string;
  kind: string;
  risk_level: string;
  author: string;
  tags: string[];
  enabled: boolean;
}

export interface SkillDetail extends SkillSummary {
  config: Record<string, unknown>;
  config_schema: Record<string, unknown>;
  dependencies: string[];
}

export interface MarketplaceItem {
  name: string;
  version: string;
  description: string;
  kind: string;
  risk_level: string;
  author: string;
  tags: string[];
  dependencies: string[];
  category: string;
  downloads: number;
  icon: string;
  installed: boolean;
}

export interface MarketplaceCategory {
  name: string;
  count: number;
}

@Injectable({ providedIn: 'root' })
export class SkillService {
  constructor(
    private readonly http: HttpClient,
    private readonly apiBase: ApiBaseService,
  ) {}

  // ── Installed skills ────────────────────────────

  listSkills(): Promise<SkillSummary[]> {
    return firstValueFrom(this.http.get<SkillSummary[]>(`${this.apiBase.baseUrl}/skills`));
  }

  getSkill(name: string): Promise<SkillDetail> {
    return firstValueFrom(this.http.get<SkillDetail>(`${this.apiBase.baseUrl}/skills/${name}`));
  }

  enableSkill(name: string): Promise<{ status: string; name: string }> {
    return firstValueFrom(this.http.post<{ status: string; name: string }>(`${this.apiBase.baseUrl}/skills/${name}/enable`, {}));
  }

  disableSkill(name: string): Promise<{ status: string; name: string }> {
    return firstValueFrom(this.http.post<{ status: string; name: string }>(`${this.apiBase.baseUrl}/skills/${name}/disable`, {}));
  }

  updateConfig(name: string, config: Record<string, unknown>): Promise<any> {
    return firstValueFrom(this.http.put(`${this.apiBase.baseUrl}/skills/${name}/config`, { config }));
  }

  // ── Local CLI sync ──────────────────────────────

  getSkillMd(name: string): Promise<string> {
    return firstValueFrom(
      this.http.get(`${this.apiBase.baseUrl}/skills/${name}/skill-md`, { responseType: 'text' }),
    );
  }

  syncSkillLocal(name: string): Promise<{ status: string; name: string; paths: string[] }> {
    return firstValueFrom(
      this.http.post<{ status: string; name: string; paths: string[] }>(`${this.apiBase.baseUrl}/skills/${name}/sync-local`, {}),
    );
  }

  syncAllSkillsLocal(): Promise<{ status: string; count: number; paths: string[] }> {
    return firstValueFrom(
      this.http.post<{ status: string; count: number; paths: string[] }>(`${this.apiBase.baseUrl}/skills/sync-all-local`, {}),
    );
  }

  // ── Skill creation ──────────────────────────────

  createSkill(data: { name: string; description: string; tags?: string[]; author?: string; risk_level?: string }): Promise<{ status: string; name: string; description: string; file: string; local_paths: string[] }> {
    return firstValueFrom(
      this.http.post<{ status: string; name: string; description: string; file: string; local_paths: string[] }>(`${this.apiBase.baseUrl}/skills/create`, data),
    );
  }

  // ── Marketplace ─────────────────────────────────

  listMarketplace(category?: string, search?: string): Promise<MarketplaceItem[]> {
    const params: Record<string, string> = {};
    if (category) params['category'] = category;
    if (search) params['search'] = search;
    return firstValueFrom(
      this.http.get<MarketplaceItem[]>(`${this.apiBase.baseUrl}/skills/marketplace`, { params }),
    );
  }

  getMarketplaceCategories(): Promise<MarketplaceCategory[]> {
    return firstValueFrom(
      this.http.get<MarketplaceCategory[]>(`${this.apiBase.baseUrl}/skills/marketplace/categories`),
    );
  }

  installSkill(name: string): Promise<{ status: string; name: string }> {
    return firstValueFrom(
      this.http.post<{ status: string; name: string }>(`${this.apiBase.baseUrl}/skills/marketplace/install`, { name }),
    );
  }

  uninstallSkill(name: string): Promise<{ status: string; name: string }> {
    return firstValueFrom(
      this.http.post<{ status: string; name: string }>(`${this.apiBase.baseUrl}/skills/marketplace/uninstall`, { name }),
    );
  }
}
