import { useState } from "react";

import { Button } from "../../../components/ui/Button";
import { ErrorBanner } from "../../../components/ui/ErrorBanner";
import { KEY_TABS } from "../../../constants/setup";
import { LATER_RELEASE_NOTE } from "../../../constants/ui";
import { useSessionStore } from "../../../state/sessionStore";
import type { KeyType } from "../api";
import { useDeleteKey, useRenameKey, useRevokeKey } from "../hooks/useApiKeys";
import { useCreateKeyForm } from "../hooks/useCreateKeyForm";
import { useKeyList } from "../hooks/useKeyList";
import { CreateKeyForm } from "./CreateKeyForm";
import { KeyCreatedPanel } from "./KeyCreatedPanel";
import { KeyRow } from "./KeyRow";

/** API keys: create data and admin keys (shown once), see them all, revoke them. */
export function ApiKeysPage() {
  const [keyType, setKeyType] = useState<KeyType>("ingest");
  const [formOpen, setFormOpen] = useState(false);
  const list = useKeyList(keyType);
  const revoke = useRevokeKey();
  const rename = useRenameKey();
  const removeKey = useDeleteKey();
  const form = useCreateKeyForm(keyType);
  const timeZone = useSessionStore((session) => session.timeZone);
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);
  // A new key stays on its own tab until copied or dismissed, so switching tabs can't lose it.
  const createdHere = form.created?.item.key_type === keyType ? form.created : null;
  const switchTab = (next: KeyType) => {
    if (form.created?.item.id === copiedKeyId) form.dismissCreated();
    setKeyType(next);
    setFormOpen(false);
  };
  return (
    <div className="setup-page">
      <header className="page-heading page-heading-row">
        <div>
          <h1 className="page-title">API keys</h1>
          <p className="text-secondary">
            Data keys let apps send logs. Admin keys let scripts and CI read through the API. A key
            is shown once when you create it; Spanport keeps only a hash.
          </p>
        </div>
        {!formOpen && !createdHere && (
          <Button
            variant="primary"
            onClick={() => {
              setFormOpen(true);
            }}
          >
            Create key
          </Button>
        )}
      </header>
      <nav className="tabs" aria-label="Key types">
        {KEY_TABS.map((tab) => (
          <button
            key={tab.keyType}
            type="button"
            className="tab"
            aria-pressed={tab.keyType === keyType}
            disabled={!tab.available}
            title={tab.available ? undefined : LATER_RELEASE_NOTE}
            onClick={() => {
              if (tab.keyType === "ingest" || tab.keyType === "admin") switchTab(tab.keyType);
            }}
          >
            {tab.label}
            {(tab.keyType === "ingest" || tab.keyType === "admin") &&
              ` · ${list.countOf(tab.keyType)}`}
          </button>
        ))}
      </nav>
      {createdHere ? (
        <KeyCreatedPanel
          created={createdHere}
          onCopied={() => {
            setCopiedKeyId(createdHere.item.id);
          }}
          onDone={() => {
            form.dismissCreated();
            setFormOpen(false);
          }}
        />
      ) : (
        formOpen && (
          <CreateKeyForm
            keyType={keyType}
            projects={list.projects}
            form={form}
            onCancel={() => {
              setFormOpen(false);
            }}
          />
        )
      )}
      {list.error && <ErrorBanner error={list.error} />}
      {revoke.error && <ErrorBanner error={revoke.error} />}
      {rename.error && <ErrorBanner error={rename.error} />}
      {removeKey.error && <ErrorBanner error={removeKey.error} />}
      <div className="panel panel-table">
        <table className="key-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Key</th>
              <th>{keyType === "ingest" ? "Project" : "Scopes"}</th>
              <th>Created</th>
              <th>Expires</th>
              <th>Status</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {list.rows.map((row) => (
              <KeyRow
                key={row.apiKey.id}
                row={row}
                timeZone={timeZone}
                onRevoke={revoke.revoke}
                onRename={rename.rename}
                onDelete={removeKey.remove}
              />
            ))}
          </tbody>
        </table>
        {list.loaded && list.rows.length === 0 && (
          <p className="empty-row text-secondary">No keys of this type yet. Create one above.</p>
        )}
      </div>
    </div>
  );
}
