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
      { path: 'approvals', loadComponent: () => import('./features/approvals/approval-queue.component').then((m) => m.ApprovalQueueComponent) },
      { path: 'agents', loadComponent: () => import('./features/agents/agent-list.component').then((m) => m.AgentListComponent) },
      { path: 'skills', loadComponent: () => import('./features/skills/skill-list.component').then((m) => m.SkillListComponent) },
      { path: 'sessions', loadComponent: () => import('./features/sessions/session-list.component').then((m) => m.SessionListComponent) },
      { path: 'repos', loadComponent: () => import('./features/repos/repo-list.component').then((m) => m.RepoListComponent) },
      { path: 'memory', loadComponent: () => import('./features/memory/memory.component').then((m) => m.MemoryComponent) },
      { path: 'audit-log', loadComponent: () => import('./features/audit-log/audit-log.component').then((m) => m.AuditLogComponent) },
      { path: 'teams', loadComponent: () => import('./features/teams/team-settings.component').then((m) => m.TeamSettingsComponent) },
      { path: '**', redirectTo: 'chat' },
    ],
  },
];
