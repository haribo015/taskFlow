import { Component, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-stat-tile',
  imports: [MatIconModule],
  template: `
    <mat-icon class="icon">{{ icon() }}</mat-icon>
    <div>
      <div class="value">{{ value() }}</div>
      <div class="label">{{ label() }}</div>
    </div>
  `,
  host: { '[class.alert]': 'alert()' },
  styles: `
    :host {
      display: flex;
      align-items: center;
      gap: 16px;
      border-radius: 16px;
      background: var(--mat-sys-surface-container);
      padding: 16px;
    }
    :host(.alert) .icon,
    :host(.alert) .value {
      color: var(--mat-sys-error);
    }
    .icon {
      color: var(--mat-sys-primary);
    }
    .value {
      font: var(--mat-sys-headline-small);
    }
    .label {
      color: var(--mat-sys-on-surface-variant);
      font: var(--mat-sys-label-medium);
    }
  `,
})
export class StatTile {
  readonly label = input.required<string>();
  readonly value = input.required<string | number>();
  readonly icon = input('insights');
  readonly alert = input(false);
}
