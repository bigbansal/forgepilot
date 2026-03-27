import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login.component').then((m) => m.LoginComponent),
  },
  {
    path: '',
    loadComponent: () => import('./layout/shell/shell.component').then((m) => m.ShellComponent),
    canActivate: [authGuard],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'chat' },
      { path: 'chat', loadComponent: () => import('./features/chat/chat-home.component').then((m) => m.ChatHomeComponent) },
      { path: 'chat/thread', loadComponent: () => import('./features/chat/chat-thread.component').then((m) => m.ChatThreadComponent) },
      { path: 'dashboard', loadComponent: () => import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent) },
      { path: 'tasks', loadComponent: () => import('./features/tasks/task-list.component').then((m) => m.TaskListComponent) },
      { path: 'tasks/:id', loadComponent: () => import('./features/tasks/task-detail.component').then((m) => m.TaskDetailComponent) },
    ],
  },
];
