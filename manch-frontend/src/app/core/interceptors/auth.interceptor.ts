import { HttpInterceptorFn, HttpRequest, HttpHandlerFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

export const authInterceptor: HttpInterceptorFn = (
  req: HttpRequest<unknown>,
  next: HttpHandlerFn,
) => {
  const auth = inject(AuthService);
  const token = auth.accessToken();

  // Skip injecting token for auth endpoints to avoid loops
  const isAuthEndpoint =
    req.url.includes('/auth/login') ||
    req.url.includes('/auth/register') ||
    req.url.includes('/auth/refresh');

  if (!token || isAuthEndpoint) {
    return next(req);
  }

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };

  // Attach active team header if available
  const teamId = auth.activeTeamId();
  if (teamId) {
    headers['X-Team-Id'] = teamId;
  }

  const authedReq = req.clone({ setHeaders: headers });

  return next(authedReq).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401 && !isAuthEndpoint) {
        // Try refreshing
        return auth.refresh().pipe(
          switchMap((tokens) => {
            const retryHeaders: Record<string, string> = { Authorization: `Bearer ${tokens.access_token}` };
            const retryTeamId = auth.activeTeamId();
            if (retryTeamId) {
              retryHeaders['X-Team-Id'] = retryTeamId;
            }
            const retryReq = req.clone({ setHeaders: retryHeaders });
            return next(retryReq);
          }),
          catchError((refreshError: unknown) => {
            auth.logout();
            return throwError(() => refreshError);
          }),
        );
      }
      return throwError(() => error);
    }),
  );
};
