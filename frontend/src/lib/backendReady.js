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
// The fix: poll the lightweight /health endpoint first -- small, fast,
// no request body -- to detect and wait out a cold start cleanly, with
// real user-facing feedback, BEFORE committing to a heavier request like
// a file upload. Once /health responds, the real request proceeds
// against an already-warm service.

export const API_BASE = "https://datapilot-opfy.onrender.com";

/**
 * Polls API_BASE/health until it responds successfully or `timeoutMs`
 * elapses. Each individual attempt has its own short timeout
 * (`perAttemptMs`) so one hung attempt can't eat the whole budget.
 *
 * @param {(status: 'waking') => void} [onWaking] - called once, the
 *   first time a health check fails to respond quickly -- use this to
 *   show "waking up the server..." messaging without flashing it for
 *   the common case where the backend was already warm.
 * @returns {Promise<boolean>} true once healthy, false if it never
 *   became healthy within timeoutMs.
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
      const res = await fetch(`${API_BASE}/health`, {
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (res.ok) return true;
    } catch {
      // Expected while cold-starting, or between retries -- a
      // failed/aborted attempt here isn't itself an error worth
      // surfacing, just a reason to try again.
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
 * request that follows a successful waitForBackend() call. Cold start
 * shouldn't be a factor by this point, but a large file on a slow
 * connection is a real, separate reason a request could hang, and no
 * user-facing request in this app should be able to hang forever with
 * no way to recover.
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
