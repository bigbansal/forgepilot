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
    const token = this.auth.accessToken();
    if (!token) {
      onStatus('DISCONNECTED');
      return () => {};
    }

    onStatus('CONNECTING');
    const url = `${this.apiBase.baseUrl}/events/stream?token=${encodeURIComponent(token)}`;
    const eventSource = new EventSource(url);

    eventSource.onopen = () => onStatus('CONNECTED');
    eventSource.onerror = () => onStatus('RECONNECTING');

    const eventTypes = [
      'task.created',
      'task.running',
      'task.waiting_approval',
      'task.completed',
      'task.failed',
      'task.log',
      'session.created',
      'sandbox.exec',
      'heartbeat'
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
            payload: { raw: message.data }
          });
        }
      });
    }

    return () => {
      eventSource.close();
      onStatus('DISCONNECTED');
    };
  }
}
