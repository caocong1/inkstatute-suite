/**
 * HomePage — desktop home page placeholder.
 * Full implementation in Task 94-01-05.
 */
import { onMount, type Component } from "solid-js";

export interface HomePageProps {
  onNavigateToWorkspace: () => void;
}

export const HomePage: Component<HomePageProps> = () => {
  onMount(() => {
    document.title = "墨律 InkStatute";
  });
  return <div>墨律 Desktop — Home (tracer placeholder)</div>;
};
