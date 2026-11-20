import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

import { errorMessage } from './auth';

@Injectable({ providedIn: 'root' })
export class Notifier {
  private readonly snackBar = inject(MatSnackBar);

  success(message: string): void {
    this.snackBar.open(message, 'OK', { duration: 3000 });
  }

  error(error: unknown, fallback?: string): void {
    this.snackBar.open(errorMessage(error, fallback), 'Fermer', {
      duration: 5000,
      panelClass: 'snack-error',
    });
  }
}

/** Formats a Date as YYYY-MM-DD in local time (what the API expects for due dates). */
export function toIsoDate(date: Date | null): string | null {
  if (!date) return null;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function fromIsoDate(value: string | null): Date | null {
  if (!value) return null;
  const [y, m, d] = value.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function isOverdue(dueDate: string | null, status: string): boolean {
  return !!dueDate && status !== 'done' && dueDate < (toIsoDate(new Date()) ?? '');
}
