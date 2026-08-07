import { describe, it, expect, vi, beforeEach } from "vitest";
import { webFileAdapter } from "../src/adapters/webFileAdapter";
import { webDropAdapter } from "../src/adapters/webDropAdapter";
import { webAppInfoAdapter } from "../src/adapters/webAppInfoAdapter";
import { webWorkspaceAdapter } from "../src/adapters/webWorkspaceAdapter";
import { webDocumentParser } from "../src/adapters/webDocumentParser";
import { webAdapters } from "../src/adapters/webAdapters";

describe("webFileAdapter", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("save returns defaultPath as placeholder", async () => {
    const result = await webFileAdapter.save({ defaultPath: "test.txt" });
    expect(result).toBe("test.txt");
  });

  it("save returns null when no defaultPath", async () => {
    const result = await webFileAdapter.save({});
    expect(result).toBeNull();
  });

  it("open creates a hidden file input element", async () => {
    const inputMock = {
      type: "",
      style: { position: "", left: "", opacity: "" },
      multiple: false,
      addEventListener: vi.fn(),
      click: vi.fn(),
      remove: vi.fn(),
      files: null,
    };
    const createElementSpy = vi.spyOn(document, "createElement").mockReturnValue(inputMock as any);
    const appendChildSpy = vi.spyOn(document.body, "appendChild").mockImplementation(() => inputMock as any);

    const promise = webFileAdapter.open();
    expect(inputMock.type).toBe("file");
    expect(inputMock.style.position).toBe("fixed");
    expect(inputMock.click).toHaveBeenCalled();
    expect(inputMock.addEventListener).toHaveBeenCalledWith("change", expect.any(Function));

    createElementSpy.mockRestore();
    appendChildSpy.mockRestore();
    // Promise remains pending (browser limitation — change event never fires in test)
  });
});

describe("webDropAdapter", () => {
  it("classifyDroppedPaths maps DataTransferItemList to DroppedPath[]", async () => {
    const mockFile = { name: "test.pdf", size: 1024 };
    const mockItems = [
      { kind: "file", getAsFile: () => mockFile },
      { kind: "string", getAsFile: () => null },
    ];
    const result = await webDropAdapter.classifyDroppedPaths(mockItems as any);
    expect(result).toHaveLength(1);
    expect(result[0].path).toBe("test.pdf");
    expect(result[0].isDir).toBe(false);
    expect(result[0].size).toBe(1024);
  });

  it("classifyDroppedPaths returns empty array for no file items", async () => {
    const mockItems = [
      { kind: "string", getAsFile: () => null },
    ];
    const result = await webDropAdapter.classifyDroppedPaths(mockItems as any);
    expect(result).toEqual([]);
  });
});

describe("webAppInfoAdapter", () => {
  it("getVersion returns version string", async () => {
    const result = await webAppInfoAdapter.getVersion();
    expect(result).toBe("0.1.0");
  });

  it("checkForUpdate returns null", async () => {
    const result = await webAppInfoAdapter.checkForUpdate?.();
    expect(result).toBeNull();
  });
});

describe("webWorkspaceAdapter", () => {
  it("listFiles returns empty array", async () => {
    const result = await webWorkspaceAdapter.listFiles();
    expect(result).toEqual([]);
  });

  it("listFiles with query returns empty array", async () => {
    const result = await webWorkspaceAdapter.listFiles("test");
    expect(result).toEqual([]);
  });
});

describe("webDocumentParser", () => {
  it("parseLegalDocument returns a model for valid content", async () => {
    const content = "这是一份法律文书，包含以下条款：甲方和乙方经友好协商，就合同事项达成如下协议：\n\n第一条 合同标的\n甲方同意向乙方提供法律服务。\n\n第二条 合同期限\n本合同自签署之日起生效，有效期为一年。";
    const result = await webDocumentParser.parseLegalDocument(content);
    expect(result).toBeDefined();
    expect(result.title).toBeDefined();
    expect(result.sections).toBeDefined();
  });

  it("parseLegalDocument returns fallback model for unparseable content", async () => {
    const result = await webDocumentParser.parseLegalDocument("not a legal document");
    expect(result).toBeDefined();
    expect(result.sections).toEqual([]);
  });
});

describe("webAdapters", () => {
  it("assembles all 5 adapters", () => {
    expect(webAdapters.file).toBeDefined();
    expect(webAdapters.drop).toBeDefined();
    expect(webAdapters.appInfo).toBeDefined();
    expect(webAdapters.workspace).toBeDefined();
    expect(webAdapters.documentParser).toBeDefined();
  });

  it("window adapter is undefined", () => {
    expect(webAdapters.window).toBeUndefined();
  });
});
