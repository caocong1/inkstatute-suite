import { render } from "solid-js/web";
import "@inkstatute/ui-core/themes";
import "./app-shell.css";

function App() {
  return <div>墨律 Web Client</div>;
}

render(() => <App />, document.getElementById("root")!);
