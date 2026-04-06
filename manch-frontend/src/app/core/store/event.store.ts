import { Injectable, computed, signal } from '@angular/core';

import { StreamEvent } from '../models/event.model';

@Injectable({ providedIn: 'root' })
export class EventStore {
  private readonly _events = signal<StreamEvent[]>([]);
  readonly events = this._events.asReadonly();

  readonly latestEvent = computed(() => this._events()[0] ?? null);

  push(event: StreamEvent): void {
    this._events.update((items) => [event, ...items].slice(0, 120));
  }

  clear(): void {
    this._events.set([]);
  }
}
