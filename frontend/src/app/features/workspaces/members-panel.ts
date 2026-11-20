import { Component, computed, inject, input, output, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatListModule } from '@angular/material/list';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';

import { WorkspaceApi } from '../../core/api';
import { AuthService } from '../../core/auth';
import { Member, ROLE_LABELS, Workspace } from '../../core/models';
import { Notifier } from '../../core/notify';

@Component({
  selector: 'app-members-panel',
  imports: [
    ReactiveFormsModule,
    MatListModule,
    MatIconModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatTooltipModule,
  ],
  template: `
    @if (canManage()) {
      <form class="invite" [formGroup]="form" (ngSubmit)="invite()">
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Email du membre</mat-label>
          <input matInput type="email" formControlName="email" />
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic" class="role">
          <mat-label>Rôle</mat-label>
          <mat-select formControlName="role">
            <mat-option value="member">Membre</mat-option>
            <mat-option value="admin">Administrateur</mat-option>
          </mat-select>
        </mat-form-field>
        <button mat-flat-button type="submit" [disabled]="form.invalid || busy()">
          <mat-icon>person_add</mat-icon> Ajouter
        </button>
      </form>
    }

    <mat-list>
      @for (member of members(); track member.user_id) {
        <mat-list-item>
          <mat-icon matListItemIcon>{{ member.role === 'owner' ? 'star' : 'person' }}</mat-icon>
          <span matListItemTitle>{{ member.full_name }}</span>
          <span matListItemLine>{{ member.email }} · {{ roleLabels[member.role] }}</span>
          @if (member.role !== 'owner' && (canManage() || member.user_id === me())) {
            <button
              mat-icon-button
              matListItemMeta
              (click)="remove(member)"
              [matTooltip]="member.user_id === me() ? 'Quitter' : 'Retirer'"
              [attr.aria-label]="'Retirer ' + member.full_name"
            >
              <mat-icon>{{ member.user_id === me() ? 'logout' : 'person_remove' }}</mat-icon>
            </button>
          }
        </mat-list-item>
      }
    </mat-list>
  `,
  styles: `
    .invite {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
      margin: 16px 0;
      mat-form-field {
        flex: 1;
        min-width: 220px;
      }
      .role {
        flex: 0 0 180px;
        min-width: 0;
      }
    }
  `,
})
export class MembersPanel {
  readonly workspace = input.required<Workspace>();
  readonly members = input<Member[]>([]);
  readonly changed = output<{ left: boolean }>();

  private readonly api = inject(WorkspaceApi);
  private readonly notifier = inject(Notifier);
  private readonly auth = inject(AuthService);

  protected readonly roleLabels = ROLE_LABELS;
  protected readonly busy = signal(false);
  protected readonly me = computed(() => this.auth.user()?.id);
  protected readonly canManage = computed(() => this.workspace().my_role !== 'member');
  protected readonly form = inject(FormBuilder).nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    role: ['member' as 'member' | 'admin'],
  });

  invite(): void {
    const { email, role } = this.form.getRawValue();
    this.busy.set(true);
    this.api.addMember(this.workspace().id, email, role).subscribe({
      next: (member) => {
        this.notifier.success(`${member.full_name} a été ajouté`);
        this.form.reset({ email: '', role: 'member' });
        this.busy.set(false);
        this.changed.emit({ left: false });
      },
      error: (err: unknown) => {
        this.notifier.error(err);
        this.busy.set(false);
      },
    });
  }

  remove(member: Member): void {
    const leaving = member.user_id === this.me();
    const question = leaving
      ? 'Quitter cet espace de travail ?'
      : `Retirer ${member.full_name} de l'espace ?`;
    if (!confirm(question)) return;
    this.api.removeMember(this.workspace().id, member.user_id).subscribe({
      next: () => this.changed.emit({ left: leaving }),
      error: (err: unknown) => this.notifier.error(err),
    });
  }
}
