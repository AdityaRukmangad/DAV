/**
 * Tiny cross-component event bus (window CustomEvent) so that generating a
 * question or paper anywhere in the app can tell the Analytics dashboard to
 * refresh, even if DAVModule isn't mounted at the moment it happens — the
 * event fires again lazily via a sessionStorage flag the next time it mounts.
 */

const DAV_REFRESH_EVENT = 'dav:data-changed';
const PENDING_REFRESH_KEY = 'dav:pending-refresh';

export function notifyDataChanged() {
  try {
    sessionStorage.setItem(PENDING_REFRESH_KEY, String(Date.now()));
  } catch {
    // sessionStorage unavailable (e.g. private mode) — event dispatch below still works if mounted
  }
  window.dispatchEvent(new CustomEvent(DAV_REFRESH_EVENT));
}

export function onDataChanged(callback: () => void): () => void {
  const handler = () => callback();
  window.addEventListener(DAV_REFRESH_EVENT, handler);
  return () => window.removeEventListener(DAV_REFRESH_EVENT, handler);
}

/** Returns true (and clears the flag) if data changed while this component was unmounted. */
export function consumePendingRefresh(): boolean {
  try {
    const pending = sessionStorage.getItem(PENDING_REFRESH_KEY);
    if (pending) {
      sessionStorage.removeItem(PENDING_REFRESH_KEY);
      return true;
    }
  } catch {
    // ignore
  }
  return false;
}
