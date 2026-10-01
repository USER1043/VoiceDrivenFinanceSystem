import { type ReactNode, useEffect, useRef } from 'react'

/** Native <dialog>: focus trapping, Escape to close and the backdrop come for free. */
export default function Modal({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const dialog = ref.current
    if (dialog && !dialog.open) dialog.showModal()
    return () => dialog?.close()
  }, [])

  return (
    <dialog
      ref={ref}
      className="sheet"
      aria-label={title}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose() // backdrop tap
      }}
    >
      <div className="sheet-head">
        <h2>{title}</h2>
        <button type="button" className="icon-button" aria-label="Close" onClick={onClose}>
          ✕
        </button>
      </div>
      {children}
    </dialog>
  )
}
