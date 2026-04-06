import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ApiBaseService {
  readonly baseUrl = 'http://localhost:8212/api/v1';

  /** WebSocket base URL — derived from baseUrl (http→ws, https→wss). */
  readonly wsUrl = this.baseUrl.replace(/^http/, 'ws');
}
