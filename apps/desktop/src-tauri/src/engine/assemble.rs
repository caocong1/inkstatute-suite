use std::fs;
use std::io::Cursor;
use std::path::{Component, Path, PathBuf};

use flate2::read::GzDecoder;
use futures::stream::{self, StreamExt, TryStreamExt};
use reqwest::Client;
use tar::Archive;

use super::lock::{EngineLock, LockedPackage};
use super::EngineError;

#[derive(Clone)]
pub struct AssembleOptions {
    pub registry: String,
    pub registry_fallback: String,
    pub concurrency: usize,
}

impl Default for AssembleOptions {
    fn default() -> Self {
        Self {
            registry: "https://registry.npmmirror.com".to_string(),
            registry_fallback: "https://registry.npmjs.org".to_string(),
            concurrency: 8,
        }
    }
}

#[derive(Debug, Clone)]
pub struct AssembleProgress {
    pub total: usize,
    pub done: usize,
    pub current: String,
}

/// Assemble the engine described by `lock` into `dest`.
///
/// The destination must not exist or must be empty. The assembler uses a sibling
/// `.partial` directory and renames it into place only after all packages,
/// integrity checks, and the entrypoint assertion succeed.
pub async fn assemble<F>(
    lock: &EngineLock,
    cordis_yml: &str,
    dest: &Path,
    opts: &AssembleOptions,
    on_progress: F,
) -> Result<(), EngineError>
where
    F: Fn(AssembleProgress) + Clone + Send + Sync + 'static,
{
    if dest.exists() && dest.read_dir()?.next().is_some() {
        return Err(EngineError::DestNotEmpty(dest.display().to_string()));
    }

    let partial_name = format!(
        "{}.partial",
        dest.file_name()
            .ok_or_else(|| EngineError::DestNotEmpty(dest.display().to_string()))?
            .to_string_lossy()
    );
    let partial_dir = dest
        .parent()
        .ok_or_else(|| EngineError::DestNotEmpty(dest.display().to_string()))?
        .join(partial_name);

    // Clean up any stale partial from a previous interrupted run.
    if partial_dir.exists() {
        fs::remove_dir_all(&partial_dir)?;
    }

    let client = Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()?;

    let total = lock.packages.len();
    let done_counter = std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0));
    stream::iter(lock.packages.iter().map(|(k, v)| (k.clone(), v.clone())))
        .map(|(lock_key, pkg)| {
            let client = client.clone();
            let partial_dir = partial_dir.clone();
            let opts = opts.clone();
            let done_counter = done_counter.clone();
            let on_progress = on_progress.clone();

            async move {
                let bytes = download_package(&client, &pkg, &opts).await?;
                pkg.verify_sha512(&bytes)?;
                unpack_package(&partial_dir, &lock_key, &pkg, &bytes)?;

                let done = done_counter.fetch_add(1, std::sync::atomic::Ordering::Relaxed) + 1;
                on_progress(AssembleProgress {
                    total,
                    done,
                    current: pkg.name.clone(),
                });
                Ok::<_, EngineError>(())
            }
        })
        .buffer_unordered(opts.concurrency)
        .try_for_each(|_| futures::future::ok(()))
        .await?;

    // Prune non-target platform prebuilds.
    for (rel_dir, names) in &lock.prune {
        let base = partial_dir.join("node_modules").join(rel_dir);
        for name in names {
            let target = base.join(name);
            if target.exists() {
                fs::remove_dir_all(&target)?;
            }
        }
    }

    // Write acp.cordis.yml and verify its sha256.
    fs::write(partial_dir.join("acp.cordis.yml"), cordis_yml)?;
    let actual_sha256 = EngineLock::sha256_cordis_config(cordis_yml);
    if actual_sha256 != lock.cordis_config_sha256 {
        return Err(EngineError::CordisConfigMismatch);
    }

    // Write a copy of the lock for runtime reference.
    fs::write(
        partial_dir.join("engine-lock.json"),
        serde_json::to_string_pretty(lock)?,
    )?;

    // Entrypoint assertion.
    let entrypoint = partial_dir.join(lock.entrypoint_path());
    if !entrypoint.is_file() {
        return Err(EngineError::MissingEntrypoint);
    }

    // Move partial into place.
    fs::rename(&partial_dir, dest)?;
    Ok(())
}

async fn download_package(
    client: &Client,
    pkg: &LockedPackage,
    opts: &AssembleOptions,
) -> Result<Vec<u8>, EngineError> {
    for registry in [&opts.registry, &opts.registry_fallback] {
        let url = format!("{}{}", registry.trim_end_matches('/'), pkg.tarball_path);
        match client.get(&url).send().await {
            Ok(resp) if resp.status().is_success() => match resp.bytes().await {
                Ok(bytes) => return Ok(bytes.to_vec()),
                Err(e) => return Err(e.into()),
            },
            Ok(resp) => {
                log::warn!("registry returned {} for {}", resp.status(), pkg.name);
            }
            Err(e) => {
                log::warn!("download error for {}: {}", pkg.name, e);
            }
        }
    }
    Err(EngineError::DownloadFailed(pkg.name.clone()))
}

fn unpack_package(
    partial_dir: &Path,
    lock_key: &str,
    pkg: &LockedPackage,
    bytes: &[u8],
) -> Result<(), EngineError> {
    let base = partial_dir.join(lock_key);
    let cursor = Cursor::new(bytes);
    let tar = GzDecoder::new(cursor);
    let mut archive = Archive::new(tar);

    for entry in archive.entries()? {
        let mut entry = entry?;
        let path = entry.path()?;
        let path_str = path.to_string_lossy();

        let inner = match path_str.strip_prefix("package/") {
            Some(inner) => Path::new(inner),
            None => continue,
        };

        // Reject any path component that is `..`.
        for comp in inner.components() {
            if comp == Component::ParentDir {
                return Err(EngineError::PathTraversal);
            }
        }

        let dest_path = base.join(inner);

        // Defensive: ensure the resolved path is still inside `base`.
        let resolved = normalize_path(&dest_path);
        let base_resolved = normalize_path(&base);
        if !resolved.starts_with(&base_resolved) {
            return Err(EngineError::PathTraversal);
        }

        match entry.header().entry_type() {
            tar::EntryType::Directory => {
                fs::create_dir_all(&dest_path)?;
            }
            tar::EntryType::Regular | tar::EntryType::GNULongName | tar::EntryType::GNULongLink => {
                if let Some(parent) = dest_path.parent() {
                    fs::create_dir_all(parent)?;
                }
                entry.unpack(&dest_path)?;
            }
            // Symlinks are skipped for safety; npm packages rarely need them at runtime.
            _ => {}
        }
    }

    log::info!("unpacked {}", pkg.name);
    Ok(())
}

fn normalize_path(path: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for comp in path.components() {
        match comp {
            Component::Prefix(_) | Component::RootDir | Component::Normal(_) => out.push(comp),
            Component::CurDir => {}
            Component::ParentDir => {
                if !out.pop() {
                    out.push("..");
                }
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::io::Write;
    use base64::{Engine, engine::general_purpose};

    fn make_tar_gz(files: &[(&str, &[u8])]) -> Vec<u8> {
        let mut tar = tar::Builder::new(Vec::new());
        for (path, data) in files {
            let mut header = tar::Header::new_gnu();
            // Bypass tar's `..` rejection by writing the name bytes directly.
            {
                let bytes = header.as_mut_bytes();
                let name = path.as_bytes();
                bytes[..name.len()].copy_from_slice(name);
            }
            header.set_size(data.len() as u64);
            header.set_mode(0o644);
            header.set_cksum();
            tar.append(&header, *data).unwrap();
        }
        let raw = tar.into_inner().unwrap();
        let mut gz = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::default());
        gz.write_all(&raw).unwrap();
        gz.finish().unwrap()
    }

    fn sha512_of(bytes: &[u8]) -> String {
        use sha2::{Digest, Sha512};
        format!("sha512-{}", general_purpose::STANDARD.encode(Sha512::digest(bytes)))
    }

    #[test]
    fn unpack_strips_package_prefix() {
        let temp = std::env::temp_dir().join(format!("inkstatute-unpack-{}", std::process::id()));
        fs::remove_dir_all(&temp).ok();
        fs::create_dir_all(&temp).unwrap();

        let files = [("package/lib/bin.js", b"console.log(1)" as &[u8])];
        let tar = make_tar_gz(&files);
        let pkg = LockedPackage {
            name: "@deepseek-ai/dsh-acp-demo".to_string(),
            version: "0.1.0-rc.6".to_string(),
            integrity: sha512_of(&tar),
            tarball_path: "/x".to_string(),
        };

        unpack_package(&temp, "node_modules/@deepseek-ai/dsh-acp-demo", &pkg, &tar).unwrap();
        let extracted = temp.join("node_modules/@deepseek-ai/dsh-acp-demo/lib/bin.js");
        assert!(extracted.exists());

        fs::remove_dir_all(&temp).ok();
    }

    #[test]
    fn unpack_rejects_path_traversal() {
        let temp = std::env::temp_dir().join(format!("inkstatute-traverse-{}", std::process::id()));
        fs::remove_dir_all(&temp).ok();
        fs::create_dir_all(&temp).unwrap();

        let files = [("package/../evil.txt", b"bad" as &[u8])];
        let tar = make_tar_gz(&files);
        let pkg = LockedPackage {
            name: "evil".to_string(),
            version: "1.0.0".to_string(),
            integrity: sha512_of(&tar),
            tarball_path: "/evil".to_string(),
        };

        assert!(matches!(
            unpack_package(&temp, "node_modules/evil", &pkg, &tar),
            Err(EngineError::PathTraversal)
        ));

        fs::remove_dir_all(&temp).ok();
    }

    #[test]
    fn verify_fails_on_bad_sha512() {
        let mut lock = sample_lock();
        lock.packages.insert(
            "node_modules/@deepseek-ai/dsh-acp-demo".to_string(),
            LockedPackage {
                name: "@deepseek-ai/dsh-acp-demo".to_string(),
                version: "0.1.0-rc.6".to_string(),
                integrity: "sha512-".to_string() + &general_purpose::STANDARD.encode([0u8; 64].as_slice()),
                tarball_path: "/x".to_string(),
            },
        );
        let pkg = lock.packages.values().next().unwrap();
        assert!(pkg.verify_sha512(b"mismatch").is_err());
    }

    fn sample_lock() -> EngineLock {
        EngineLock {
            schema_version: "1.0.0".to_string(),
            engine_version: "0.1.0-rc.6".to_string(),
            node_version: "24.19.0".to_string(),
            target_platform: "win32-x64".to_string(),
            compatible_app_range: ">=0.1.0 <1.0.0".to_string(),
            cordis_config_sha256: "deadbeef".to_string(),
            generated_at: "2026-08-15T00:00:00Z".to_string(),
            prune: HashMap::new(),
            packages: HashMap::new(),
        }
    }
}
