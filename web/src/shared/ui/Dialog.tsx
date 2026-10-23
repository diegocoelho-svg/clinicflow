import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

let modals: HTMLDialogElement[] = [];
let bodyOverflow = '';
const originalVisibility = new Map<Element, string | null>();

function updateModalVisibility() {
  const top = modals.at(-1);
  if (top) {
    document.body.style.overflow = 'hidden';
    for (const node of Array.from(document.body.children)) {
      if (!originalVisibility.has(node))
        originalVisibility.set(node, node.getAttribute('aria-hidden'));
      if (node === top) node.removeAttribute('aria-hidden');
      else node.setAttribute('aria-hidden', 'true');
    }
  } else {
    document.body.style.overflow = bodyOverflow;
    for (const [node, value] of originalVisibility) {
      if (value === null) node.removeAttribute('aria-hidden');
      else node.setAttribute('aria-hidden', value);
    }
    originalVisibility.clear();
  }
}

export function Dialog({
  title,
  children,
  close,
  busy = false,
  drawer = false,
  navigation,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  busy?: boolean;
  drawer?: boolean;
  navigation?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current!;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (modals.length === 0) bodyOverflow = document.body.style.overflow;
    modals.push(dialog);
    updateModalVisibility();
    dialog.showModal();
    return () => {
      dialog.close();
      modals = modals.filter((modal) => modal !== dialog);
      updateModalVisibility();
      if (trigger?.isConnected && !trigger.closest('[aria-hidden="true"]')) trigger.focus();
    };
  }, []);
  return createPortal(
    <dialog
      ref={ref}
      className={`app-dialog ${drawer ? 'record-drawer' : ''}`}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) close();
      }}
    >
      <header className="dialog-heading">
        <h2 id={titleId}>{title}</h2>
        <div className="dialog-navigation">
          {navigation}
          <button
            className="button subtle"
            type="button"
            disabled={busy}
            onClick={close}
            aria-label={`Fechar ${title.toLowerCase()}`}
          >
            Fechar <span aria-hidden="true">×</span>
          </button>
        </div>
      </header>
      <div className="dialog-content">{children}</div>
    </dialog>,
    document.body,
  );
}
