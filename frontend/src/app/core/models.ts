export type Role = 'owner' | 'admin' | 'member';
export type TaskStatus = 'todo' | 'in_progress' | 'done';
export type TaskPriority = 'low' | 'medium' | 'high';

export interface User {
  id: number;
  email: string;
  full_name: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Workspace {
  id: number;
  name: string;
  description: string;
  owner_id: number;
  created_at: string;
  my_role: Role;
  member_count: number;
}

export interface Member {
  user_id: number;
  email: string;
  full_name: string;
  role: Role;
  joined_at: string;
}

export interface Task {
  id: number;
  workspace_id: number;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  assignee_id: number | null;
  due_date: string | null;
  created_by: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface TaskPayload {
  workspace_id?: number;
  title?: string;
  description?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  assignee_id?: number | null;
  due_date?: string | null;
}

export interface Activity {
  event: string;
  actor_id: number | null;
  summary: string;
  occurred_at: string;
}

export interface WorkspaceStats {
  workspace_id: number;
  total_tasks: number;
  by_status: Record<TaskStatus, number>;
  by_priority: Record<TaskPriority, number>;
  completion_rate: number;
  overdue_tasks: number;
  completed_last_7_days: number;
  by_assignee: { assignee_id: number | null; total: number; done: number }[];
  recent_activity: Activity[];
}

export interface MyStats {
  total_assigned: number;
  by_status: Record<TaskStatus, number>;
  overdue_tasks: number;
  completed_last_7_days: number;
  workspaces: number;
}

export const STATUSES: TaskStatus[] = ['todo', 'in_progress', 'done'];
export const PRIORITIES: TaskPriority[] = ['low', 'medium', 'high'];

export const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: 'À faire',
  in_progress: 'En cours',
  done: 'Terminé',
};

export const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: 'Basse',
  medium: 'Moyenne',
  high: 'Haute',
};

export const ROLE_LABELS: Record<Role, string> = {
  owner: 'Propriétaire',
  admin: 'Administrateur',
  member: 'Membre',
};
