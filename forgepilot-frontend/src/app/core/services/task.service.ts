import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ApiBaseService } from './api-base.service';
import { SessionRecord, Task, TaskMessage, TaskRunner, TaskStartResponse } from '../models/task.model';

@Injectable({ providedIn: 'root' })
export class TaskService {
  constructor(
    private readonly http: HttpClient,
    private readonly apiBase: ApiBaseService,
  ) {}

  createTask(prompt: string): Promise<Task> {
    return firstValueFrom(
      this.http.post<Task>(`${this.apiBase.baseUrl}/tasks`, { prompt })
    );
  }

  startTask(taskId: string, runner: TaskRunner): Promise<TaskStartResponse> {
    return firstValueFrom(
      this.http.post<TaskStartResponse>(`${this.apiBase.baseUrl}/tasks/${taskId}/start`, { runner })
    );
  }

  listTasks(): Promise<Task[]> {
    return firstValueFrom(this.http.get<Task[]>(`${this.apiBase.baseUrl}/tasks`));
  }

  getTask(taskId: string): Promise<Task> {
    return firstValueFrom(this.http.get<Task>(`${this.apiBase.baseUrl}/tasks/${taskId}`));
  }

  getTaskMessages(taskId: string): Promise<TaskMessage[]> {
    return firstValueFrom(this.http.get<TaskMessage[]>(`${this.apiBase.baseUrl}/tasks/${taskId}/messages`));
  }

  listSessions(): Promise<SessionRecord[]> {
    return firstValueFrom(this.http.get<SessionRecord[]>(`${this.apiBase.baseUrl}/sessions`));
  }
}
