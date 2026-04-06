import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class UiStore {
  readonly sidebarOpen = signal(true);
  readonly activeTheme = signal<'dark' | 'light'>('dark');

  toggleSidebar(): void {
    this.sidebarOpen.update((open) => !open);
  }

  setTheme(theme: 'dark' | 'light'): void {
    this.activeTheme.set(theme);
  }
}
