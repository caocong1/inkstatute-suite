/**
 * App — root component with context providers and router.
 *
 * Wraps everything in:
 * AuthProvider → AdapterContext.Provider → ConversationProvider → Router
 *
 * Routes:
 * - /login → LoginPage (unauthenticated)
 * - / → AppLayout > HomePage (authenticated)
 * - /workspace/:conversationId → AppLayout > WorkspacePage (authenticated)
 */
import { type Component } from "solid-js";
import { Router, Route } from "@solidjs/router";
import { AdapterContext } from "@inkstatute/ui-core";
import { AuthProvider } from "./contexts/AuthContext";
import { ConversationProvider } from "./contexts/ConversationContext";
import { webAdapters } from "./adapters/webAdapters";
import { AppLayout } from "./layouts/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { HomePage } from "./pages/HomePage";
import { WorkspacePage } from "./pages/WorkspacePage";

const App: Component = () => {
  return (
    <AuthProvider>
      <AdapterContext.Provider value={webAdapters}>
        <ConversationProvider>
          <Router>
            <Route path="/login" component={LoginPage} />
            <Route path="/" component={AppLayout}>
              <Route path="/" component={HomePage} />
              <Route path="/workspace/:conversationId" component={WorkspacePage} />
            </Route>
          </Router>
        </ConversationProvider>
      </AdapterContext.Provider>
    </AuthProvider>
  );
};

export default App;
