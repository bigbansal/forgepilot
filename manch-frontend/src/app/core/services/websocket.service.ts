import { Injectable, inject, NgZone } from '@angular/core';
import { ApiBaseService } from './api-base.service';
import { AuthService } from './auth.service';
import { StreamEvent, StreamStatus } from '../models/event.model';

type EventListener = (event: StreamEvent) => void;
type StatusListener = (status: StreamStatus) => void;

interface Listener {
  id: number;
  onEvent: EventListener;
  onStatus: StatusListener;
}

/**
 * WebSocket-based event service — replaces SSE EventStreamService.
 *
 * Singleton connection shared by all components. Multiple callers can call
 * connect() — each receives events through their own callbacks.
 * Connection is established on the first connect() and torn down when the
 * last listener disconnects.
 *
 * Protocol (JSON):
 *   → { action: "subscribe", task_ids: ["..."] }
 *   → { action: "unsubscribe", task_ids: ["..."] }
 *   → { action: "ping" }
 *   ← { type: "pong" }
 *   ← { type: "...", timestamp: "...", payload: {...} }
 */
@Injectable({ providedIn: 'root' })
export class WebSocketService {
  private readonly apiBase = inject(ApiBaseService);
  private readonly auth = inject(AuthService);
  private readonly zone = inject(NgZone);

  private ws: WebSocket | null = null;
  private disposed = false;
  private retryDelay = 1000;
  private retryTimeout: ReturnType<typeof setTimeout> | null = null;
  private pingInterval: ReturnType<typeof setInterval> | null = null;

  private listeners: Listener[] = [];
  private nextListenerId = 0;
  private currentStatus: StreamStatus = 'DISCONNECTED';

  private subscribedTaskIds = new Set<string>();

  /**
   * Register a listener and ensure the shared WS connection is open.
   * Returns a dispose function — when all listeners have disconnected
   * the socket is closed.
   */
  connect(
    onEvent: EventListener,
    onStatus: StatusListener,
  ): () => void {
    const id = this.nextListenerId++;
    this.listeners.push({ id, onEvent, onStatus });

    // Immediately inform the new listener of current status
    onStatus(this.currentStatus);

    // Open the shared connection if this is the first listener
    if (this.listeners.length === 1) {
      this.disposed = false;
      this.createConnection();
    }

    return () => {
      this.listeners = this.listeners.filter((l) => l.id !== id);
      if (this.listeners.length === 0) {
        this.disposed = true;
        this.cleanup();
        this.broadcastStatus('DISCONNECTED');
      }
    };
  }

  /** Subscribe to live events for specific task IDs. */
  subscribeToTasks(taskIds: string[]): void {
    for (const id of taskIds) this.subscribedTaskIds.add(id);
    this.send({ action: 'subscribe', task_ids: taskIds });
  }

  /** Unsubscribe from specific task IDs. */
  unsubscribeFromTasks(taskIds: string[]): void {
    for (const id of taskIds) this.subscribedTaskIds.delete(id);
    this.send({ action: 'unsubscribe', task_ids: taskIds });
  }

  private createConnection(): void {
    if (this.disposed) return;

    const token = this.auth.accessToken();
    if (!token) {
      this.broadcastStatus('DISCONNECTED');
      return;
    }

    this.broadcastStatus('CONNECTING');
    const url = `${this.apiBase.wsUrl}/events/ws?token=${encodeURIComponent(token)}`;

    this.zone.runOutsideAngular(() => {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.zone.run(() => this.broadcastStatus('CONNECTED'));
        this.retryDelay = 1000;

        // Re-subscribe to any task IDs we were following
        if (this.subscribedTaskIds.size > 0) {
          this.send({ action: 'subscribe', task_ids: Array.from(this.subscribedTaskIds) });
        }

        // Start keepalive pings every 25s
        this.pingInterval = setInterval(() => this.send({ action: 'ping' }), 25_000);
      };

      this.ws.onclose = () => {
        this.cleanupPing();
        if (!this.disposed) {
          this.zone.run(() => this.broadcastStatus('RECONNECTING'));
          this.retryTimeout = setTimeout(() => this.createConnection(), this.retryDelay);
          this.retryDelay = Math.min(this.retryDelay * 2, 15_000);
        }
      };

      this.ws.onerror = () => {
        // onclose will fire after onerror — reconnect happens there
      };

      this.ws.onmessage = (raw: MessageEvent) => {
        this.zone.run(() => {
          try {
            const data = JSON.parse(raw.data as string);
            const type: string = data.type ?? '';

            if (type === 'pong' || type === 'heartbeat') return;

            const event: StreamEvent = {
              type,
              timestamp: data.timestamp ?? new Date().toISOString(),
              payload: data.payload ?? data,
            };
            this.broadcastEvent(event);
          } catch {
            // Ignore malformed messages
          }
        });
      };
    });
  }

  private send(msg: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  private broadcastEvent(event: StreamEvent): void {
    for (const l of this.listeners) l.onEvent(event);
  }

  private broadcastStatus(status: StreamStatus): void {
    this.currentStatus = status;
    for (const l of this.listeners) l.onStatus(status);
  }

  private cleanupPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private cleanup(): void {
    this.cleanupPing();
    if (this.retryTimeout) {
      clearTimeout(this.retryTimeout);
      this.retryTimeout = null;
    }
    this.ws?.close();
    this.ws = null;
  }
}
