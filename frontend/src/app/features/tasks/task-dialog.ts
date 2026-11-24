import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import {
  Member,
  PRIORITIES,
  PRIORITY_LABELS,
  STATUSES,
  STATUS_LABELS,
  Task,
  TaskPayload,
  TaskPriority,
  TaskStatus,
} from '../../core/models';
import { fromIsoDate, toIsoDate } from '../../core/notify';

export interface TaskDialogData {
  task?: Task;
  members: Member[];
  status?: TaskStatus;
}

export type TaskDialogResult = { action: 'save'; payload: TaskPayload } | { action: 'delete' };

@Component({
  selector: 'app-task-dialog',
  imports: [
    ReactiveFormsModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDatepickerModule,
    MatButtonModule,
    MatIconModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ data.task ? 'Modifier la tâche' : 'Nouvelle tâche' }}</h2>
    <form [formGroup]="form" (ngSubmit)="save()">
      <mat-dialog-content class="task-dialog-content">
        <div class="task-fields">
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Titre</mat-label>
            <input matInput formControlName="title" maxlength="200" cdkFocusInitial />
          </mat-form-field>
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Description</mat-label>
            <textarea matInput formControlName="description" rows="3"></textarea>
          </mat-form-field>
          <div class="details-grid">
            <mat-form-field appearance="outline">
              <mat-label>Statut</mat-label>
              <mat-select formControlName="status">
                @for (status of statuses; track status) {
                  <mat-option [value]="status">{{ statusLabels[status] }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Priorité</mat-label>
              <mat-select formControlName="priority">
                @for (priority of priorities; track priority) {
                  <mat-option [value]="priority">{{ priorityLabels[priority] }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
          </div>
          <div class="details-grid">
            <mat-form-field appearance="outline">
              <mat-label>Assignée à</mat-label>
              <mat-select formControlName="assigneeId">
                <mat-option [value]="null">Personne</mat-option>
                @for (member of data.members; track member.user_id) {
                  <mat-option [value]="member.user_id">{{ member.full_name }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Échéance</mat-label>
              <input matInput [matDatepicker]="picker" formControlName="dueDate" />
              <mat-datepicker-toggle matIconSuffix [for]="picker" />
              <mat-datepicker #picker />
            </mat-form-field>
          </div>
        </div>
      </mat-dialog-content>
      <mat-dialog-actions class="task-dialog-actions">
        @if (data.task) {
          <button mat-button type="button" class="danger" (click)="remove()">
            <mat-icon>delete</mat-icon> Supprimer
          </button>
        }
        <span class="spacer"></span>
        <button mat-button type="button" mat-dialog-close>Annuler</button>
        <button mat-flat-button type="submit" [disabled]="form.invalid">Enregistrer</button>
      </mat-dialog-actions>
    </form>
  `,
  styles: `
    .task-dialog-content {
      padding-top: 12px;
    }
    .task-fields {
      display: grid;
      gap: 8px 16px;
    }
    .full-width {
      width: 100%;
    }
    .details-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }
    .details-grid mat-form-field {
      min-width: 0;
      width: 100%;
    }
    .task-dialog-actions {
      padding: 12px 24px 20px;
    }
    .spacer {
      flex: 1;
    }
    @media (max-width: 600px) {
      .details-grid {
        grid-template-columns: 1fr;
        gap: 8px;
      }
      .task-dialog-actions {
        padding-inline: 16px;
      }
    }
  `,
})
export class TaskDialog {
  protected readonly data = inject<TaskDialogData>(MAT_DIALOG_DATA);
  private readonly ref = inject<MatDialogRef<TaskDialog, TaskDialogResult>>(MatDialogRef);

  protected readonly statuses = STATUSES;
  protected readonly priorities = PRIORITIES;
  protected readonly statusLabels = STATUS_LABELS;
  protected readonly priorityLabels = PRIORITY_LABELS;

  protected readonly form = inject(FormBuilder).group({
    title: [this.data.task?.title ?? '', [Validators.required, Validators.maxLength(200)]],
    description: [this.data.task?.description ?? ''],
    status: [this.data.task?.status ?? this.data.status ?? ('todo' as TaskStatus)],
    priority: [this.data.task?.priority ?? ('medium' as TaskPriority)],
    assigneeId: [this.data.task?.assignee_id ?? null],
    dueDate: [fromIsoDate(this.data.task?.due_date ?? null)],
  });

  save(): void {
    if (this.form.invalid) return;
    const value = this.form.getRawValue();
    this.ref.close({
      action: 'save',
      payload: {
        title: value.title ?? '',
        description: value.description ?? '',
        status: value.status ?? 'todo',
        priority: value.priority ?? 'medium',
        assignee_id: value.assigneeId,
        due_date: toIsoDate(value.dueDate),
      },
    });
  }

  remove(): void {
    this.ref.close({ action: 'delete' });
  }
}
