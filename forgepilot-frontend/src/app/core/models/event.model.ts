export interface StreamEvent {
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export type StreamStatus = 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED';
