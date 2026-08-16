#!/usr/bin/env node
// SKL-11: 语料仓 → 分域预设物化管线。
//
// 把 ai-for-china-legal 语料仓 4 个域的法律技能物化进 `presets/<domain>/skills/`：
//
//   commercial-legal → legal-commercial     employment-legal → legal-employment
//   family-legal     → legal-family         litigation-legal → legal-litigation
//
// 形态变换（对齐 DSH skill-filesystem 的单层发现语义 + token 预算门禁）：
//   1. 只有顶层父技能进目录（21 条）；全部子技能正文**内联**为父文档的
//      「子技能」章节 —— 目录预算只计 name+description，正文由引擎在
//      技能被调用时才加载，不占目录预算。
//   2. 斜杠命令引用（/xxx-legal:name）与子技能路径引用改写为文档内章节
//      引用或已挂载技能名。
//   3. `_shared` 参考文档原样拷贝到 skills/_shared/（无 SKILL.md，
//      对目录与门禁不可见），正文引用改写为 ../_shared/ 相对路径。
//   4. 物化目录名 = frontmatter name（门禁要求 name == 目录名）。
//
// legal-core 不在映射内，保持手写内容不动。
//
// 用法：node scripts/materialize-corpus-skills.mjs
//   语料仓路径默认取本仓的兄弟目录 ../ai-for-china-legal，
//   可用 INKSTATUTE_CORPUS_DIR 覆盖。
//
// 幂等：每次运行整体重建映射域的 skills/ 目录。

import {
  readFileSync,
  writeFileSync,
  readdirSync,
  statSync,
  existsSync,
  rmSync,
  mkdirSync,
  copyFileSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const CORPUS_ROOT =
  process.env.INKSTATUTE_CORPUS_DIR || path.resolve(REPO_ROOT, "..", "ai-for-china-legal");

const DOMAIN_MAP = {
  "commercial-legal": "legal-commercial",
  "employment-legal": "legal-employment",
  "family-legal": "legal-family",
  "litigation-legal": "legal-litigation",
};

const BUDGET = parseInt(process.env.INKSTATUTE_SKILL_BUDGET || "8000", 10);

if (!existsSync(CORPUS_ROOT)) {
  console.error(`[FAIL] 语料仓不存在：${CORPUS_ROOT}（可用 INKSTATUTE_CORPUS_DIR 覆盖）`);
  process.exit(1);
}

// --- frontmatter ------------------------------------------------------------

/** 解析 SKILL.md：返回 { name, description, body }。description 支持块标量（> / >-）。 */
function parseSkill(filePath) {
  const raw = readFileSync(filePath, "utf8").replace(/\r\n/g, "\n");
  const m = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!m) throw new Error(`无 frontmatter：${filePath}`);
  const fm = m[1];
  const body = m[2];

  const name = ((fm.match(/^name:\s*(.+)$/m) || [])[1] || "").trim();
  if (!name) throw new Error(`frontmatter 缺 name：${filePath}`);

  let description = "";
  const block = fm.match(/^description:\s*>-?\s*\n((?:[ \t]+.*\n?)+)/m);
  if (block) {
    description = block[1].replace(/\s+/g, " ").trim();
  } else {
    description = ((fm.match(/^description:\s*(.+)$/m) || [])[1] || "").trim();
  }
  if (!description) throw new Error(`frontmatter 缺 description：${filePath}`);

  return { name, description, body };
}

// --- 收集 -------------------------------------------------------------------

/** 一个父技能：{ dir, name, description, body, children: [{dir, name, description, body}] } */
function collectDomain(corpusDomain) {
  const skillsRoot = path.join(CORPUS_ROOT, corpusDomain, "skills");
  const parents = [];
  for (const d of readdirSync(skillsRoot).sort()) {
    if (d === "_shared") continue;
    const dirPath = path.join(skillsRoot, d);
    if (!statSync(dirPath).isDirectory()) continue;
    const skillMd = path.join(dirPath, "SKILL.md");
    if (!existsSync(skillMd)) continue;

    const parent = { dir: d, ...parseSkill(skillMd), children: [] };
    for (const c of readdirSync(dirPath).sort()) {
      const childMd = path.join(dirPath, c, "SKILL.md");
      if (existsSync(childMd)) {
        parent.children.push({ dir: c, ...parseSkill(childMd) });
      }
    }
    parents.push(parent);
  }
  return parents;
}

// --- 引用改写 ----------------------------------------------------------------

/**
 * 改写一个已组装文档里的旧引用：
 *  - /<domain>:<name> 斜杠命令 → 文档内子技能章节 或 已挂载技能名
 *  - 子技能路径 …/<parentDir>/<childDir>/SKILL.md → 文档内子技能章节
 *  - skills/_shared/ → ../_shared/
 * 返回 { text, unresolved: [...] }。
 */
function rewriteRefs(text, ctx) {
  const unresolved = [];

  // 斜杠命令。目标可能是：本父技能的子技能目录名 / 本域或他域顶层技能目录名 /
  // 域内其他父技能的子技能（域内目录名唯一时才可安全定向）/ 语料仓悬空引用。
  text = text.replace(/\/([a-z]+-legal):([a-z0-9-]+)/g, (full, dom, target) => {
    const child = ctx.childrenByDir.get(target);
    if (child) return `「子技能：${child.name}」章节（见本文档）`;
    const mounted = ctx.topLevelByDomainDir.get(`${dom}/${target}`);
    if (mounted) return `\`${mounted}\` 技能`;
    const crossParent = ctx.uniqueChildByDomainDir.get(`${dom}/${target}`);
    if (crossParent === "AMBIGUOUS") {
      unresolved.push(full);
      return full;
    }
    if (crossParent) {
      return `\`${crossParent.parentName}\` 技能的「子技能：${crossParent.childName}」章节`;
    }
    // 语料仓中不存在的技能（悬空引用）：明示不可用，保持流程可降级。
    return `「${target}」（本环境未提供该技能，此步由律师线下执行或跳过）`;
  });

  // 子技能路径（含可选的域前缀 / skills 前缀 / 反引号内出现）。
  text = text.replace(
    /(?:[a-z-]+\/)?skills\/([a-z0-9-]+)\/([a-z0-9-]+)\/SKILL\.md/g,
    (full, parentDir, childDir) => {
      if (parentDir === ctx.parentDir) {
        const child = ctx.childrenByDir.get(childDir);
        if (child) return `本文档「子技能：${child.name}」章节`;
      }
      unresolved.push(full);
      return full;
    }
  );

  // 裸 <childDir>/SKILL.md 形式。
  text = text.replace(/(?<![a-z0-9/-])([a-z0-9-]+)\/SKILL\.md/g, (full, childDir) => {
    const child = ctx.childrenByDir.get(childDir);
    if (child) return `本文档「子技能：${child.name}」章节`;
    return full;
  });

  // _shared 引用：物化后位于技能目录的兄弟目录。
  text = text.replace(/(?:[a-z-]+\/)?skills\/_shared\//g, "../_shared/");

  return { text, unresolved };
}

// --- 组装 -------------------------------------------------------------------

function preamble() {
  return `> **墨律桌面环境适配说明**（物化管线自动生成）：
> - 本文档已把全部子技能**内联**为「子技能」章节；原文对子技能路径或斜杠命令的引用均已改写为文档内引用。
> - 实践配置文件（\`CLAUDE.md\`）在本环境**不存在**：读取不到时一律按模板默认值处理，**不要**尝试创建或写入 CLAUDE.md。
> - \`../_shared/\` 参考文档随技能包提供；若读取被沙箱拒绝，按各文档的默认约定处理。
> - 起草或生成任何文档之前，必须先向用户确认**输出格式**与**保存位置**（见文末「硬性护栏」）。
`;
}

function composeParent(parent, ctx) {
  // 子技能按父文档正文首次引用顺序排列，未被引用的按目录名附后。
  const order = [];
  for (const c of parent.children) {
    const idx = parent.body.indexOf(c.dir);
    order.push({ c, idx: idx === -1 ? Number.MAX_SAFE_INTEGER : idx });
  }
  order.sort((a, b) => a.idx - b.idx || a.c.dir.localeCompare(b.c.dir));

  let doc = `---\nname: ${parent.name}\ndescription: ${parent.description}\n---\n\n`;
  doc += preamble() + "\n";
  doc += parent.body.trimEnd() + "\n";

  for (const { c } of order) {
    doc += `\n\n---\n\n# 子技能：${c.name}\n\n`;
    doc += `> 原独立子技能 \`${c.dir}\`：${c.description}\n\n`;
    doc += c.body.trimEnd() + "\n";
  }

  const { text, unresolved } = rewriteRefs(doc, ctx);
  return { text, unresolved };
}

// --- 主流程 ------------------------------------------------------------------

const allDomains = {};
for (const corpusDomain of Object.keys(DOMAIN_MAP)) {
  allDomains[corpusDomain] = collectDomain(corpusDomain);
}

// 顶层技能名索引：`<corpusDomain>/<dir>` → 挂载名（frontmatter name）。
const topLevelByDomainDir = new Map();
for (const [corpusDomain, parents] of Object.entries(allDomains)) {
  for (const p of parents) topLevelByDomainDir.set(`${corpusDomain}/${p.dir}`, p.name);
}

// 域内子技能索引：`<corpusDomain>/<childDir>` → { parentName, childName }。
// 目录名在域内不唯一时置 "AMBIGUOUS"（改写时保留原文并报未解析）。
const uniqueChildByDomainDir = new Map();
for (const [corpusDomain, parents] of Object.entries(allDomains)) {
  for (const p of parents) {
    for (const c of p.children) {
      const key = `${corpusDomain}/${c.dir}`;
      if (uniqueChildByDomainDir.has(key)) {
        uniqueChildByDomainDir.set(key, "AMBIGUOUS");
      } else {
        uniqueChildByDomainDir.set(key, { parentName: p.name, childName: c.name });
      }
    }
  }
}

let totalParents = 0;
let totalChildren = 0;
const allUnresolved = [];
const mountedNames = [];

for (const [corpusDomain, targetDomain] of Object.entries(DOMAIN_MAP)) {
  const parents = allDomains[corpusDomain];
  const targetSkills = path.join(REPO_ROOT, "presets", targetDomain, "skills");

  rmSync(targetSkills, { recursive: true, force: true });
  mkdirSync(targetSkills, { recursive: true });

  for (const parent of parents) {
    const ctx = {
      parentDir: parent.dir,
      childrenByDir: new Map(parent.children.map((c) => [c.dir, c])),
      topLevelByDomainDir,
      uniqueChildByDomainDir,
    };
    const { text, unresolved } = composeParent(parent, ctx);
    for (const u of unresolved) allUnresolved.push(`${corpusDomain}/${parent.dir}: ${u}`);

    const outDir = path.join(targetSkills, parent.name);
    mkdirSync(outDir, { recursive: true });
    writeFileSync(path.join(outDir, "SKILL.md"), text);
    mountedNames.push(parent.name);
    totalParents++;
    totalChildren += parent.children.length;
  }

  // _shared 参考文档原样拷贝（无 SKILL.md，对 DSH 发现与门禁均不可见）。
  const sharedSrc = path.join(CORPUS_ROOT, corpusDomain, "skills", "_shared");
  if (existsSync(sharedSrc)) {
    const sharedDst = path.join(targetSkills, "_shared");
    mkdirSync(sharedDst, { recursive: true });
    for (const f of readdirSync(sharedSrc)) {
      copyFileSync(path.join(sharedSrc, f), path.join(sharedDst, f));
    }
  }

  console.log(`${corpusDomain} → ${targetDomain}: ${parents.length} 父技能`);
}

// --- 校验 -------------------------------------------------------------------

let failed = false;
function check(name, fn) {
  try {
    fn();
    console.log(`[PASS] ${name}`);
  } catch (e) {
    failed = true;
    console.log(`[FAIL] ${name}: ${e.message}`);
  }
}

check("无未解析的旧引用（斜杠命令 / 子技能路径）", () => {
  if (allUnresolved.length > 0) {
    throw new Error(`${allUnresolved.length} 处：\n  ` + allUnresolved.slice(0, 10).join("\n  "));
  }
});

check("技能名全局唯一（含 legal-core）且 name == 目录名", () => {
  const seen = new Map();
  const presetsRoot = path.join(REPO_ROOT, "presets");
  for (const domain of readdirSync(presetsRoot)) {
    const skillsDir = path.join(presetsRoot, domain, "skills");
    if (!existsSync(skillsDir)) continue;
    for (const d of readdirSync(skillsDir)) {
      const md = path.join(skillsDir, d, "SKILL.md");
      if (!existsSync(md)) continue;
      const { name } = parseSkill(md);
      if (name !== d) throw new Error(`${domain}/${d}: name '${name}' ≠ 目录名`);
      if (seen.has(name)) throw new Error(`重名 '${name}'：${domain} 与 ${seen.get(name)}`);
      seen.set(name, domain);
    }
  }
});

check(`目录预算 ≤ ${BUDGET} 字符（全部 presets 域）`, () => {
  let total = 0;
  const presetsRoot = path.join(REPO_ROOT, "presets");
  for (const domain of readdirSync(presetsRoot)) {
    const skillsDir = path.join(presetsRoot, domain, "skills");
    if (!existsSync(skillsDir)) continue;
    for (const d of readdirSync(skillsDir)) {
      const md = path.join(skillsDir, d, "SKILL.md");
      if (!existsSync(md)) continue;
      const { name, description } = parseSkill(md);
      total += `- \`${name}\`: ${description}\n`.length;
    }
  }
  console.log(`  目录预算实际：${total} 字符`);
  if (total > BUDGET) throw new Error(`超预算：${total} > ${BUDGET}`);
});

console.log(
  `\n物化完成：${totalParents} 父技能（内联 ${totalChildren} 子技能）→ presets/`
);
process.exit(failed ? 1 : 0);
