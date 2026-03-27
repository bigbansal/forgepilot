import { Injectable, computed, signal } from '@angular/core';
import { ChatMessage, Conversation, MessageRole } from '../models/chat.model';
import { TaskStatus } from '../models/task.model';

@Injectable({ providedIn: 'root' })
export class ChatStore {
  private readonly _conversations = signal<Conversation[]>([]);
  private readonly _activeConversationId = signal<string | null>(null);

  readonly conversations = this._conversations.asReadonly();
  readonly activeConversation = computed(() => {
    const activeId = this._activeConversationId();
    if (!activeId) {
      return null;
    }
    return this._conversations().find((item) => item.id === activeId) ?? null;
  });

  constructor() {}

  replaceConversations(items: Conversation[]): void {
    this._conversations.set(items);

    if (items.length === 0) {
      this._activeConversationId.set(null);
      return;
    }

    const current = this._activeConversationId();
    const exists = current ? items.some((item) => item.id === current) : false;
    if (!exists) {
      this._activeConversationId.set(items[0].id);
    }
  }

  upsertConversation(conversation: Conversation): void {
    this._conversations.update((list) => {
      const found = list.find((item) => item.id === conversation.id);
      if (!found) {
        return [conversation, ...list].sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));
      }

      return list
        .map((item) => (item.id === conversation.id ? { ...item, ...conversation } : item))
        .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));
    });

    if (!this._activeConversationId()) {
      this._activeConversationId.set(conversation.id);
    }
  }

  createConversation(title: string): Conversation {
    const now = new Date().toISOString();
    const conversation: Conversation = {
      id: this.generateId(),
      title,
      createdAt: now,
      updatedAt: now,
      messages: []
    };

    this._conversations.update((list) => [conversation, ...list]);
    return conversation;
  }

  startNewConversation(): void {
    const conversation = this.createConversation('New Chat');
    this._activeConversationId.set(conversation.id);
  }

  setActiveConversation(id: string): void {
    this._activeConversationId.set(id);
  }

  appendMessage(role: MessageRole, content: string, taskId?: string): ChatMessage {
    const active = this.activeConversation();
    if (!active) {
      throw new Error('No active conversation');
    }

    const message: ChatMessage = {
      id: this.generateId(),
      role,
      content,
      createdAt: new Date().toISOString(),
      taskId,
    };

    this._conversations.update((list) =>
      list.map((item) => {
        if (item.id !== active.id) {
          return item;
        }
        return {
          ...item,
          title: item.messages.length === 0 && role === 'user' ? this.summarizeTitle(content) : item.title,
          updatedAt: new Date().toISOString(),
          messages: [...item.messages, message],
          latestTaskId: taskId ?? item.latestTaskId,
        };
      })
    );

    return message;
  }

  updateActiveTaskStatus(status: TaskStatus, taskId?: string): void {
    const active = this.activeConversation();
    if (!active) {
      return;
    }

    this._conversations.update((list) =>
      list.map((item) => {
        if (item.id !== active.id) {
          return item;
        }
        return {
          ...item,
          latestTaskStatus: status,
          latestTaskId: taskId ?? item.latestTaskId,
          updatedAt: new Date().toISOString(),
        };
      })
    );
  }

  getActiveConversationId(): string | null {
    return this._activeConversationId();
  }

  private summarizeTitle(content: string): string {
    const cleaned = content.trim().replace(/\s+/g, ' ');
    if (!cleaned) {
      return 'New Chat';
    }
    return cleaned.length > 40 ? `${cleaned.slice(0, 40)}...` : cleaned;
  }

  private generateId(): string {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }
}
