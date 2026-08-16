/**
 * Desktop app entry — renders the full App with theme CSS imports.
 */
import { render } from "solid-js/web";
import "@inkstatute/ui-core/themes";
// Component styles are extracted to dist/ui-core.css by the lib build;
// the JS bundle does not import them itself. Missing this line renders
// every ui-core component unstyled (giant SVGs, drawer as a static column).
import "@inkstatute/ui-core/ui-core.css";
import "./desktop-shell.css";
import App from "./App";

render(() => <App />, document.getElementById("root")!);
