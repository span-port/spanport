import { useState } from "react";

import { Button } from "../../../components/ui/Button";
import { DELETE_CONFIRM_LABEL, REVOKE_CONFIRM_LABEL } from "../../../constants/setup";
import { EMPTY_VALUE } from "../../../constants/ui";
import { maskedKey } from "../../../lib/apiKeys";
import { formatRangeTime } from "../../../lib/formatTime";
import type { KeyListRow } from "../hooks/useKeyList";

interface KeyRowProps {
  row: KeyListRow;
  timeZone: string;
  onRevoke: (keyId: string) => void;
  onRename: (keyId: string, name: string) => Promise<unknown>;
  onDelete: (keyId: string) => void;
}

/**
 * One key: rename it, revoke it, and once revoked delete it from the list. Revoke and delete
 * need a second click, so a stray click can't break an app or lose history.
 */
export function KeyRow({ row, timeZone, onRevoke, onRename, onDelete }: KeyRowProps) {
  const { apiKey, covers, status } = row;
  const [confirming, setConfirming] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [draftName, setDraftName] = useState<string | null>(null);
  const saveName = (name: string) => {
    if (name.trim() === "") return;
    void onRename(apiKey.id, name.trim()).then(() => {
      setDraftName(null);
    });
  };
  return (
    <tr>
      <td>
        {draftName === null ? (
          (apiKey.name ?? EMPTY_VALUE)
        ) : (
          <input
            className="input input-compact"
            aria-label="Key name"
            value={draftName}
            onChange={(event) => {
              setDraftName(event.target.value);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") saveName(draftName);
              if (event.key === "Escape") setDraftName(null);
            }}
          />
        )}
      </td>
      <td className="mono">{maskedKey(apiKey)}</td>
      <td>{covers}</td>
      <td className="mono">{formatRangeTime(Date.parse(apiKey.created_at), timeZone)}</td>
      <td className="mono">
        {apiKey.expires_at ? formatRangeTime(Date.parse(apiKey.expires_at), timeZone) : "Never"}
      </td>
      <td>
        <span className={`status-tag status-${status}`}>{status}</span>
      </td>
      <td className="cell-actions">
        {draftName === null ? (
          <Button
            className="button-small"
            onClick={() => {
              setDraftName(apiKey.name ?? "");
            }}
          >
            Rename
          </Button>
        ) : (
          <>
            <Button
              className="button-small"
              variant="primary"
              onClick={() => {
                saveName(draftName);
              }}
            >
              Save
            </Button>
            <Button
              className="button-small"
              onClick={() => {
                setDraftName(null);
              }}
            >
              Cancel
            </Button>
          </>
        )}
        {status === "active" && draftName === null && (
          <Button
            className="button-small button-danger-text"
            onClick={() => {
              if (confirming) onRevoke(apiKey.id);
              else setConfirming(true);
            }}
          >
            {confirming ? REVOKE_CONFIRM_LABEL : "Revoke"}
          </Button>
        )}
        {status === "revoked" && draftName === null && (
          <Button
            className="button-small button-danger-text"
            onClick={() => {
              if (confirmingDelete) onDelete(apiKey.id);
              else setConfirmingDelete(true);
            }}
          >
            {confirmingDelete ? DELETE_CONFIRM_LABEL : "Delete"}
          </Button>
        )}
      </td>
    </tr>
  );
}
