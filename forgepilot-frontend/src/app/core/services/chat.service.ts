import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ApiBaseService } from './api-base.service';
import { Conversation } from '../models/chat.model';
import { TaskRunner, TaskStatus } from '../models/task.model';

type ApiChatMessage = {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  task_id?: string | null;
};

type ApiConversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: ApiChatMessage[];
};

type SendMessageResponse = {
  conversation: ApiConversation;
  task?: {
    id: string;
    status: TaskStatus;
  };
};

@Injectable({ providedIn: 'root' })
export class ChatService {
  constructor(
    private readonly http: HttpClient,
    private readonly apiBase: ApiBaseService,
  ) {}

  async listConversations(): Promise<Conversation[]> {
    const rows = await firstValueFrom(
      this.http.get<ApiConversation[]>(`${this.apiBase.baseUrl}/conversations`)
    );
    return rows.map((row) => this.mapConversation(row));
  }

  async createConversation(title = 'New Chat'): Promise<Conversation> {
    const row = await firstValueFrom(
      this.http.post<ApiConversation>(`${this.apiBase.baseUrl}/conversations`, { title })
    );
    return this.mapConversation(row);
  }

  async getConversation(conversationId: string): Promise<Conversation> {
    const row = await firstValueFrom(
      this.http.get<ApiConversation>(`${this.apiBase.baseUrl}/conversations/${conversationId}`)
    );
    return this.mapConversation(row);
  }

  async sendMessage(
    conversationId: string,
    content: string,
    runner: TaskRunner,
    approvalMode: string = 'yolo',
  ): Promise<{ conversation: Conversation; taskId?: string; taskStatus?: TaskStatus }> {
    const response = await firstValueFrom(
      this.http.post<SendMessageResponse>(
        `${this.apiBase.baseUrl}/conversations/${conversationId}/messages`,
        { content, runner, approval_mode: approvalMode }
      )
    );

    return {
      conversation: this.mapConversation(response.conversation),
      taskId: response.task?.id,
      taskStatus: response.task?.status,
    };
  }

  private mapConversation(row: ApiConversation): Conversation {
    const messages = (row.messages ?? []).map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      createdAt: message.created_at,
      taskId: message.task_id ?? undefined,
    }));

    const latestTaskId = [...messages].reverse().find((item) => item.taskId)?.taskId;

    return {
      id: row.id,
      title: row.title,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      messages,
      latestTaskId,
    };
  }
}
