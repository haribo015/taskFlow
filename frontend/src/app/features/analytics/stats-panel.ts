import { DatePipe, DecimalPipe, PercentPipe } from '@angular/common';
import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { AnalyticsApi } from '../../core/api';
import { Member, STATUSES, STATUS_LABELS, WorkspaceStats } from '../../core/models';
import { Notifier } from '../../core/notify';
import { StatTile } from './stat-tile';

@Component({
  selector: 'app-stats-panel',
  imports: [
    DatePipe,
    PercentPipe,
    DecimalPipe,
    MatProgressBarModule,
    MatListModule,
    MatIconModule,
    StatTile,
  ],
  template: `
    @if (stats(); as s) {
      <section class="tiles">
        <app-stat-tile label="Tâches" [value]="s.total_tasks" icon="assignment" />
        <app-stat-tile
          label="Terminées"
          [value]="(s.completion_rate | percent) ?? '0 %'"
          icon="done_all"
        />
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

      <div class="columns">
        <section class="panel">
          <h3>Répartition par statut</h3>
          @for (status of statuses; track status) {
            <div class="bar-row">
              <span class="bar-label">{{ statusLabels[status] }}</span>
              <mat-progress-bar
                mode="determinate"
                [value]="ratio(s.by_status[status], s.total_tasks)"
              />
              <span class="bar-value">{{ s.by_status[status] }}</span>
            </div>
          }

          <h3>Charge par personne</h3>
          @for (row of s.by_assignee; track row.assignee_id) {
            <div class="bar-row">
              <span class="bar-label">{{ name(row.assignee_id) }}</span>
              <mat-progress-bar mode="determinate" [value]="ratio(row.done, row.total)" />
              <span class="bar-value">{{ row.done }}/{{ row.total }}</span>
            </div>
          } @empty {
            <p class="muted">Aucune tâche</p>
          }
        </section>

        <section class="panel">
          <h3>Activité récente</h3>
          <mat-list>
            @for (activity of s.recent_activity; track $index) {
              <mat-list-item>
                <mat-icon matListItemIcon>history</mat-icon>
                <span matListItemTitle>{{ activity.summary }}</span>
                <span matListItemLine>
                  {{ name(activity.actor_id) }} · {{ activity.occurred_at | date: 'short' }}
                </span>
              </mat-list-item>
            } @empty {
              <p class="muted">Pas encore d'activité</p>
            }
          </mat-list>
        </section>
      </div>
      <p class="muted hint">
        Statistiques calculées par AnalyticsService à partir des événements RabbitMQ ({{
          s.total_tasks | number
        }}
        tâche(s) projetée(s)).
      </p>
    } @else {
      <mat-progress-bar mode="indeterminate" />
    }
  `,
  styles: `
    .columns {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      margin-top: 16px;
    }
    .panel {
      border-radius: 16px;
      background: var(--mat-sys-surface-container-low);
      padding: 8px 16px 16px;
    }
    .bar-row {
      display: grid;
      grid-template-columns: 120px 1fr 48px;
      align-items: center;
      gap: 12px;
      margin: 8px 0;
    }
    .bar-label {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .bar-value {
      text-align: right;
      font: var(--mat-sys-label-large);
    }
    .hint {
      margin-top: 16px;
      font: var(--mat-sys-body-small);
    }
  `,
})
export class StatsPanel implements OnInit {
  readonly workspaceId = input.required<number>();
  readonly members = input<Member[]>([]);

  private readonly api = inject(AnalyticsApi);
  private readonly notifier = inject(Notifier);

  protected readonly statuses = STATUSES;
  protected readonly statusLabels = STATUS_LABELS;
  protected readonly stats = signal<WorkspaceStats | null>(null);
  private readonly names = computed(
    () => new Map(this.members().map((m) => [m.user_id, m.full_name])),
  );

  ngOnInit(): void {
    this.api.workspace(this.workspaceId()).subscribe({
      next: (stats) => this.stats.set(stats),
      error: (err: unknown) => this.notifier.error(err),
    });
  }

  ratio(part: number, total: number): number {
    return total ? (part / total) * 100 : 0;
  }

  name(userId: number | null): string {
    if (userId === null) return 'Non assignée';
    return this.names().get(userId) ?? `Utilisateur #${userId}`;
  }
}
