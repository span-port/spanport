import { useState } from "react";

import { Button } from "../../../components/ui/Button";
import { useCopyText } from "../../../hooks/useCopyText";
import { keySnippets } from "../../../lib/apiKeys";
import type { CreatedKey } from "../api";

interface KeyCreatedPanelProps {
  created: CreatedKey;
  /** Called when the key is copied; after that, leaving the tab may close the panel. */
  onCopied: () => void;
  onDone: () => void;
}

/** The new key, shown this once, with a copy button and how to use it. */
export function KeyCreatedPanel({ created, onCopied, onDone }: KeyCreatedPanelProps) {
  const copyKey = useCopyText();
  const snippets = keySnippets(created.item.key_type, window.location.origin);
  const [snippetIndex, setSnippetIndex] = useState(0);
  const snippet = snippets[snippetIndex] ?? snippets[0];
  const envName = created.item.key_type === "ingest" ? "SPANPORT_DATA_KEY" : "SPANPORT_ADMIN_KEY";
  return (
    <section className="panel created-key" aria-label="New key">
      <h2 className="panel-title">{created.item.name} is ready</h2>
      <div role="alert" className="banner banner-warning">
        <strong>Copy this key now. You won&apos;t see it again.</strong> Spanport keeps only a hash.
        If you lose it, revoke it and create a new one.
      </div>
      <div className="created-key-row">
        <code className="created-key-value">{created.key}</code>
        <Button
          variant="primary"
          onClick={() => {
            copyKey.copy(created.key);
            onCopied();
          }}
        >
          {copyKey.copied ? "Copied" : "Copy key"}
        </Button>
      </div>
      {copyKey.failed && (
        <p role="alert" className="field-error">
          The browser blocked clipboard access. Select the key and copy it instead.
        </p>
      )}
      <div className="tabs">
        {snippets.map((example, index) => (
          <button
            key={example.label}
            type="button"
            className="tab"
            aria-pressed={index === snippetIndex}
            onClick={() => {
              setSnippetIndex(index);
            }}
          >
            {example.label}
          </button>
        ))}
      </div>
      {snippet && <pre className="snippet">{snippet.code}</pre>}
      <p className="text-secondary text-sm">
        Put the key in your app&apos;s environment as {envName}, never in code.
      </p>
      <div>
        <Button onClick={onDone}>I&apos;ve copied it</Button>
      </div>
    </section>
  );
}
