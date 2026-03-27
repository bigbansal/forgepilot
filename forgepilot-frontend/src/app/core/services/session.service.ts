import { Injectable } from '@angular/core';

import { TaskService } from './task.service';
import { SessionRecord } from '../models/task.model';

@Injectable({ providedIn: 'root' })
export class SessionService {
  constructor(private readonly taskService: TaskService) {}

  listSessions(): Promise<SessionRecord[]> {
    return this.taskService.listSessions();
  }
}
