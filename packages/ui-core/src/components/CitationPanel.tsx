/**
 * CitationPanel — slide-in citation sources with verification badges.
 *
 * Ported from lawyer-desktop/src/components/workspace/CitationPanel.tsx.
 * Adapted for ui-core: takes CitationGroups as a prop (instead of useConversation()),
 * manages tab state internally, and uses callback props for actions.
 *
 * Pure presentational component driven by citation data from citation.recorded events.
 */

import { createSignal, For, Show } from "solid-js";
import type { CitationCard, CitationGroups } from "../types/legal";
import { renderSegs } from "../utils/renderSegs";
import { Icon } from "./Icons";
import "./CitationPanel.css";

export interface CitationPanelProps {
  groups: CitationGroups;
  open: boolean;
  onToggle: () => void;
  onInsert?: (citation: CitationCard) => void;
  onLocate?: (citation: CitationCard) => void;
}

function verificationBadge(c: CitationCard): { cls: string; label: string } | null {
  if (c.verified === "verified") return { cls: "ok", label: "✓ 已核验" };
  if (c.verified === "retrieved") return { cls: "ret", label: "✓ 已检索" };
  if (c.verified === "unverified") return { cls: "warn", label: "⚠ 待律师复核" };
  return null;
}

export function CitationPanel(props: CitationPanelProps) {
  const [tab, setTab] = createSignal<"law" | "case">("law");

  const list = () => (tab() === "case" ? props.groups.case : props.groups.law);

  return (
    <div
      class={`cite-panel${props.open ? " open" : ""}`}
      aria-label={props.open ? "引用来源面板" : undefined}
    >
      <div class="cp-h">
        <Icon name="book" style={{ width: "18px", height: "18px", color: "var(--accent)" }} />
        <span class="t">引用来源</span>
        <span class="grow" />
        <button
          type="button"
          class="cp-close"
          aria-label="关闭"
          onClick={props.onToggle}
        >
          <Icon name="x" />
        </button>
      </div>
      <div class="cp-tabs">
        <div
          class={`cp-tab${tab() === "law" ? " on" : ""}`}
          onClick={() => setTab("law")}
        >
          法条（{props.groups.law.length}）
        </div>
        <div
          class={`cp-tab${tab() === "case" ? " on" : ""}`}
          onClick={() => setTab("case")}
        >
          判例 · 类案（{props.groups.case.length}）
        </div>
      </div>
      <div class="cp-body scroll">
        <Show
          when={list().length > 0}
          fallback={<div class="cp-empty">暂无引用来源，将在文书生成后自动收录</div>}
        >
          <For each={list()}>
            {(c) => (
              <div class="cite-card" id={`cc-${c.key}`}>
                <div class="cc-tag">
                  <Icon
                    name={tab() === "case" ? "gavel" : "scale"}
                    style={{ width: "12px", height: "12px" }}
                  />
                  {c.tag}
                  <Show when={verificationBadge(c)}>
                    {(badge) => (
                      <span class={`cc-verify ${badge().cls}`}>{badge().label}</span>
                    )}
                  </Show>
                  <Show when={c.tier}>
                    <span class="cc-tier">{c.tier}</span>
                  </Show>
                </div>
                <div class="cc-title">{c.title}</div>
                <Show when={c.note}>
                  <div class="cc-note">{c.note}</div>
                </Show>
                <div class="cc-src">{c.src}</div>
                <div class="cc-text">{c.text}</div>
                <div class="cc-rel">{renderSegs(c.rel, {})}</div>
                <div class="cc-actions">
                  <button
                    type="button"
                    class="cc-btn prim"
                    onClick={() => props.onInsert?.(c)}
                  >
                    <Icon name="plus" />
                    插入引用
                  </button>
                  <button
                    type="button"
                    class="cc-btn"
                    onClick={() => props.onLocate?.(c)}
                  >
                    <Icon name="locate" />
                    在文中定位
                  </button>
                </div>
              </div>
            )}
          </For>
        </Show>
      </div>
    </div>
  );
}
