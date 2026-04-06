import { Injectable } from '@angular/core';
import { ApiBaseService } from './api-base.service';
import { AuthService } from './auth.service';
import { StreamEvent, StreamStatus } from '../models/event.model';

@Injectable({ providedIn: 'root' })
export class EventStreamService {
  constructor(
    private readonly apiBase: ApiBaseService,
    private readonly auth: AuthService,
  ) {}

  connect(
    onEvent: (event: StreamEvent) => void,
    onStatus: (status: StreamStatus) => void,
  ): () => void {
    let eventSource: EventSource | null = null;
    let disposed = false;
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;
    let retryDelay = 1000;

    const createConnection = () => {
      if (disposed) return;

      const token = this.auth.accessToken();
      if (!token) {
        onStatus('DISCONNECTED');
        return;
      }

      onStatus('CONNECTING');
      const url = `${this.apiBase.baseUrl}/events/stream?token=${encodeURIComponent(token)}`;
      eventSource = new EventSource(url);

      eventSource.onopen = () => {
        onStatus('CONNECTED');
        retryDelay = 1000; // reset backoff
      };

      eventSource.onerror = () => {
        onStatus('RECONNECTING');
        eventSource?.close();
        // Exponential backoff: 1s, 2s, 4s, 8s, max 15s
        retryTimeout = setTimeout(createConnection, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 15000);
      };

      const eventTypes = [
        'task.created',
        'task.running',
        'task.waiting_approval',
        'task.completed',
        'task.failed',
        'task.log',
        'task.planned',
        'task.agent_start',
        'task.agent_done',
        'task.agent_error',
        'task.agent_resume',
        'step.running',
        'step.completed',
        'session.created',
        'sandbox.exec',
        'heartbeat',
      ];

      for (const type of eventTypes) {
        eventSource.addEventListener(type, (raw: Event) => {
          const message = raw as MessageEvent;
          if (type === 'heartbeat') {
            onStatus('CONNECTED');
            return;
          }

          try {
            const parsed = JSON.parse(message.data) as StreamEvent;
            onEvent({ ...parsed, type });
          } catch {
            onEvent({
              type,
              timestamp: new Date().toISOString(),
              payload: { raw: message.data },
            });
          }
        });
      }
    };

    createConnection();

    return () => {
      disposed = true;
      if (retryTimeout) clearTimeout(retryTimeout);
      eventSource?.close();
      onStatus('DISCONNECTED');
    };
  }
}
