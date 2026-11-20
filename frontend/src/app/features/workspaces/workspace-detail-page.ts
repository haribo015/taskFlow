import { Component, OnInit, inject, input, numberAttribute, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Router, RouterLink } from '@angular/router';
import { filter, forkJoin, switchMap } from 'rxjs';

import { WorkspaceApi } from '../../core/api';
import { Member, ROLE_LABELS, Workspace } from '../../core/models';
import { Notifier } from '../../core/notify';
import { StatsPanel } from '../analytics/stats-panel';
import { TaskBoard } from '../tasks/task-board';
import { MembersPanel } from './members-panel';
import { WorkspaceDialog, WorkspaceDialogData } from './workspace-dialog';

@Component({
  selector: 'app-workspace-detail-page',
  imports: [
    RouterLink,
    MatTabsModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatTooltipModule,
    MatProgressBarModule,
    TaskBoard,
    MembersPanel,
    StatsPanel,
  ],
  template: `
    @if (workspace(); as ws) {
      <header class="page-header">
        <div>
          <a mat-button routerLink="/workspaces"><mat-icon>arrow_back</mat-icon> Espaces</a>
          <h1>{{ ws.name }}</h1>
          <p class="muted">{{ ws.description }}</p>
        </div>
        <div class="actions">
          <mat-chip-set
            ><mat-chip>{{ roleLabels[ws.my_role] }}</mat-chip></mat-chip-set
          >
          @if (ws.my_role !== 'member') {
            <button mat-icon-button (click)="edit(ws)" matTooltip="Modifier" aria-label="Modifier">
              <mat-icon>edit</mat-icon>
            </button>
          }
          @if (ws.my_role === 'owner') {
            <button
              mat-icon-button
              (click)="remove(ws)"
              matTooltip="Supprimer"
              aria-label="Supprimer"
            >
              <mat-icon>delete</mat-icon>
            </button>
          }
        </div>
      </header>

      <mat-tab-group mat-stretch-tabs="false" animationDuration="150ms">
        <mat-tab label="Tableau">
          <ng-template matTabContent>
            <app-task-board [workspaceId]="ws.id" [members]="members()" />
          </ng-template>
        </mat-tab>
        <mat-tab [label]="'Membres (' + members().length + ')'">
          <ng-template matTabContent>
            <app-members-panel
              [workspace]="ws"
              [members]="members()"
              (changed)="onMembersChanged($event)"
            />
          </ng-template>
        </mat-tab>
        <mat-tab label="Statistiques">
          <ng-template matTabContent>
            <app-stats-panel [workspaceId]="ws.id" [members]="members()" />
          </ng-template>
        </mat-tab>
      </mat-tab-group>
    } @else {
      <mat-progress-bar mode="indeterminate" />
    }
  `,
  styles: `
    .actions {
      display: flex;
      align-items: center;
      gap: 4px;
    }
  `,
})
export class WorkspaceDetailPage implements OnInit {
  readonly id = input.required({ transform: numberAttribute });

  private readonly api = inject(WorkspaceApi);
  private readonly dialog = inject(MatDialog);
  private readonly notifier = inject(Notifier);
  private readonly router = inject(Router);

  protected readonly roleLabels = ROLE_LABELS;
  protected readonly workspace = signal<Workspace | null>(null);
  protected readonly members = signal<Member[]>([]);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    forkJoin([this.api.get(this.id()), this.api.members(this.id())]).subscribe({
      next: ([workspace, members]) => {
        this.workspace.set(workspace);
        this.members.set(members);
      },
      error: (err: unknown) => {
        this.notifier.error(err, 'Espace introuvable');
        void this.router.navigate(['/workspaces']);
      },
    });
  }

  onMembersChanged({ left }: { left: boolean }): void {
    if (left) void this.router.navigate(['/workspaces']);
    else this.load();
  }

  edit(workspace: Workspace): void {
    this.dialog
      .open<WorkspaceDialog, WorkspaceDialogData, WorkspaceDialogData>(WorkspaceDialog, {
        width: '480px',
        data: { name: workspace.name, description: workspace.description },
      })
      .afterClosed()
      .pipe(
        filter((result): result is WorkspaceDialogData => !!result),
        switchMap((changes) => this.api.update(workspace.id, changes)),
      )
      .subscribe({
        next: (updated) => this.workspace.set(updated),
        error: (err: unknown) => this.notifier.error(err),
      });
  }

  remove(workspace: Workspace): void {
    if (!confirm(`Supprimer « ${workspace.name} » et toutes ses tâches ?`)) return;
    this.api.delete(workspace.id).subscribe({
      next: () => {
        this.notifier.success('Espace supprimé');
        void this.router.navigate(['/workspaces']);
      },
      error: (err: unknown) => this.notifier.error(err),
    });
  }
}
