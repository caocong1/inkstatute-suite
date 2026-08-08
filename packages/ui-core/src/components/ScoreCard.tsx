/**
 * ScoreCard — per-agent per-round 10-point self-score display.
 *
 * Displays arena self-scores on a 10-point framework. Each agent slot gets
 * one row; each round gets one column. Score cells show a numeric value with
 * a visual bar (width = score * 10%). The "best score" column shows the
 * maximum score per agent across all rounds.
 *
 * Data comes from `ArenaScoreEntry[]` (populated by `arenaMetaReducer` from
 * `arena.score_recorded` events). The component does NOT fetch data itself —
 * it accepts scores as a prop.
 *
 * Color coding: >= 8 green, 5-7 yellow, < 5 red.
 */

import { For, Show } from "solid-js";
import type { ArenaScoreEntry } from "../types/arena";
import "./ScoreCard.css";

export interface ScoreCardProps {
  scores: ArenaScoreEntry[];
}

/** Color class for a score value: green >= 8, yellow 5-7, red < 5. */
function scoreColorClass(score: number): string {
  if (score >= 8) return "green";
  if (score >= 5) return "yellow";
  return "red";
}

/** Deterministic avatar color from a slot name. */
function avatarColor(slot: string): string {
  const palette = ["#3b5998", "#1a7f4b", "#b45309", "#7c3aed", "#0e7490", "#be185d"];
  let hash = 0;
  for (let i = 0; i < slot.length; i++) {
    hash = (hash * 31 + slot.charCodeAt(i)) >>> 0;
  }
  return palette[hash % palette.length];
}

export function ScoreCard(props: ScoreCardProps) {
  const maxRound = () => Math.max(...props.scores.map((s) => s.round), 0);
  const rounds = () => Array.from({ length: maxRound() }, (_, i) => i + 1);

  const slots = () => {
    const seen: string[] = [];
    for (const s of props.scores) {
      if (!seen.includes(s.agent_slot)) seen.push(s.agent_slot);
    }
    return seen.sort((a, b) => a.localeCompare(b));
  };

  /** Map of slot → (round → score) plus best score. */
  function slotData(slot: string): {
    byRound: Map<number, number>;
    best: number;
  } {
    const byRound = new Map<number, number>();
    let best = 0;
    for (const s of props.scores) {
      if (s.agent_slot === slot) {
        byRound.set(s.round, s.score);
        if (s.score > best) best = s.score;
      }
    }
    return { byRound, best };
  }

  return (
    <div class="score-card">
      <Show
        when={props.scores.length > 0}
        fallback={<div class="score-empty">暂无评分数据</div>}
      >
        <table class="score-table">
          <thead>
            <tr>
              <th class="col-agent">Agent</th>
              <For each={rounds()}>
                {(r) => <th class="col-round">第 {r} 轮</th>}
              </For>
              <th class="col-best">最佳</th>
            </tr>
          </thead>
          <tbody>
            <For each={slots()}>
              {(slot) => {
                const data = slotData(slot);
                return (
                  <tr>
                    <th class="cell-agent">
                      <span
                        class="agent-avatar"
                        style={{ background: avatarColor(slot) }}
                      >
                        {slot.slice(-2)}
                      </span>
                      <span class="agent-name">{slot}</span>
                    </th>
                    <For each={rounds()}>
                      {(r) => {
                        const score = data.byRound.get(r);
                        return (
                          <Show
                            when={score !== undefined}
                            fallback={<td class="cell-score empty">—</td>}
                          >
                            <td class={`cell-score ${scoreColorClass(score!)}`}>
                              <span class="score-value">{score}</span>
                              <div class="score-bar-track">
                                <div
                                  class="score-bar"
                                  style={{ width: `${score! * 10}%` }}
                                />
                              </div>
                            </td>
                          </Show>
                        );
                      }}
                    </For>
                    <td class={`cell-best ${scoreColorClass(data.best)}`}>
                      {data.best}
                    </td>
                  </tr>
                );
              }}
            </For>
          </tbody>
        </table>
      </Show>
    </div>
  );
}
