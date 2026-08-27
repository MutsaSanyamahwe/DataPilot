// lib/backendReady.js
//
// Handles Render's free-tier cold start: the service spins down after
// ~15 minutes of inactivity, and the next request triggers a ~30-60
// second cold start (confirmed against Render's own docs/community
// reports). A raw fetch() sent straight at a cold service has no
// built-in timeout -- if the browser, network, or any intermediary proxy
// drops that idle connection before the app finishes booting, the fetch
// promise just never resolves. No error, no timeout, nothing for a
// catch block to handle -- the UI is left showing "Uploading..." forever
// even after the backend has actually finished waking up, because the
// original request is already abandoned by then.
//
// The mitigation: poll the lightweight /status endpoint first -- small,
// fast, no request body -- to detect and wait out a cold start cleanly,
// with real user-facing feedback, BEFORE committing to a heavier request
// like a file upload.
//
// IMPORTANT: waitForBackend() is advisory, not a gate. A real deployment
// showed `net::ERR_BLOCKED_BY_CLIENT` on this endpoint -- Chrome's
// specific error for "a browser extension blocked this request," not a
// network or server problem. Some ad-blocker / privacy-extension filter
// lists match generically on telemetry-sounding keywords like "health"
// (this endpoint used to be named /health, renamed to /status partly for
// this reason), and could plausibly still match "status" or something
// else for a different user's extension setup -- there's no keyword
// that's permanently safe from every blocklist. If this probe fails,
// callers should still attempt the real request rather than treating a
// failed probe as proof the backend is unreachable; only the real
// request's own outcome should be trusted for that.

export const API_BASE = "https://datapilot-opfy.onrender.com";

/**
 * Polls API_BASE/status until it responds successfully or `timeoutMs`
 * elapses. Each individual attempt has its own short timeout
 * (`perAttemptMs`) so one hung attempt can't eat the whole budget.
 *
 * Advisory only -- see this file's module docstring. A `false` return
 * means "couldn't confirm the backend is awake," NOT "the backend is
 * definitely down." Callers should still attempt their real request.
 *
 * @param {(status: 'waking') => void} [onWaking] - called once, the
 *   first time a health check fails to respond quickly -- use this to
 *   show "waking up the server..." messaging without flashing it for
 *   the common case where the backend was already warm.
 * @returns {Promise<boolean>} true once healthy, false if it never
 *   became healthy within timeoutMs (which may mean the backend is
 *   genuinely still cold-starting, OR that this specific request is
 *   being blocked client-side while the backend is fine).
 */
export async function waitForBackend(
  onWaking,
  { timeoutMs = 75000, perAttemptMs = 8000, pollIntervalMs = 3000 } = {},
) {
  const deadline = Date.now() + timeoutMs;
  let attempt = 0;

  while (Date.now() < deadline) {
    attempt += 1;
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), perAttemptMs);
      const res = await fetch(`${API_BASE}/status`, {
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (res.ok) return true;
    } catch {
      // Expected while the service is cold-starting or between
      // retries -- fall through and try again below. Also covers
      // the ERR_BLOCKED_BY_CLIENT case: a blocked request throws
      // here just like a network failure would, and this function
      // has no way to distinguish the two -- which is exactly why
      // callers must treat a `false` return as advisory, not fatal.
    }

    if (attempt === 1) {
      onWaking?.("waking");
    }
    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
  }

  return false;
}

/**
 * fetch() with a hard timeout via AbortController -- for the ACTUAL
 * request that follows waitForBackend(). Cold start shouldn't be a
 * factor by this point (whether waitForBackend succeeded OR gave up),
 * but a large file on a slow connection is a real, separate reason a
 * request could hang, and no user-facing request in this app should be
 * able to hang forever with no way to recover.
 */
export async function fetchWithTimeout(url, options = {}, timeoutMs = 60000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}
