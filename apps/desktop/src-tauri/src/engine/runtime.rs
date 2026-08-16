//! Runtime observation bridge: tailer → mapper → Tauri event channel.
//!
//! Starts a background task that tails `session.jsonl` for a given session,
//! maps each DSH event through [`EventMapper`], and emits the resulting
//! `RunEventEnvelope` JSON on the `inkstatute://run-event` Tauri event channel.
//! The task is cancellable via [`ObservationHandle::stop`].

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use serde_json::Value;
use tauri::{AppHandle, Emitter};

use super::mapper::{EventMapper, RunEventEnvelope};
use super::tailer::{tail_session, TailedEvent};

/// The Tauri event channel URI for run events.
pub const RUN_EVENT_CHANNEL: &str = "inkstatute://run-event";

/// Handle to a running observation task. Drop or call `stop` to cancel.
pub struct ObservationHandle {
    stop_flag: Arc<AtomicBool>,
    _join: tokio::task::JoinHandle<()>,
}

impl ObservationHandle {
    /// Stop the observation task. Idempotent.
    pub fn stop(&self) {
        self.stop_flag.store(true, Ordering::SeqCst);
    }
}

impl Drop for ObservationHandle {
    fn drop(&mut self) {
        self.stop_flag.store(true, Ordering::SeqCst);
    }
}

/// Start observing a session: tail its log, map events, emit envelopes on the
/// Tauri event channel.
///
/// `sessions_root` is the engine's sessions directory (from `paths::sessions_root`).
/// `session_id` is the ACP session ID. `run_id` is the app's conversation/run ID
/// used as the envelope `run_id`.
pub fn start_observation(
    app: AppHandle,
    sessions_root: PathBuf,
    session_id: String,
    run_id: String,
) -> ObservationHandle {
    let stop_flag = Arc::new(AtomicBool::new(false));
    let stop_for_task = stop_flag.clone();

    let join = tokio::spawn(observation_loop(
        app,
        sessions_root,
        session_id,
        run_id,
        stop_for_task,
    ));

    ObservationHandle {
        stop_flag,
        _join: join,
    }
}

async fn observation_loop(
    app: AppHandle,
    sessions_root: PathBuf,
    session_id: String,
    run_id: String,
    stop_flag: Arc<AtomicBool>,
) {
    let mut tail = tail_session(
        sessions_root,
        session_id.clone(),
        Duration::from_secs(30),
    );

    let mut mapper = EventMapper::new(run_id);

    loop {
        if stop_flag.load(Ordering::SeqCst) {
            return;
        }

        match tokio::time::timeout(Duration::from_millis(200), tail.events.recv()).await {
            Ok(Some(TailedEvent::Header(h))) => {
                for env in mapper.map_header(&h) {
                    emit(&app, &env);
                }
            }
            Ok(Some(TailedEvent::Event(ev))) => {
                for env in mapper.map(&ev) {
                    emit(&app, &env);
                }
            }
            Ok(Some(TailedEvent::SeqGap { expected, got })) => {
                eprintln!(
                    "[observation] seq gap for session {session_id}: expected {expected}, got {got}"
                );
            }
            Ok(Some(TailedEvent::LogNotFound { session_id: sid })) => {
                eprintln!("[observation] log not found for session {sid}");
                // Emit an error envelope so the UI can show a message.
                let env = RunEventEnvelope {
                    event_id: format!("{}-lognotfound", mapper_run_id(&mapper)),
                    run_id: mapper_run_id(&mapper),
                    event_type: "error".to_string(),
                    occurred_at: iso_now(),
                    seq: 0,
                    payload: Some(serde_json::json!({
                        "error": {
                            "category": "observation",
                            "message": "会话日志未找到",
                        }
                    })),
                    metadata: None,
                };
                emit(&app, &env);
                return;
            }
            Ok(Some(TailedEvent::Closed)) | Ok(None) => {
                return;
            }
            // Timeout tick: no event within 200ms. This is the normal quiet
            // state — loop back and re-check stop_flag. Returning here (the
            // original bug) killed observation in the first quiet 200ms, so
            // the UI never received a single engine event and hung on 回复中.
            Err(_) => {
                continue;
            }
        }
    }
}

fn emit(app: &AppHandle, env: &RunEventEnvelope) {
    eprintln!("[dbg-emit] {} run={} seq={}", env.event_type, env.run_id, env.seq);
    let payload: Value = serde_json::to_value(env)
        .unwrap_or_else(|_| Value::Null);
    let _ = app.emit(RUN_EVENT_CHANNEL, payload);
}

/// Extract the run_id from a mapper (for the LogNotFound envelope).
fn mapper_run_id(_mapper: &EventMapper) -> String {
    // EventMapper doesn't expose run_id; we pass it via the closure instead.
    // This helper is only used in the LogNotFound path before any header arrives.
    "unknown".to_string()
}

fn iso_now() -> String {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    let ms = now.as_millis() as i64;
    let secs = ms / 1000;
    let millis = ms % 1000;
    let dt = format_unix_time(secs);
    format!("{dt}.{millis:03}Z")
}

fn format_unix_time(secs: i64) -> String {
    let days = secs.div_euclid(86400);
    let rem = secs.rem_euclid(86400);
    let hour = rem / 3600;
    let minute = (rem % 3600) / 60;
    let second = rem % 60;
    let (y, m, d) = civil_from_days(days);
    format!("{y:04}-{m:02}-{d:02}T{hour:02}:{minute:02}:{second:02}")
}

fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    (if m <= 2 { y + 1 } else { y }, m, d)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn channel_uri_is_stable() {
        assert_eq!(RUN_EVENT_CHANNEL, "inkstatute://run-event");
    }
}
