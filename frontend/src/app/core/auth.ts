import { HttpClient, HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Observable, catchError, map, switchMap, throwError } from 'rxjs';

import { TokenResponse, User } from './models';

const STORAGE_KEY = 'taskflow.session';

interface Session {
  token: string;
  user: User;
  expiresAt: number;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly session = signal<Session | null>(this.restore());

  readonly user = computed(() => this.session()?.user ?? null);
  readonly token = computed(() => this.session()?.token ?? null);
  readonly isAuthenticated = computed(() => this.session() !== null);

  login(email: string, password: string): Observable<User> {
    return this.http.post<TokenResponse>('/api/auth/login', { email, password }).pipe(
      map((response) => {
        const session: Session = {
          token: response.access_token,
          user: response.user,
          expiresAt: Date.now() + response.expires_in * 1000,
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
        this.session.set(session);
        return response.user;
      }),
    );
  }

  register(fullName: string, email: string, password: string): Observable<User> {
    return this.http
      .post<User>('/api/auth/register', { full_name: fullName, email, password })
      .pipe(switchMap(() => this.login(email, password)));
  }

  updateProfile(fullName: string): Observable<User> {
    return this.http.patch<User>('/api/users/me', { full_name: fullName }).pipe(
      map((user) => {
        const current = this.session();
        if (current) {
          const updated = { ...current, user };
          localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
          this.session.set(updated);
        }
        return user;
      }),
    );
  }

  logout(): void {
    localStorage.removeItem(STORAGE_KEY);
    this.session.set(null);
    void this.router.navigate(['/login']);
  }

  private restore(): Session | null {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const session = raw ? (JSON.parse(raw) as Session) : null;
      return session && session.expiresAt > Date.now() ? session : null;
    } catch {
      return null;
    }
  }
}

/** Adds the JWT to API calls and logs out when the token is rejected. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const token = auth.token();
  const request =
    token && req.url.startsWith('/api/')
      ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : req;
  return next(request).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401 && token) {
        auth.logout();
      }
      return throwError(() => error);
    }),
  );
};

export const authGuard: CanActivateFn = () =>
  inject(AuthService).isAuthenticated() || inject(Router).createUrlTree(['/login']);

export const guestGuard: CanActivateFn = () =>
  !inject(AuthService).isAuthenticated() || inject(Router).createUrlTree(['/workspaces']);

export function errorMessage(error: unknown, fallback = 'Une erreur est survenue'): string {
  if (error instanceof HttpErrorResponse) {
    const detail = (error.error as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length) return 'Données invalides';
    if (error.status === 0) return 'Serveur injoignable';
  }
  return fallback;
}
