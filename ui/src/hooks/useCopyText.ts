// Copy text to the clipboard and report how it went.
import { useMutation } from "@tanstack/react-query";

/** `copy(text)` writes to the clipboard; `copied` and `failed` describe the last attempt. */
export function useCopyText() {
  const clipboardWrite = useMutation({
    mutationFn: (text: string) => navigator.clipboard.writeText(text),
  });
  return {
    copy: (text: string) => {
      clipboardWrite.mutate(text);
    },
    copied: clipboardWrite.isSuccess,
    failed: clipboardWrite.isError,
  };
}
