import { signalStore, withMethods, withState, patchState } from '@ngrx/signals';

export interface NotificationItem {
  id: string;
  title: string;
  detail: string;
  level: 'info' | 'success' | 'warning' | 'error';
  createdAt: string;
  read: boolean;
}

type NotificationState = {
  items: NotificationItem[];
  drawerOpen: boolean;
};

const initialState: NotificationState = {
  items: [],
  drawerOpen: false,
};

export const NotificationStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),
  withMethods((store) => ({
    push(notification: Omit<NotificationItem, 'id' | 'createdAt' | 'read'>): void {
      const item: NotificationItem = {
        ...notification,
        id: crypto.randomUUID(),
        createdAt: new Date().toISOString(),
        read: false,
      };

      patchState(store, {
        items: [item, ...store.items()].slice(0, 100),
      });
    },

    toggleDrawer(): void {
      patchState(store, { drawerOpen: !store.drawerOpen() });
    },

    closeDrawer(): void {
      patchState(store, { drawerOpen: false });
    },

    markAllRead(): void {
      patchState(store, {
        items: store.items().map((item) => ({ ...item, read: true })),
      });
    },

    clear(): void {
      patchState(store, { items: [] });
    },
  }))
);
