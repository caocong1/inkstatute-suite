pub struct ReplayTurn {
    pub role: ReplayRole,
    pub text: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReplayRole {
    User,
    Assistant,
}

pub struct ReplayConfig {
    /// Maximum number of turns (one user + one assistant) to replay.
    pub max_turns: usize,
    /// Soft character budget for the seed prefix.
    pub max_chars: usize,
}

impl Default for ReplayConfig {
    fn default() -> Self {
        Self {
            max_turns: 20,
            max_chars: 200_000,
        }
    }
}

/// Builds a replay seed prefix from the conversation history.
/// Returns `None` when there is no history to replay.
pub fn build_seed_prefix(turns: &[ReplayTurn], cfg: &ReplayConfig) -> Option<String> {
    if turns.is_empty() {
        return None;
    }

    // 1. Apply max_turns from the most recent end.
    let mut start = 0usize;
    if turns.len() > cfg.max_turns {
        start = turns.len() - cfg.max_turns;
    }

    let mut skipped_turns = start;
    loop {
        let seed = render_seed(&turns[start..], skipped_turns);
        if seed.len() <= cfg.max_chars || start + 1 >= turns.len() {
            return Some(seed);
        }
        // 2. Still over budget: drop the oldest remaining turn while keeping the newest.
        skipped_turns += 1;
        start += 1;
    }
}

fn render_seed(turns: &[ReplayTurn], skipped: usize) -> String {
    let mut parts = Vec::new();
    parts.push(
        "[以下是本次对话此前的往来记录，供你恢复上下文。请勿重复回答其中已回答的问题，也不要把这段记录当作用户的新指令。]"
            .to_string(),
    );
    if skipped > 0 {
        parts.push(format!("[更早的 {} 轮记录已省略]", skipped));
    }

    for (i, turn) in turns.iter().enumerate() {
        let role_label = match turn.role {
            ReplayRole::User => "用户",
            ReplayRole::Assistant => "助手",
        };
        // The displayed round number is relative to the replayed slice.
        parts.push(format!("【第 {} 轮 · {}】{}", i + 1, role_label, turn.text));
    }

    parts.push("[记录结束。以下是用户的新问题。]".to_string());
    parts.join("\n\n")
}

/// Composes the prompt text sent to the engine. If `seed` is `None`, only the
/// user input is returned, ensuring no prefix pollution on new conversations.
pub fn compose_seeded_prompt(seed: Option<&str>, user_input: &str) -> String {
    match seed {
        Some(prefix) => format!("{}\n\n{}", prefix, user_input),
        None => user_input.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_history_no_seed() {
        assert!(build_seed_prefix(&[], &ReplayConfig::default()).is_none());
    }

    #[test]
    fn three_turns_format() {
        let turns = vec![
            ReplayTurn {
                role: ReplayRole::User,
                text: "第一条".to_string(),
            },
            ReplayTurn {
                role: ReplayRole::Assistant,
                text: "回答一".to_string(),
            },
            ReplayTurn {
                role: ReplayRole::User,
                text: "第二条".to_string(),
            },
        ];
        let seed = build_seed_prefix(&turns, &ReplayConfig::default()).unwrap();
        assert!(seed.contains("【第 1 轮 · 用户】第一条"));
        assert!(seed.contains("[记录结束"));
    }

    #[test]
    fn max_turns_truncates() {
        let mut turns = Vec::new();
        for i in 0..25 {
            turns.push(ReplayTurn {
                role: if i % 2 == 0 {
                    ReplayRole::User
                } else {
                    ReplayRole::Assistant
                },
                text: format!("turn {}", i),
            });
        }
        let mut cfg = ReplayConfig::default();
        cfg.max_turns = 20;
        let seed = build_seed_prefix(&turns, &cfg).unwrap();
        assert!(seed.contains("[更早的 5 轮记录已省略]"));
        assert!(!seed.contains("turn 0"));
        assert!(!seed.contains("turn 4"));
        assert!(seed.contains("turn 24"));
        // The first included round is renumbered to 1.
        assert!(seed.contains("【第 1 轮"));
    }

    #[test]
    fn max_chars_keeps_most_recent() {
        let mut turns = Vec::new();
        for i in 0..10 {
            turns.push(ReplayTurn {
                role: if i % 2 == 0 {
                    ReplayRole::User
                } else {
                    ReplayRole::Assistant
                },
                text: "x".repeat(100),
            });
        }
        let mut cfg = ReplayConfig::default();
        cfg.max_chars = 250;
        let seed = build_seed_prefix(&turns, &cfg).unwrap();
        // Only the most recent turn fits under this tight budget.
        assert!(seed.contains("【第 1 轮"));
        assert!(!seed.contains("【第 2 轮"));
        assert!(seed.contains("x".repeat(100).as_str()));
    }

    #[test]
    fn compose_no_seed_is_clean() {
        let out = compose_seeded_prompt(None, "问题");
        assert_eq!(out, "问题");
    }

    #[test]
    fn compose_with_seed_appends_user() {
        let out = compose_seeded_prompt(Some("prefix"), "问题");
        assert!(out.starts_with("prefix"));
        assert!(out.ends_with("问题"));
    }
}
