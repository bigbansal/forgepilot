import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ApiBaseService {
  readonly baseUrl = 'http://localhost:8080/api/v1';
}
