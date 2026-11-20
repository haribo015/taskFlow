import { DatePipe, LowerCasePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { RouterLink } from '@angular/router';

import { AnalyticsApi, TaskApi } from '../../core/api';
import {
  MyStats,
  PRIORITY_LABELS,
  STATUSES,
  STATUS_LABELS,
  Task,
  TaskStatus,
} from '../../core/models';
import { Notifier, isOverdue } from '../../core/notify';
import { StatTile } from '../analytics/stat-tile';

@Component({
  selector: 'app-my-tasks-page',
  imports: [
    DatePipe,
    LowerCasePipe,
    RouterLink,
    MatListModule,
    MatIconModule,
    MatSelectModule,
    MatFormFieldModule,
    MatProgressBarModule,
    StatTile,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Mes tâches</h1>
        <p class="muted">Toutes les tâches qui vous sont assignées, tous espaces confondus.</p>
      </div>
    </header>

    @if (stats(); as s) {
      <section class="tiles">
        <app-stat-tile label="Assignées" [value]="s.total_assigned" icon="assignment_ind" />
        <app-stat-tile label="En cours" [value]="s.by_status.in_progress" icon="autorenew" />
        <app-stat-tile
          label="En retard"
          [value]="s.overdue_tasks"
          icon="warning"
          [alert]="s.overdue_tasks > 0"
        />
        <app-stat-tile
          label="Terminées (7 j)"
          [value]="s.completed_last_7_days"
          icon="trending_up"
        />
      </section>
    }

    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    } @else {
      <mat-list class="task-list">
        @for (task of tasks(); track task.id) {
          <mat-list-item>
            <mat-icon matListItemIcon>{{
              task.status === 'done' ? 'task_alt' : 'radio_button_unchecked'
            }}</mat-icon>
            <a matListItemTitle [routerLink]="['/workspaces', task.workspace_id]">{{
              task.title
            }}</a>
            <span matListItemLine>
              Priorité {{ priorityLabels[task.priority] | lowercase }}
              @if (task.due_date) {
                ·
                <span [class.overdue]="isOverdue(task.due_date, task.status)">
                  échéance {{ task.due_date | date: 'longDate' }}
                </span>
              }
            </span>
            <mat-form-field
              matListItemMeta
              appearance="outline"
              subscriptSizing="dynamic"
              class="status-select"
            >
              <mat-select
                [value]="task.status"
                (valueChange)="changeStatus(task, $event)"
                aria-label="Statut"
              >
                @for (status of statuses; track status) {
                  <mat-option [value]="status">{{ statusLabels[status] }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
          </mat-list-item>
        } @empty {
          <div class="empty-state">
            <mat-icon>celebration</mat-icon>
            <p>Aucune tâche assignée. Profitez-en !</p>
          </div>
        }
      </mat-list>
    }
  `,
  styles: `
    .task-list {
      margin-top: 16px;
    }
    .status-select {
      width: 150px;
    }
    .overdue {
      color: var(--mat-sys-error);
    }
    mat-list-item {
      height: auto !important;
      padding-block: 8px;
    }
  `,
})
export class MyTasksPage implements OnInit {
  private readonly taskApi = inject(TaskApi);
  private readonly analyticsApi = inject(AnalyticsApi);
  private readonly notifier = inject(Notifier);

  protected readonly statuses = STATUSES;
  protected readonly statusLabels = STATUS_LABELS;
  protected readonly priorityLabels = PRIORITY_LABELS;
  protected readonly isOverdue = isOverdue;
  protected readonly tasks = signal<Task[]>([]);
  protected readonly stats = signal<MyStats | null>(null);
  protected readonly loading = signal(true);

  ngOnInit(): void {
    this.taskApi.mine().subscribe({
      next: (tasks) => {
        this.tasks.set(tasks);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.notifier.error(err);
        this.loading.set(false);
      },
    });
    this.loadStats();
  }

  changeStatus(task: Task, status: TaskStatus): void {
    this.taskApi.update(task.id, { status }).subscribe({
      next: (updated) => {
        this.tasks.update((tasks) => tasks.map((t) => (t.id === updated.id ? updated : t)));
        // analytics are updated asynchronously through RabbitMQ
        setTimeout(() => this.loadStats(), 500);
      },
      error: (err: unknown) => this.notifier.error(err),
    });
  }

  private loadStats(): void {
    this.analyticsApi.me().subscribe({
      next: (stats) => this.stats.set(stats),
      error: () => this.stats.set(null),
    });
  }
}
