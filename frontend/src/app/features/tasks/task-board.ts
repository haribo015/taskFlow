import { CdkDragDrop, DragDropModule } from '@angular/cdk/drag-drop';
import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';

import { TaskApi } from '../../core/api';
import {
  Member,
  PRIORITY_LABELS,
  STATUSES,
  STATUS_LABELS,
  Task,
  TaskStatus,
} from '../../core/models';
import { Notifier, isOverdue } from '../../core/notify';
import { TaskDialog, TaskDialogData, TaskDialogResult } from './task-dialog';

@Component({
  selector: 'app-task-board',
  imports: [
    DatePipe,
    DragDropModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
    MatProgressBarModule,
  ],
  templateUrl: './task-board.html',
  styleUrl: './task-board.scss',
})
export class TaskBoard implements OnInit {
  readonly workspaceId = input.required<number>();
  readonly members = input<Member[]>([]);

  private readonly api = inject(TaskApi);
  private readonly dialog = inject(MatDialog);
  private readonly notifier = inject(Notifier);

  protected readonly statusLabels = STATUS_LABELS;
  protected readonly priorityLabels = PRIORITY_LABELS;
  protected readonly isOverdue = isOverdue;
  protected readonly loading = signal(true);
  protected readonly tasks = signal<Task[]>([]);
  protected readonly columns = computed(() =>
    STATUSES.map((status) => ({
      status,
      tasks: this.tasks().filter((task) => task.status === status),
    })),
  );
  private readonly memberNames = computed(
    () => new Map(this.members().map((m) => [m.user_id, m.full_name])),
  );

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.api.list(this.workspaceId()).subscribe({
      next: (tasks) => {
        this.tasks.set(tasks);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.notifier.error(err);
        this.loading.set(false);
      },
    });
  }

  assigneeName(task: Task): string | null {
    return task.assignee_id === null
      ? null
      : (this.memberNames().get(task.assignee_id) ?? `#${task.assignee_id}`);
  }

  drop(event: CdkDragDrop<TaskStatus, TaskStatus, Task>): void {
    const task = event.item.data;
    const status = event.container.data;
    if (task.status === status) return;
    this.replace({ ...task, status }); // optimistic update
    this.api.update(task.id, { status }).subscribe({
      next: (updated) => this.replace(updated),
      error: (err: unknown) => {
        this.replace(task);
        this.notifier.error(err);
      },
    });
  }

  open(task?: Task, status?: TaskStatus): void {
    this.dialog
      .open<TaskDialog, TaskDialogData, TaskDialogResult>(TaskDialog, {
        width: '600px',
        data: { task, status, members: this.members() },
      })
      .afterClosed()
      .subscribe((result) => {
        if (!result) return;
        if (result.action === 'delete' && task) {
          this.api.delete(task.id).subscribe({
            next: () => {
              this.tasks.update((tasks) => tasks.filter((t) => t.id !== task.id));
              this.notifier.success('Tâche supprimée');
            },
            error: (err: unknown) => this.notifier.error(err),
          });
        } else if (result.action === 'save') {
          const request = task
            ? this.api.update(task.id, result.payload)
            : this.api.create({ ...result.payload, workspace_id: this.workspaceId() });
          request.subscribe({
            next: (saved) => {
              if (task) this.replace(saved);
              else this.tasks.update((tasks) => [saved, ...tasks]);
            },
            error: (err: unknown) => this.notifier.error(err),
          });
        }
      });
  }

  private replace(task: Task): void {
    this.tasks.update((tasks) => tasks.map((t) => (t.id === task.id ? task : t)));
  }
}
