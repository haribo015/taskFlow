import { DatePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { Router, RouterLink } from '@angular/router';
import { filter, switchMap } from 'rxjs';

import { WorkspaceApi } from '../../core/api';
import { ROLE_LABELS, Workspace } from '../../core/models';
import { Notifier } from '../../core/notify';
import { WorkspaceDialog, WorkspaceDialogData } from './workspace-dialog';

@Component({
  selector: 'app-workspaces-page',
  imports: [
    DatePipe,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Espaces de travail</h1>
        <p class="muted">Regroupez vos projets et collaborez avec votre équipe.</p>
      </div>
      <button mat-flat-button (click)="create()"><mat-icon>add</mat-icon> Nouvel espace</button>
    </header>

    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    } @else {
      <section class="card-grid">
        @for (workspace of workspaces(); track workspace.id) {
          <mat-card
            class="clickable"
            appearance="outlined"
            [routerLink]="['/workspaces', workspace.id]"
          >
            <mat-card-header>
              <mat-icon mat-card-avatar>folder_shared</mat-icon>
              <mat-card-title>{{ workspace.name }}</mat-card-title>
              <mat-card-subtitle
                >Créé le {{ workspace.created_at | date: 'longDate' }}</mat-card-subtitle
              >
            </mat-card-header>
            <mat-card-content>
              <p class="description">{{ workspace.description || 'Aucune description' }}</p>
            </mat-card-content>
            <mat-card-footer class="card-footer">
              <mat-chip-set>
                <mat-chip>{{ roleLabels[workspace.my_role] }}</mat-chip>
                <mat-chip>
                  <mat-icon matChipAvatar>group</mat-icon>{{ workspace.member_count }}
                </mat-chip>
              </mat-chip-set>
            </mat-card-footer>
          </mat-card>
        } @empty {
          <div class="empty-state">
            <mat-icon>inbox</mat-icon>
            <p>Aucun espace pour le moment. Créez-en un pour commencer !</p>
          </div>
        }
      </section>
    }
  `,
  styles: `
    .description {
      min-height: 40px;
      color: var(--mat-sys-on-surface-variant);
    }
    .card-footer {
      padding: 0 16px 16px;
    }
  `,
})
export class WorkspacesPage implements OnInit {
  private readonly api = inject(WorkspaceApi);
  private readonly dialog = inject(MatDialog);
  private readonly notifier = inject(Notifier);
  private readonly router = inject(Router);

  protected readonly roleLabels = ROLE_LABELS;
  protected readonly workspaces = signal<Workspace[]>([]);
  protected readonly loading = signal(true);

  ngOnInit(): void {
    this.api.list().subscribe({
      next: (workspaces) => {
        this.workspaces.set(workspaces);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.notifier.error(err);
        this.loading.set(false);
      },
    });
  }

  create(): void {
    this.dialog
      .open<WorkspaceDialog, null, WorkspaceDialogData>(WorkspaceDialog, { width: '480px' })
      .afterClosed()
      .pipe(
        filter((result): result is WorkspaceDialogData => !!result),
        switchMap(({ name, description }) => this.api.create(name, description)),
      )
      .subscribe({
        next: (workspace) => {
          this.notifier.success('Espace créé');
          void this.router.navigate(['/workspaces', workspace.id]);
        },
        error: (err: unknown) => this.notifier.error(err),
      });
  }
}
