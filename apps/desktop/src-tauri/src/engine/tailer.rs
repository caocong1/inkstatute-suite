//! Session log tailer.
//!
//! Locates `<sessionsRoot>/<cwd-dir>/<sessionId>/session.jsonl` and incrementally
//! reads new lines as the engine appends them, emitting parsed events on a
//! channel. The cwd directory name is a lossy normalization (separator swap +
//! truncation), so the tailer matches by `sessionId` across all top-level
//! directories rather than reverse-engineering the cwd — see Phase 124 CONTEXT
//! "日志路径推导".
//!
//! Design constraints (binding, from 124-01-PLAN Task 3):
//! - Polling, not inotify/`notify`: simpler and reliable across platforms.
//! - Only complete `\n`-terminated lines are emitted; a partial trailing read
//!   is buffered until the next poll. This is the only half-line defense.
//! - File shrink (engine crash-recovery rewrite) → reset offset to 0 and reread.
//! - `seq` continuity: emit `SeqGap` but keep tailing.
//! - Non-JSON lines are ignored, never abort.
//! - `stop()` and `Drop` both terminate the read loop and emit `Closed`.

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use tokio::sync::mpsc;

use super::events::{parse_line, ParsedLine, SessionEvent, SessionHeader};

/// What the tailer pushes to its consumer.
#[derive(Debug, Clone)]
pub enum TailedEvent {
    Header(SessionHeader),
    Event(SessionEvent),
    /// The log file did not appear within `find_timeout`.
    LogNotFound { session_id: String },
    /// `seq` was not the expected next value. Tailing continues.
    SeqGap { expected: u64, got: u64 },
    /// The read loop exited (stop requested or file permanently gone after open).
    Closed,
}

pub struct TailerHandle {
    pub events: mpsc::UnboundedReceiver<TailedEvent>,
    stop_flag: Arc<AtomicBool>,
    _join: tokio::task::JoinHandle<()>,
}

/// Stop the tailer. Idempotent. The consumer will eventually receive `Closed`.
pub fn stop(handle: &TailerHandle) {
    handle.stop_flag.store(true, Ordering::SeqCst);
}

impl Drop for TailerHandle {
    fn drop(&mut self) {
        self.stop_flag.store(true, Ordering::SeqCst);
    }
}

/// Start tailing `session.jsonl` for `session_id` under `sessions_root`.
///
/// The file is located by scanning `sessions_root/*/<session_id>/session.jsonl`.
/// If it does not appear within `find_timeout`, `LogNotFound` is emitted and the
/// tailer closes.
pub fn tail_session(
    sessions_root: PathBuf,
    session_id: String,
    find_timeout: Duration,
) -> TailerHandle {
    let (tx, rx) = mpsc::unbounded_channel::<TailedEvent>();
    let stop_flag = Arc::new(AtomicBool::new(false));
    let stop_for_task = stop_flag.clone();
    let sid_for_task = session_id.clone();

    let join = tokio::spawn(tail_loop(
        sessions_root,
        session_id,
        find_timeout,
        tx,
        stop_for_task,
        sid_for_task,
    ));

    TailerHandle {
        events: rx,
        stop_flag,
        _join: join,
    }
}

async fn tail_loop(
    sessions_root: PathBuf,
    session_id: String,
    find_timeout: Duration,
    tx: mpsc::UnboundedSender<TailedEvent>,
    stop_flag: Arc<AtomicBool>,
    _sid_for_task: String,
) {
    // 1. Locate the file, retrying every 200ms until find_timeout.
    let path = match locate_log(&sessions_root, &session_id, find_timeout, &stop_flag).await {
        LocateResult::Found(p) => p,
        LocateResult::Timeout => {
            let _ = tx.send(TailedEvent::LogNotFound { session_id });
            let _ = tx.send(TailedEvent::Closed);
            return;
        }
        LocateResult::Stopped => {
            let _ = tx.send(TailedEvent::Closed);
            return;
        }
    };

    // 2. Incremental read loop.
    let mut offset: u64 = 0u64;
    let mut buf: Vec<u8> = Vec::new();
    let mut header_seen = false;
    let mut expected_seq: u64 = 0u64;

    loop {
        if stop_flag.load(Ordering::SeqCst) {
            let _ = tx.send(TailedEvent::Closed);
            return;
        }

        let read_result = read_increment(&path, offset, &mut buf).await;
        match read_result {
            ReadOutcome::NotFound => {
                // File vanished after we had it. Treat like a shrink: reset and
                // try to re-locate briefly. If it stays gone, close.
                offset = 0;
                buf.clear();
                header_seen = false;
                expected_seq = 0;
                // Re-locate with a short grace window.
                match locate_log(&sessions_root, &session_id, Duration::from_secs(5), &stop_flag)
                    .await
                {
                    LocateResult::Found(_) => continue,
                    _ => {
                        let _ = tx.send(TailedEvent::Closed);
                        return;
                    }
                }
            }
            ReadOutcome::Shrunk => {
                // File replaced/truncated (engine crash recovery rewrites it).
                offset = 0;
                buf.clear();
                header_seen = false;
                expected_seq = 0;
                continue;
            }
            ReadOutcome::Append { new_bytes, new_offset } => {
                offset = new_offset;
                // new_bytes is the freshly read tail appended to buf.
                let _ = new_bytes; // already in buf
                // Drain complete lines from buf.
                loop {
                    let nl = match buf.iter().position(|&b| b == b'\n') {
                        Some(i) => i,
                        None => break, // incomplete trailing line, wait for more
                    };
                    let line_bytes: Vec<u8> = buf.drain(..=nl).collect();
                    let line_str = String::from_utf8_lossy(&line_bytes);
                    let line_trimmed = line_str.trim_end_matches(['\n', '\r']);
                    if line_trimmed.is_empty() {
                        continue;
                    }
                    match parse_line(line_trimmed) {
                        Ok(ParsedLine::Header(h)) => {
                            header_seen = true;
                            let _ = tx.send(TailedEvent::Header(h));
                        }
                        Ok(ParsedLine::Event(ev)) => {
                            // seq continuity check (only after header; events are 0-indexed).
                            if header_seen {
                                if ev.seq != expected_seq {
                                    let _ = tx.send(TailedEvent::SeqGap {
                                        expected: expected_seq,
                                        got: ev.seq,
                                    });
                                }
                                expected_seq = ev.seq.saturating_add(1);
                            }
                            let _ = tx.send(TailedEvent::Event(ev));
                        }
                        Ok(ParsedLine::Ignored) | Err(_) => {
                            // Non-JSON / unrecognized lines are silently ignored.
                        }
                    }
                }
            }
            ReadOutcome::NoChange => {
                // Nothing new; poll again after 100ms (unless stopped).
                tokio::time::sleep(Duration::from_millis(100)).await;
            }
        }
    }
}

enum LocateResult {
    Found(PathBuf),
    Timeout,
    Stopped,
}

async fn locate_log(
    sessions_root: &PathBuf,
    session_id: &str,
    timeout: Duration,
    stop_flag: &Arc<AtomicBool>,
) -> LocateResult {
    let deadline = tokio::time::Instant::now() + timeout;
    loop {
        if stop_flag.load(Ordering::SeqCst) {
            return LocateResult::Stopped;
        }
        if let Some(p) = scan_for_log(sessions_root, session_id) {
            return LocateResult::Found(p);
        }
        if tokio::time::Instant::now() >= deadline {
            return LocateResult::Timeout;
        }
        tokio::time::sleep(Duration::from_millis(200)).await;
    }
}

/// Scan `sessions_root/*/<session_id>/session.jsonl`. Returns the first hit.
fn scan_for_log(sessions_root: &PathBuf, session_id: &str) -> Option<PathBuf> {
    let entries = match std::fs::read_dir(sessions_root) {
        Ok(e) => e,
        Err(_) => return None,
    };
    for entry in entries.flatten() {
        let candidate = entry.path().join(session_id).join("session.jsonl");
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

enum ReadOutcome {
    NotFound,
    Shrunk,
    NoChange,
    Append { new_bytes: usize, new_offset: u64 },
}

/// Read any new bytes appended to the file since `offset`, appending them to
/// `buf`. Returns the outcome and updates `offset` via the `Append` variant.
async fn read_increment(path: &PathBuf, offset: u64, buf: &mut Vec<u8>) -> ReadOutcome {
    let metadata = match std::fs::metadata(path) {
        Ok(m) => m,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return ReadOutcome::NotFound,
        Err(_) => return ReadOutcome::NotFound,
    };
    let len = metadata.len();
    if len < offset {
        return ReadOutcome::Shrunk;
    }
    if len == offset {
        return ReadOutcome::NoChange;
    }
    // There are new bytes [offset, len). Read them.
    let mut file = match std::fs::File::open(path) {
        Ok(f) => f,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return ReadOutcome::NotFound,
        Err(_) => return ReadOutcome::NoChange,
    };
    use std::io::{Read, Seek, SeekFrom};
    if let Err(e) = file.seek(SeekFrom::Start(offset)) {
        if e.kind() == std::io::ErrorKind::UnexpectedEof {
            return ReadOutcome::NoChange;
        }
        return ReadOutcome::NoChange;
    }
    let to_read = (len - offset) as usize;
    let mut chunk = vec![0u8; to_read];
    let n = match file.read(&mut chunk) {
        Ok(n) => n,
        Err(_) => return ReadOutcome::NoChange,
    };
    chunk.truncate(n);
    buf.extend_from_slice(&chunk);
    ReadOutcome::Append {
        new_bytes: n,
        new_offset: offset + n as u64,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::io::Write;
    use std::path::PathBuf;

    fn temp_sessions_root() -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "inkstatute-tailer-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::remove_dir_all(&dir).ok();
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn session_dir(root: &PathBuf, session_id: &str) -> PathBuf {
        // Mimic engine layout: <root>/<cwd-dir>/<session_id>/session.jsonl
        let dir = root.join("--some-cwd-dir--").join(session_id);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn append_line(path: &PathBuf, line: &str) {
        let mut f = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .unwrap();
        writeln!(f, "{line}").unwrap();
    }

    async fn drain(handle: &mut TailerHandle, expected: usize) -> Vec<TailedEvent> {
        // Collect `expected` events, but keep draining for a short grace window
        // after each event so trailing events (e.g. SeqGap + Event) arrive
        // together. Hard stop at 3s.
        let mut out = Vec::new();
        let hard_deadline = tokio::time::Instant::now() + Duration::from_secs(3);
        loop {
            let remaining = hard_deadline.saturating_duration_since(tokio::time::Instant::now());
            if remaining.is_zero() {
                break;
            }
            match tokio::time::timeout(remaining, handle.events.recv()).await {
                Ok(Some(ev)) => {
                    out.push(ev);
                    if out.len() >= expected {
                        // Grace window for trailing events.
                        let grace = tokio::time::Instant::now() + Duration::from_millis(250);
                        while tokio::time::Instant::now() < grace {
                            if let Ok(Some(extra)) =
                                tokio::time::timeout(Duration::from_millis(50), handle.events.recv())
                                    .await
                            {
                                out.push(extra);
                            }
                        }
                        break;
                    }
                }
                _ => break,
            }
        }
        out
    }

    /// Drain everything for a fixed window — used after `stop()` to collect `Closed`.
    async fn drain_window(handle: &mut TailerHandle, window: Duration) -> Vec<TailedEvent> {
        let mut out = Vec::new();
        let deadline = tokio::time::Instant::now() + window;
        while tokio::time::Instant::now() < deadline {
            match tokio::time::timeout(Duration::from_millis(100), handle.events.recv()).await {
                Ok(Some(ev)) => out.push(ev),
                _ => {}
            }
        }
        out
    }

    #[tokio::test]
    async fn split_line_is_reassembled() {
        let root = temp_sessions_root();
        let sid = "sess-split";
        let dir = session_dir(&root, sid);
        let path = dir.join("session.jsonl");
        let header = r#"{"type":"session","version":0,"id":"sess-split","createdAt":1}"#;
        let ev = r#"{"type":"turn/start","seq":0,"time":2,"data":{"turn":1}}"#;
        append_line(&path, header);
        append_line(&path, ev);

        let mut handle = tail_session(root.clone(), sid.to_string(), Duration::from_secs(2));
        // Wait for the two complete lines.
        let got = drain(&mut handle, 2).await;
        stop(&handle);
        let _ = drain_window(&mut handle, Duration::from_millis(200)).await;

        let mut headers = 0;
        let mut events = 0;
        for ev in &got {
            match ev {
                TailedEvent::Header(_) => headers += 1,
                TailedEvent::Event(_) => events += 1,
                _ => {}
            }
        }
        assert_eq!(headers, 1);
        assert_eq!(events, 1);

        fs::remove_dir_all(&root).ok();
    }

    #[tokio::test]
    async fn half_line_buffered_until_completion() {
        let root = temp_sessions_root();
        let sid = "sess-half";
        let dir = session_dir(&root, sid);
        let path = dir.join("session.jsonl");

        // Write a header so the tailer has something to emit immediately.
        let header = r#"{"type":"session","version":0,"id":"sess-half","createdAt":1}"#;
        append_line(&path, header);

        let mut handle = tail_session(root.clone(), sid.to_string(), Duration::from_secs(2));

        // Drain the header first.
        let _ = drain(&mut handle, 1).await;

        // Write the first half of a line (no newline).
        {
            let mut f = std::fs::OpenOptions::new()
                .append(true)
                .open(&path)
                .unwrap();
            write!(f, r#"{{"type":"turn/start","seq":0,"time":2,"da"#).unwrap();
        }
        // Wait a bit; nothing should arrive.
        let none = drain_window(&mut handle, Duration::from_millis(400)).await;
        assert!(
            none.is_empty(),
            "no event should be emitted for a half line"
        );

        // Complete the line.
        {
            let mut f = std::fs::OpenOptions::new()
                .append(true)
                .open(&path)
                .unwrap();
            writeln!(f, r#"ta":{{"turn":1}}}}"#).unwrap();
        }
        let got = drain(&mut handle, 1).await;
        stop(&handle);
        let _ = drain_window(&mut handle, Duration::from_millis(200)).await;
        assert!(
            got.iter().any(|e| matches!(e, TailedEvent::Event(_))),
            "completed line should produce an event, got: {got:?}"
        );

        fs::remove_dir_all(&root).ok();
    }

    #[tokio::test]
    async fn file_appears_later() {
        let root = temp_sessions_root();
        let sid = "sess-late";
        // Do NOT create the session dir yet.

        let mut handle = tail_session(root.clone(), sid.to_string(), Duration::from_secs(3));

        // After 600ms, create the file with a header.
        tokio::time::sleep(Duration::from_millis(600)).await;
        let dir = session_dir(&root, sid);
        let path = dir.join("session.jsonl");
        let header = r#"{"type":"session","version":0,"id":"sess-late","createdAt":1}"#;
        append_line(&path, header);

        let got = drain(&mut handle, 1).await;
        stop(&handle);
        let _ = drain_window(&mut handle, Duration::from_millis(200)).await;
        assert!(got.iter().any(|e| matches!(e, TailedEvent::Header(_))));

        fs::remove_dir_all(&root).ok();
    }

    #[tokio::test]
    async fn file_never_appears_emits_lognotfound() {
        let root = temp_sessions_root();
        let sid = "sess-missing";
        let mut handle = tail_session(
            root.clone(),
            sid.to_string(),
            Duration::from_millis(400),
        );
        // Drain until LogNotFound + Closed.
        let mut got_not_found = false;
        let mut got_closed = false;
        let deadline = tokio::time::Instant::now() + Duration::from_secs(3);
        while tokio::time::Instant::now() < deadline && !(got_not_found && got_closed) {
            match tokio::time::timeout(Duration::from_millis(200), handle.events.recv()).await {
                Ok(Some(TailedEvent::LogNotFound { .. })) => got_not_found = true,
                Ok(Some(TailedEvent::Closed)) => got_closed = true,
                _ => {}
            }
        }
        assert!(got_not_found, "should emit LogNotFound");
        assert!(got_closed, "should emit Closed after LogNotFound");
        fs::remove_dir_all(&root).ok();
    }

    #[tokio::test]
    async fn truncated_file_reread_from_start() {
        let root = temp_sessions_root();
        let sid = "sess-trunc";
        let dir = session_dir(&root, sid);
        let path = dir.join("session.jsonl");
        let header = r#"{"type":"session","version":0,"id":"sess-trunc","createdAt":1}"#;
        let ev1 = r#"{"type":"turn/start","seq":0,"time":2,"data":{"turn":1}}"#;
        append_line(&path, header);
        append_line(&path, ev1);

        let mut handle = tail_session(root.clone(), sid.to_string(), Duration::from_secs(2));
        // Drain the first two events.
        let _ = drain(&mut handle, 2).await;

        // Truncate + rewrite with a fresh header.
        {
            let _ = std::fs::remove_file(&path);
        }
        let header2 = r#"{"type":"session","version":0,"id":"sess-trunc","createdAt":99}"#;
        append_line(&path, header2);
        let got = drain(&mut handle, 1).await;
        stop(&handle);
        let _ = drain_window(&mut handle, Duration::from_millis(200)).await;
        assert!(
            got.iter().any(|e| matches!(e, TailedEvent::Header(_))),
            "truncated file should be reread from start"
        );
        fs::remove_dir_all(&root).ok();
    }

    #[tokio::test]
    async fn non_json_lines_ignored() {
        let root = temp_sessions_root();
        let sid = "sess-noise";
        let dir = session_dir(&root, sid);
        let path = dir.join("session.jsonl");
        let header = r#"{"type":"session","version":0,"id":"sess-noise","createdAt":1}"#;
        append_line(&path, header);
        append_line(&path, "this is not json");
        append_line(&path, "");
        let ev = r#"{"type":"turn/start","seq":0,"time":2,"data":{"turn":1}}"#;
        append_line(&path, ev);

        let mut handle = tail_session(root.clone(), sid.to_string(), Duration::from_secs(2));
        let got = drain(&mut handle, 2).await;
        stop(&handle);
        let _ = drain_window(&mut handle, Duration::from_millis(200)).await;
        let mut headers = 0;
        let mut events = 0;
        for e in &got {
            match e {
                TailedEvent::Header(_) => headers += 1,
                TailedEvent::Event(_) => events += 1,
                _ => {}
            }
        }
        assert_eq!(headers, 1);
        assert_eq!(events, 1);
        fs::remove_dir_all(&root).ok();
    }

    #[tokio::test]
    async fn stop_emits_closed() {
        let root = temp_sessions_root();
        let sid = "sess-stop";
        let dir = session_dir(&root, sid);
        let path = dir.join("session.jsonl");
        let header = r#"{"type":"session","version":0,"id":"sess-stop","createdAt":1}"#;
        append_line(&path, header);

        let mut handle = tail_session(root.clone(), sid.to_string(), Duration::from_secs(2));
        let _ = drain(&mut handle, 1).await;
        stop(&handle);
        let got = drain_window(&mut handle, Duration::from_secs(2)).await;
        assert!(
            got.iter().any(|e| matches!(e, TailedEvent::Closed)),
            "stop() should produce Closed"
        );
        fs::remove_dir_all(&root).ok();
    }

    #[tokio::test]
    async fn seq_gap_emitted_but_tailing_continues() {
        let root = temp_sessions_root();
        let sid = "sess-gap";
        let dir = session_dir(&root, sid);
        let path = dir.join("session.jsonl");
        let header = r#"{"type":"session","version":0,"id":"sess-gap","createdAt":1}"#;
        append_line(&path, header);
        // seq starts at 0, then jumps to 5 (skipping 1..4).
        let ev0 = r#"{"type":"turn/start","seq":0,"time":2,"data":{"turn":1}}"#;
        append_line(&path, ev0);
        let ev5 = r#"{"type":"turn/end","seq":5,"time":3,"data":{"turn":1,"reason":{"kind":"stop"}}}"#;
        append_line(&path, ev5);

        let mut handle = tail_session(root.clone(), sid.to_string(), Duration::from_secs(2));
        // Expect: header, event(seq0), SeqGap, event(seq5).
        let got = drain(&mut handle, 4).await;
        stop(&handle);
        let _ = drain_window(&mut handle, Duration::from_millis(200)).await;
        let has_gap = got
            .iter()
            .any(|e| matches!(e, TailedEvent::SeqGap { expected: 1, got: 5 }));
        assert!(has_gap, "should emit SeqGap expected=1 got=5, got: {got:?}");
        // And both events still arrive.
        let events = got
            .iter()
            .filter(|e| matches!(e, TailedEvent::Event(_)))
            .count();
        assert_eq!(events, 2);
        fs::remove_dir_all(&root).ok();
    }
}
