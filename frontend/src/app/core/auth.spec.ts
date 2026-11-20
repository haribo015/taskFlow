import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Component } from '@angular/core';
import { provideRouter } from '@angular/router';

import { AuthService, authInterceptor } from './auth';
import { TokenResponse } from './models';

@Component({ template: '' })
class EmptyPage {}

const TOKEN_RESPONSE: TokenResponse = {
  access_token: 'jwt-token',
  token_type: 'bearer',
  expires_in: 3600,
  user: { id: 1, email: 'alice@example.com', full_name: 'Alice', created_at: '2026-01-01' },
};

describe('AuthService', () => {
  let auth: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: 'login', component: EmptyPage }]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('stores the session after login', () => {
    auth.login('alice@example.com', 'secret123').subscribe();
    const request = http.expectOne('/api/auth/login');
    expect(request.request.body).toEqual({ email: 'alice@example.com', password: 'secret123' });
    request.flush(TOKEN_RESPONSE);

    expect(auth.isAuthenticated()).toBe(true);
    expect(auth.user()?.full_name).toBe('Alice');
    expect(localStorage.getItem('taskflow.session')).toContain('jwt-token');
  });

  it('adds the bearer token to API requests', () => {
    auth.login('alice@example.com', 'secret123').subscribe();
    http.expectOne('/api/auth/login').flush(TOKEN_RESPONSE);

    TestBed.inject(HttpClient).get('/api/workspaces').subscribe();
    const request = http.expectOne('/api/workspaces');
    expect(request.request.headers.get('Authorization')).toBe('Bearer jwt-token');
    request.flush([]);
  });

  it('logs out when the API answers 401', () => {
    auth.login('alice@example.com', 'secret123').subscribe();
    http.expectOne('/api/auth/login').flush(TOKEN_RESPONSE);

    TestBed.inject(HttpClient)
      .get('/api/users/me')
      .subscribe({ error: () => undefined });
    http.expectOne('/api/users/me').flush({}, { status: 401, statusText: 'Unauthorized' });

    expect(auth.isAuthenticated()).toBe(false);
    expect(localStorage.getItem('taskflow.session')).toBeNull();
  });
});
