import { $unreadFinishedSessionIds } from './session'
import { isHudWindow, isSecondaryWindow } from './windows'

/**
 * DOCK BADGE ("messages waiting") — mirror the sidebar's unread-session count
 * onto the app icon, which macOS renders as the red Dock badge.
 *
 * The number is `$unreadFinishedSessionIds.length`: the SAME atom the sidebar
 * already paints as "finished — unread" green dots. Nothing new is derived
 * here, so the icon and the session list cannot disagree, and acking a session
 * (opening it, "mark all as read") clears the badge through the same path.
 *
 * ONLY the primary chrome window writes it. The badge belongs to one app icon
 * while every window writes the same IPC channel, so a secondary (single-chat
 * pop-out) or HUD window publishing its own sliver of the session lists would
 * clobber the primary's count — the same isolation rule the persisted unread
 * records follow in session-unread.ts.
 *
 * Presentation only: the count never travels back to the backend, and a
 * missing bridge (browser build, tests, a context without the preload) is a
 * silent no-op. The main process owns the platform call — `setBadgeCount` is
 * the Dock badge on macOS, a Unity-launcher badge on Linux, and a no-op on
 * Windows — so the renderer never branches on platform.
 */
// Wiring at module scope, same pattern as session-unread.ts's listeners:
// loaded via session-unread.ts so it is active wherever unread is.
if (!isSecondaryWindow() && !isHudWindow()) {
  const push = (count: number): void => {
    window.hermesDesktop?.setUnreadBadge?.(count)
  }

  push($unreadFinishedSessionIds.get().length)
  $unreadFinishedSessionIds.listen(ids => push(ids.length))
}
