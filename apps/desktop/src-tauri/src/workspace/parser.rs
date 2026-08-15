use anyhow::{Context, Result};
use encoding_rs::GB18030;
use std::path::Path;

/// Parsed file content normalized to Markdown-ish plain text.
#[derive(Debug, Clone)]
pub struct ParsedDocument {
    pub markdown: String,
    pub source_ext: String,
}

fn read_text_with_encoding(path: &Path) -> Result<String> {
    let bytes =
        std::fs::read(path).with_context(|| format!("read text file: {}", path.display()))?;

    if let Ok(s) = std::str::from_utf8(&bytes) {
        return Ok(s.to_string());
    }

    let (decoded, _, had_errors) = GB18030.decode(&bytes);
    if had_errors {
        log::warn!(
            "GB18030 decode had errors for {}, using lossy UTF-8 fallback",
            path.display()
        );
        Ok(String::from_utf8_lossy(&bytes).into_owned())
    } else {
        Ok(decoded.into_owned())
    }
}

fn parse_text_like(path: &Path, ext: &str) -> Result<ParsedDocument> {
    let markdown = read_text_with_encoding(path)?;
    Ok(ParsedDocument {
        markdown,
        source_ext: ext.to_string(),
    })
}

fn unsupported_file(path: &Path, ext: &str, reason: &str) -> Result<ParsedDocument> {
    let size = std::fs::metadata(path).map(|m| m.len()).unwrap_or(0);
    Ok(ParsedDocument {
        markdown: format!(
            "[{} 文件: {} — {} bytes — {}]",
            ext.to_uppercase(),
            path.display(),
            size,
            reason
        ),
        source_ext: ext.into(),
    })
}

/// Parse a file into unified Markdown text based on extension.
///
/// DOCX and PDF parsing are removed in V5 because native Word export is no longer
/// a product goal and the `docx-rs` / `pdf-extract` dependencies are dropped.
/// Plain text and common source files remain supported.
pub fn parse_file(path: &Path, ext: &str) -> Result<ParsedDocument> {
    let ext = ext.to_lowercase();
    match ext.as_str() {
        "pdf" => unsupported_file(path, &ext, "V5 不解析 PDF 文本"),
        "docx" => unsupported_file(path, &ext, "V5 不解析 DOCX 文本"),
        _ => parse_text_like(path, &ext),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use uuid::Uuid;

    fn temp_dir() -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!("lawyer-ws-parse-{}", Uuid::new_v4()));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn parses_markdown_file() {
        let dir = temp_dir();
        let path = dir.join("doc.md");
        fs::write(&path, "# Title\n\nBody text").unwrap();
        let doc = parse_file(&path, "md").unwrap();
        assert!(doc.markdown.contains("# Title"));
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn parses_json_as_text() {
        let dir = temp_dir();
        let path = dir.join("data.json");
        fs::write(&path, r#"{"key": "索赔"}"#).unwrap();
        let doc = parse_file(&path, "json").unwrap();
        assert!(doc.markdown.contains("索赔"));
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn docx_is_unsupported_marker() {
        let dir = temp_dir();
        let path = dir.join("file.docx");
        fs::write(&path, "fake docx bytes").unwrap();
        let doc = parse_file(&path, "docx").unwrap();
        assert!(doc.markdown.contains("V5 不解析 DOCX 文本"));
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn pdf_is_unsupported_marker() {
        let dir = temp_dir();
        let path = dir.join("file.pdf");
        fs::write(&path, "fake pdf bytes").unwrap();
        let doc = parse_file(&path, "pdf").unwrap();
        assert!(doc.markdown.contains("V5 不解析 PDF 文本"));
        let _ = fs::remove_dir_all(&dir);
    }
}
