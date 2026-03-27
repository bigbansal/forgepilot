import { Injectable, computed, signal } from '@angular/core';

import { Task, TaskStatus } from '../models/task.model';

@Injectable({ providedIn: 'root' })
export class TaskStore {
  private readonly _tasks = signal<Task[]>([]);
  readonly tasks = this._tasks.asReadonly();

  readonly runningCount = computed(() => this._tasks().filter((task) => task.status === 'RUNNING').length);

  setTasks(tasks: Task[]): void {
    this._tasks.set(tasks);
  }

  upsertTask(task: Task): void {
    this._tasks.update((items) => {
      const found = items.find((item) => item.id === task.id);
      if (!found) {
        return [task, ...items].sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1));
      }
      return items
        .map((item) => (item.id === task.id ? task : item))
        .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1));
    });
  }

  updateTaskStatus(taskId: string, status: TaskStatus): void {
    this._tasks.update((items) =>
      items.map((task) =>
        task.id === taskId
          ? { ...task, status, updated_at: new Date().toISOString() }
          : task
      )
    );
  }
}
