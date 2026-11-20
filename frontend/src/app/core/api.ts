import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  Member,
  MyStats,
  Role,
  Task,
  TaskPayload,
  TaskStatus,
  Workspace,
  WorkspaceStats,
} from './models';

@Injectable({ providedIn: 'root' })
export class WorkspaceApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/workspaces';

  list(): Observable<Workspace[]> {
    return this.http.get<Workspace[]>(this.base);
  }

  get(id: number): Observable<Workspace> {
    return this.http.get<Workspace>(`${this.base}/${id}`);
  }

  create(name: string, description: string): Observable<Workspace> {
    return this.http.post<Workspace>(this.base, { name, description });
  }

  update(id: number, changes: { name?: string; description?: string }): Observable<Workspace> {
    return this.http.patch<Workspace>(`${this.base}/${id}`, changes);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }

  members(id: number): Observable<Member[]> {
    return this.http.get<Member[]>(`${this.base}/${id}/members`);
  }

  addMember(id: number, email: string, role: Exclude<Role, 'owner'>): Observable<Member> {
    return this.http.post<Member>(`${this.base}/${id}/members`, { email, role });
  }

  removeMember(id: number, userId: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}/members/${userId}`);
  }
}

@Injectable({ providedIn: 'root' })
export class TaskApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/tasks';

  list(workspaceId: number, status?: TaskStatus): Observable<Task[]> {
    let params = new HttpParams().set('workspace_id', workspaceId);
    if (status) params = params.set('status', status);
    return this.http.get<Task[]>(this.base, { params });
  }

  mine(): Observable<Task[]> {
    return this.http.get<Task[]>(`${this.base}/mine`);
  }

  create(payload: TaskPayload): Observable<Task> {
    return this.http.post<Task>(this.base, payload);
  }

  update(id: number, changes: TaskPayload): Observable<Task> {
    return this.http.patch<Task>(`${this.base}/${id}`, changes);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }
}

@Injectable({ providedIn: 'root' })
export class AnalyticsApi {
  private readonly http = inject(HttpClient);

  workspace(id: number): Observable<WorkspaceStats> {
    return this.http.get<WorkspaceStats>(`/api/analytics/workspaces/${id}`);
  }

  me(): Observable<MyStats> {
    return this.http.get<MyStats>('/api/analytics/me');
  }
}
