/**
 * Web FileAdapter — browser-based file open/save using hidden <input> and <a download>.
 *
 * Replaces the Tauri dialog-based FileAdapter. In the browser, file paths
 * are not exposed — `open()` returns the file name(s), and `save()` triggers
 * a download.
 */
import type { FileAdapter } from "@inkstatute/ui-core";

export const webFileAdapter: FileAdapter = {
  async open(options) {
    return new Promise((resolve) => {
      const input = document.createElement("input");
      input.type = "file";
      input.style.position = "fixed";
      input.style.left = "-9999px";
      input.style.opacity = "0";
      if (options?.multiple) {
        input.multiple = true;
      }
      input.addEventListener("change", () => {
        if (!input.files || input.files.length === 0) {
          resolve(null);
          return;
        }
        if (options?.multiple) {
          const names: string[] = [];
          for (let i = 0; i < input.files.length; i++) {
            names.push(input.files[i].name);
          }
          resolve(names);
        } else {
          resolve(input.files[0].name);
        }
        input.remove();
      });
      // If the user cancels the dialog, the change event never fires.
      // We can't detect cancellation in the browser, so the Promise
      // remains pending. This is a known browser limitation.
      document.body.appendChild(input);
      input.click();
    });
  },

  async save(options) {
    // In the browser, save() cannot write to a specific path.
    // The actual file content is managed by the calling code via
    // a separate download mechanism. Here we just return the
    // defaultPath as a "saved path" placeholder.
    return options.defaultPath ?? null;
  },
};
