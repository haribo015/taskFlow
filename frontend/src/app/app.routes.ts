import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './core/auth';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'workspaces' },
  {
    path: 'login',
    canActivate: [guestGuard],
    title: 'Connexion · TaskFlow',
    loadComponent: () => import('./features/auth/login-page').then((m) => m.LoginPage),
  },
  {
    path: 'register',
    canActivate: [guestGuard],
    title: 'Inscription · TaskFlow',
    loadComponent: () => import('./features/auth/register-page').then((m) => m.RegisterPage),
  },
  {
    path: 'workspaces',
    canActivate: [authGuard],
    title: 'Espaces · TaskFlow',
    loadComponent: () =>
      import('./features/workspaces/workspaces-page').then((m) => m.WorkspacesPage),
  },
  {
    path: 'workspaces/:id',
    canActivate: [authGuard],
    title: 'Espace · TaskFlow',
    loadComponent: () =>
      import('./features/workspaces/workspace-detail-page').then((m) => m.WorkspaceDetailPage),
  },
  {
    path: 'my-tasks',
    canActivate: [authGuard],
    title: 'Mes tâches · TaskFlow',
    loadComponent: () => import('./features/tasks/my-tasks-page').then((m) => m.MyTasksPage),
  },
  { path: '**', redirectTo: 'workspaces' },
];
