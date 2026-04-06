import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { ApiBaseService } from './api-base.service';

export interface AgentDefinition {
  name: string;
  tier: string;
  purpose: string;
  file_path: string;
}

export interface RegisteredAgent {
  name: string;
  tier: string;
  model_class: string;
  parallel_safe: boolean;
  purpose: string;
}

@Injectable({ providedIn: 'root' })
export class AgentService {
  constructor(
    private readonly http: HttpClient,
    private readonly apiBase: ApiBaseService,
  ) {}

  listAgents(): Promise<AgentDefinition[]> {
    return firstValueFrom(this.http.get<AgentDefinition[]>(`${this.apiBase.baseUrl}/agents`));
  }

  listRegistryAgents(): Promise<RegisteredAgent[]> {
    return firstValueFrom(this.http.get<RegisteredAgent[]>(`${this.apiBase.baseUrl}/agents/registry`));
  }
}
