"""Safe way to call Gemini.

Problem: when Gemini is overloaded (error 503) Google's own library keeps retrying quietly,
so the agent can look frozen for minutes or crash with a long traceback.

This wrapper gives every Gemini call:
  * a hard time limit per attempt (default 40 s),
  * a few retries with a short, growing pause (default 3 attempts),
  * retries ONLY for temporary problems (503, timeouts, connection errors),
  * a clear GeminiUnavailable error if Gemini still does not answer.
Quota errors (429) and real mistakes (wrong model name, bad key) are NOT retried.
They are passed straight back so the caller handles them as before.

Settings (optional, environment variables): GEMINI_ATTEMPTS, GEMINI_DEADLINE_S, GEMINI_WAIT_S
"""
import os
import threading
import time

class GeminiUnavailable(Exception):
    """Gemini could not be reached after every attempt."""

_NOT_RETRYABLE = ("429", "rate limit", "too_many_requests",
                  "error code: 400", "error code: 401", "error code: 403", "error code: 404")
_RETRYABLE = ("503", "502", "504", "500", "service_unavailable", "high demand", "overloaded",
              "unavailable", "timed out", "timeout", "connection")


def _is_retryable(error):
    text = str(error).lower()
    if any(k in text for k in _NOT_RETRYABLE):
        return False
    return any(k in text for k in _RETRYABLE)


def _setting(name, default, cast):
    try:
        return cast(os.getenv(name, default))
    except ValueError:
        return default


def _run_with_deadline(fn, deadline_s):
    """Run fn() in a background thread; give up waiting after deadline_s seconds."""
    box = {}

    def worker():
        try:
            box["value"] = fn()
        except BaseException as error:  # hand any error back to the caller
            box["error"] = error

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(deadline_s)
    if thread.is_alive():
        raise TimeoutError(f"no answer within {deadline_s:g} s")
    if "error" in box:
        raise box["error"]
    return box["value"]


def create_interaction(client, **kwargs):
    """Same as client.interactions.create(**kwargs), but with time limit and retries."""
    attempts = _setting("GEMINI_ATTEMPTS", 3, int)
    deadline = _setting("GEMINI_DEADLINE_S", 40.0, float)
    wait = _setting("GEMINI_WAIT_S", 4.0, float)
    reason = "unknown"

    for attempt in range(1, attempts + 1):
        try:
            return _run_with_deadline(lambda: client.interactions.create(**kwargs), deadline)
        except TimeoutError:
            reason = f"no answer within {deadline:g} s"
        except Exception as error:
            if not _is_retryable(error):
                raise  # quota, wrong model, bad key...: not our job to hide these
            reason = (str(error).splitlines() or ["unknown error"])[0][:120]

        if attempt < attempts:
            pause = wait * attempt
            print(f"[RETRY] Gemini attempt {attempt}/{attempts} failed ({reason}). Waiting {pause:g} s...")
            time.sleep(pause)

    raise GeminiUnavailable(f"Gemini did not respond after {attempts} attempts ({reason}).")
