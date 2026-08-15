//! Stores an API key in the OS credential store.
//!
//! Usage: `store-key <provider>`
//!
//! The key is read from a hidden TTY prompt, or — when stdin is not a terminal —
//! from stdin, so the tool also works from an IDE terminal, a here-doc, or a
//! pipe. The key is never taken as a command-line argument: argv is world-readable
//! through `ps` on most systems.

use std::io::{self, BufRead, IsTerminal, Write};

use inkstatute_desktop_lib::engine::credentials::{store_key, Provider};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        eprintln!("Usage: store-key <provider>");
        eprintln!("Providers: deepseek openai anthropic google groq xai zhipu qwen custom");
        eprintln!("Interactive: store-key deepseek        (hidden prompt)");
        eprintln!("Piped:       cat key.txt | store-key deepseek");
        std::process::exit(1);
    }

    let provider = match Provider::from_id(&args[1]) {
        Some(p) => p,
        None => {
            eprintln!("Unknown provider: {}", args[1]);
            eprintln!("Providers: deepseek openai anthropic google groq xai zhipu qwen custom");
            std::process::exit(1);
        }
    };

    // A hidden prompt needs a terminal. Under an IDE console, a here-doc, or a
    // pipe there is no TTY and rpassword fails with "Device not configured";
    // fall back to a plain stdin read so those environments still work.
    let key = if io::stdin().is_terminal() {
        print!("API key for {} (input hidden): ", provider.display_name());
        io::stdout().flush().ok();
        let read = rpassword::read_password();
        println!();
        read.unwrap_or_else(|e| {
            eprintln!("Failed to read key from terminal: {}", e);
            std::process::exit(1);
        })
    } else {
        let mut line = String::new();
        io::stdin().lock().read_line(&mut line).unwrap_or_else(|e| {
            eprintln!("Failed to read key from stdin: {}", e);
            std::process::exit(1);
        });
        line
    };

    // Store the trimmed value: a pasted key often carries a trailing space or
    // newline, and storing it verbatim produces an auth failure whose cause is
    // invisible to the user.
    let key = key.trim();
    if key.is_empty() {
        eprintln!("No key provided");
        std::process::exit(1);
    }

    store_key(provider, key).unwrap_or_else(|e| {
        eprintln!("Failed to store key: {}", e);
        std::process::exit(1);
    });

    // Confirm without echoing the secret: length and a short prefix are enough
    // to tell a truncated paste from a complete one.
    let prefix: String = key.chars().take(3).collect();
    println!(
        "Key stored for {} ({} chars, starts with {}…)",
        provider.display_name(),
        key.chars().count(),
        prefix
    );
}
