/**
 * groupCitations — maps CitationRecord[] (from citation.recorded events) to
 * CitationGroups (law/case grouping with verification status).
 *
 * CitationRecord has only `source` and `status` fields. This helper:
 * 1. Determines if a citation is a law or case citation based on source text patterns
 * 2. Maps the status to CitationVerification
 * 3. Builds CitationCard objects for the CitationPanel
 */

import type { CitationCard, CitationGroups } from "../types/legal";
import type { CitationRecord } from "@inkstatute/platform-sdk-ts/events";

const CASE_PATTERN = /判例|案例|裁定|判决|案号|人民法院|最高法|高院/;

export function groupCitations(citations: CitationRecord[]): CitationGroups {
  const law: CitationCard[] = [];
  const caseList: CitationCard[] = [];
  let lawIdx = 0;
  let caseIdx = 0;

  for (const c of citations) {
    const isCase = CASE_PATTERN.test(c.source);
    if (isCase) {
      caseIdx++;
      caseList.push({
        key: `case${caseIdx}`,
        tag: "案例",
        title: c.source,
        src: c.source,
        text: c.source,
        rel: [{ t: c.source }],
        verified: c.status,
      });
    } else {
      lawIdx++;
      law.push({
        key: `law${lawIdx}`,
        tag: c.source,
        title: c.source,
        src: c.source,
        text: c.source,
        rel: [{ t: c.source }],
        verified: c.status,
      });
    }
  }

  return { law, case: caseList };
}
