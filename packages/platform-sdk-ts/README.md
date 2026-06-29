# @inkstatute/platform-sdk-ts

Remote/thin TypeScript SDK generated from the InkStatute platform API
OpenAPI document.

The SDK makes plain HTTP requests against a platform API host and never
embeds a local runtime, queue, database, or backend construction. It is
designed for use in Tauri, Electron, and Flutter webview clients, as well
as any other browser or Node.js surface that needs to talk to the platform
API.

## Generation

The SDK is generated deterministically from
`apps/platform_api/openapi/platform-api.json`. To regenerate:

```bash
python packages/platform-sdk-ts/scripts/generate_sdk.py \
  --openapi apps/platform_api/openapi/platform-api.json \
  --out packages/platform-sdk-ts/src/index.ts
```

The generator sorts all multi-valued collections, so two consecutive runs
on the same input produce byte-identical output. Tests assert this in
`packages/platform-sdk-ts/tests/test_sdk_generation.py`.

## Usage

```ts
import { PlatformApiClient } from "@inkstatute/platform-sdk-ts";

const client = new PlatformApiClient({
  baseUrl: "https://inkstatute.example/v1",
});

const run = await client.createRun({
  turn: {
    turn_id: "turn-001",
    conversation_id: "conv-001",
    channel: "web",
    user_id: "user-001",
    message_type: "text",
    received_at: "2026-06-29T00:00:00Z",
  },
  solution: { solution_id: "lawyer-v1" },
});

for await (const frame of client.streamRun(run.run_id)) {
  console.log(frame.event, frame.id, frame.data);
}
```

## Not live acceptance

The SDK is a default-off, fixture-grade client. It is **not** live
acceptance evidence and **not** a production web UI. The platform API host
it talks to is itself default-off behind `INKSTATUTE_PLATFORM_API_ENABLED`.
