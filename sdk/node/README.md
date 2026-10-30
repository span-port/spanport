# spanport (Node.js SDK)

Send your Node.js app's logs to Spanport. Keep logging the way you already do.

```bash
npm install spanport
```

```js
import * as spanport from "spanport";

spanport.init({
  // From Setup → API keys → Data keys in Spanport (shown once)
  dataKey: "sp_ingest_...",
  service: "orders-api",
  // Defaults: http://localhost:4318 and http://localhost:8000
  collectorUrl: "https://spanport-collector.example.com",
  serverUrl: "https://spanport.example.com",
});

console.error("Payment failed for order 1042"); // sent automatically
```

**pino and winston** write JSON lines to `spanport.logStream()`:

```js
import pino from "pino";
const logger = pino(pino.multistream([{ stream: process.stdout }, { stream: spanport.logStream() }]));

import winston from "winston";
const logger = winston.createLogger({
  format: winston.format.combine(winston.format.timestamp(), winston.format.json()),
  transports: [
    new winston.transports.Console(),
    new winston.transports.Stream({ stream: spanport.logStream() }),
  ],
});
```

- **`console.debug/log/info/warn/error` are sent automatically**; what your app prints doesn't change. Turn this off with `captureConsole: false`.
- **Logs are sent in the background**, in batches. A normal exit sends what is left; on `SIGTERM`, send it yourself: `process.on("SIGTERM", async () => { await spanport.shutdown(); process.exit(0); })`.
- **Logs inside an OpenTelemetry span** carry its `trace_id` and `span_id`; so do pino lines that include them.
- **Wrong key?** At start-up the SDK asks the server once whether the key is valid and prints a clear error on stderr if not. Pass `checkKey: false` if the app cannot reach the server.
- **Use `https://` for anything beyond your own machine or Docker network.** The data key is sent with every batch.
- **It never breaks your app.** `init()` never throws; setup and key problems are printed on stderr as `spanport: ...` and the app carries on. An unreachable collector is not reported yet (see [Troubleshooting](#nothing-arrives-and-there-is-no-error)).

Node.js 22.15 or newer. ES module; CommonJS apps can `require("spanport")`.

At start-up the SDK prints, on stderr:

```
INFO spanport: sending logs for service orders-api to http://localhost:4318
INFO spanport: data key ...a1b2 accepted
```

If the second line is missing or says something else, see [Troubleshooting](#troubleshooting).

## What Spanport receives

| You write | Message | Level | Fields you can filter on |
| --- | --- | --- | --- |
| `console.log("Paid", { orderId: 7 })` | `Paid { orderId: 7 }` (as the terminal shows it) | `debug` DEBUG, `log`/`info` INFO, `warn` WARN, `error` ERROR | none: objects become part of the text |
| pino `logger.info({ "user.id": "u42" }, "Paid")` | `Paid` | pino's level (`fatal` is FATAL, `trace` is TRACE) | every other key, e.g. `user.id` |
| winston `logger.info("Paid", { "user.id": "u42" })` | `Paid` | winston's level (`http` is INFO, `verbose` is DEBUG) | every other key |

- **Use flat, dotted names for fields**: `{ "user.id": "u42" }`, not `{ user: { id: "u42" } }`. A nested object arrives as one field (`user`) holding JSON text, so the User ID filter can't see it.
- Spanport's **Client IP** and **User ID** filters read the fields `client.ip` and `user.id`. Every line also has `log.source` (`console` or `stream`) and the `service` you passed to `init()`.
- Errors: `console.error(err)` and pino's `logger.error(err)` both keep the stack trace in the message.

## Finding logs in Spanport

Pick the project and time range first; a search only looks inside that range.

- **Message contains** finds any part of the text, ignoring case. `nitish` finds `GET /api/files 200 12ms user=nitish@acme.com`; `nitishbharadwaj` doesn't, because those letters never appear together in that line.
- **User ID is u42** and **Client IP is ...** work only for lines that carry the `user.id` / `client.ip` fields (pino or winston, see above). A user written inside the message text is found with Message contains instead.
- **Any other field** you send: choose "Type a query instead" and write `field:value`, e.g. `order.id:1042` or `tenant:acme*` (`*` is a wildcard). In a query, a plain word matches a whole word: `timeout` finds "request timeout" but not "timeouts"; use `timeout*` for that.
- Expand a line to see all its fields, with Filter and Exclude next to each.

## Troubleshooting

### Nothing arrives and there is no error

The SDK checks the data key, not the collector. If `collectorUrl` is wrong or the collector is down, batches are dropped **without a message**. Check that the collector answers from where the app runs:

```bash
curl -i -X POST http://localhost:4318/v1/logs -H "Content-Type: application/json" -d "{}"
```

Any HTTP answer (e.g. `200`) means it is reachable; "connection refused" means it isn't. An app running in Docker can't reach the host's `localhost`: use `http://host.docker.internal:4318`, or `http://collector:4318` on the Spanport Compose network. Also check the Logs page shows the right project and a time range that includes now.

### Searching for a name or id finds nothing

Search finds only text that is in the line. Expand a line you expect to match and look at its message and fields: if the user appears as `user=nitish@acme.com` inside the message, search **Message contains** `nitish@acme.com`; to use the **User ID** filter, send `user.id` as a field (see [What Spanport receives](#what-spanport-receives)).

### NestJS errors show in the terminal but not in Spanport

Nest's built-in logger writes straight to `process.stdout`/`process.stderr`, not through `console`, so the SDK never sees its lines. That includes `ERROR [ExceptionsHandler] ...` for every unhandled exception. Route Nest's logger through `console` and they arrive with the right level (and stack trace), while the terminal output stays the same:

```ts
// src/common/logger/console-routed.logger.ts
import { LoggerService } from "@nestjs/common";

function asText(value: unknown): string {
  if (value instanceof Error) return value.stack ?? value.message;
  return typeof value === "string" ? value : JSON.stringify(value);
}

// Nest passes the context last; a value with line breaks is a stack trace, not a context.
function formatLine(message: unknown, optionalParams: unknown[]): string {
  const lastParam = optionalParams.at(-1);
  const context = typeof lastParam === "string" && !lastParam.includes("\n") ? lastParam : undefined;
  const extraValues = context === undefined ? optionalParams : optionalParams.slice(0, -1);
  const firstLine = context ? `[${context}] ${asText(message)}` : asText(message);
  return [firstLine, ...extraValues.map(asText)].join("\n");
}

export class ConsoleRoutedLogger implements LoggerService {
  log(message: unknown, ...params: unknown[]) { console.log(formatLine(message, params)); }
  warn(message: unknown, ...params: unknown[]) { console.warn(formatLine(message, params)); }
  error(message: unknown, ...params: unknown[]) { console.error(formatLine(message, params)); }
  fatal(message: unknown, ...params: unknown[]) { console.error(formatLine(message, params)); }
  debug(message: unknown, ...params: unknown[]) { console.debug(formatLine(message, params)); }
  verbose(message: unknown, ...params: unknown[]) { console.debug(formatLine(message, params)); }
}
```

```ts
// main.ts
const app = await NestFactory.create(AppModule, { logger: new ConsoleRoutedLogger() });
```

The same applies to any library that writes to `process.stdout` directly: give it a logger that uses `console`, pino or winston.

### Failed requests show as INFO

Every `console.log` line is INFO, whatever its text says. A request logger should pick the method by status, so the ERROR and WARN cards on the Logs page count failed calls:

```ts
const writeLine = status >= 500 ? console.error : status >= 400 ? console.warn : console.log;
writeLine(`${method} ${url} ${status} ${durationMs}ms`);
```

### "data key ...xxxx was rejected"

The server doesn't know the key: it was mistyped, revoked, deleted, belongs to an archived project, or is an admin key (`sp_admin_...`) instead of a data key (`sp_ingest_...`). Check it with:

```bash
curl -i http://localhost:8000/api/v1/api-keys/current -H "Authorization: Bearer sp_ingest_..."
```

`200` means the key is fine; `401` means create a new data key on the API keys page (it is shown once) and restart the app with it.

### Client IP and user are empty

The SDK sends only what a log line carries. Add them as fields named `client.ip` and `user.id`, e.g. with pino: `logger.error({ "client.ip": req.ip, "user.id": userId }, "Payment failed")`. Behind a proxy, read the client address from `X-Forwarded-For` (`app.set("trust proxy", true)` in Express).

### "could not reach ... to check data key"

The key check couldn't reach `serverUrl` (default `http://localhost:8000`). Logs are still sent to the collector, but nobody has confirmed the key. Point `serverUrl` at the Spanport server, or pass `checkKey: false` if the app has no route to it.

## Development

```bash
npm install
npm test
npm run lint
npm run typecheck
npm run build
```
