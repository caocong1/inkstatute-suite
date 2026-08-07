/** Placeholder — full implementation in Task 93-01-05 */
import { type Component } from "solid-js";
import { useParams } from "@solidjs/router";

export const WorkspacePage: Component = () => {
  const params = useParams();
  return <div>工作区占位: {params.conversationId}</div>;
};
