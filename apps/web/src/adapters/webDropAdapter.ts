/**
 * Web DropAdapter — browser drag-drop path classification.
 *
 * Maps DataTransferItemList to DroppedPath[]. Browsers don't expose
 * real file system paths — `path` is the file name, `isDir` is always false.
 */
import type { DropAdapter, DroppedPath } from "@inkstatute/ui-core";

export const webDropAdapter: DropAdapter = {
  async classifyDroppedPaths(items: DataTransferItemList): Promise<DroppedPath[]> {
    const paths: DroppedPath[] = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind !== "file") continue;
      const file = item.getAsFile();
      if (!file) continue;
      paths.push({
        path: file.name,
        isDir: false,
        size: file.size,
      });
    }
    return paths;
  },
};
