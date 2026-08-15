/**
 * Settings service — wrappers for credential/provider Tauri commands.
 * Components never call invoke() directly.
 */
import { invoke } from "@tauri-apps/api/core";

export interface ProviderInfo {
  id: string;
  display_name: string;
  env_var: string;
  has_key: boolean;
}

export async function listProviders(): Promise<ProviderInfo[]> {
  return invoke<ProviderInfo[]>("list_providers");
}

export async function getActiveProvider(): Promise<string> {
  return invoke<string>("get_active_provider");
}

export async function setActiveProvider(id: string): Promise<void> {
  await invoke("set_active_provider", { id });
}

export async function setProviderKey(id: string, key: string): Promise<void> {
  await invoke("set_provider_key", { id, key });
}

export async function clearProviderKey(id: string): Promise<void> {
  await invoke("clear_provider_key", { id });
}

export async function testProvider(id: string): Promise<string> {
  return invoke<string>("test_provider", { id });
}

// Re-export file dir commands for settings
export async function getAllowedFileDirs(): Promise<string[]> {
  return invoke<string[]>("get_allowed_file_dirs");
}

export async function setAllowedFileDirs(dirs: string[]): Promise<void> {
  await invoke("set_allowed_file_dirs", { dirs });
}

export async function grantPathAccess(path: string): Promise<void> {
  await invoke("grant_path_access", { path });
}
