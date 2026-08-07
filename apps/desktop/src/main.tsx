/**
 * Desktop app entry — renders the full App with theme CSS imports.
 */
import { render } from "solid-js/web";
import "@inkstatute/ui-core/themes";
import "./desktop-shell.css";
import App from "./App";

render(() => <App />, document.getElementById("root")!);
