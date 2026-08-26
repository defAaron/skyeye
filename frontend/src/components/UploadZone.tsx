import { useId, useState } from 'react'
import './UploadZone.css'
import { formatBytes } from '../lib/format'

export interface UploadRejection {
  code: 'UNSUPPORTED_TYPE' | 'FILE_TOO_LARGE'
  message: string
}

interface UploadZoneProps {
  allowedTypes: string[]
  maxUploadBytes: number
  /** True while a sample owns the input slot, so only one source can ever be active. */
  disabled: boolean
  onAccept: (file: File) => void
  onReject: (rejection: UploadRejection) => void
}

export default function UploadZone({
  allowedTypes,
  maxUploadBytes,
  disabled,
  onAccept,
  onReject,
}: UploadZoneProps) {
  const [dragging, setDragging] = useState(false)
  const inputId = useId()

  function validate(file: File) {
    // Checked here so the user gets a readable message instead of a bare 413.
    if (!allowedTypes.includes(file.type)) {
      onReject({
        code: 'UNSUPPORTED_TYPE',
        message: `“${file.name}” is ${file.type || 'of an unrecognised type'}.`,
      })
      return
    }
    if (file.size > maxUploadBytes) {
      onReject({
        code: 'FILE_TOO_LARGE',
        message: `“${file.name}” is ${formatBytes(file.size)}, over the ${formatBytes(maxUploadBytes)} upload limit.`,
      })
      return
    }
    onAccept(file)
  }

  function takeFiles(files: FileList | null) {
    const file = files?.[0]
    if (file) validate(file)
  }

  return (
    <div
      className={`dropzone${dragging ? ' dropzone--active' : ''}${disabled ? ' dropzone--disabled' : ''}`}
      onDragOver={(event) => {
        if (disabled) return
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        if (disabled) return
        event.preventDefault()
        setDragging(false)
        takeFiles(event.dataTransfer.files)
      }}
    >
      <p className="dropzone__lead">
        {disabled
          ? 'Clear the selected sample to add your own image instead.'
          : 'Drag a drone-altitude JPEG or PNG here'}
      </p>
      <p className="dropzone__hint">
        Up to {formatBytes(maxUploadBytes)}. The image stays on your machine until you
        run detection.
      </p>
      <input
        id={inputId}
        className="dropzone__input"
        type="file"
        accept={allowedTypes.join(',')}
        disabled={disabled}
        onChange={(event) => {
          takeFiles(event.target.files)
          // Reset so re-picking the same file still fires a change event.
          event.target.value = ''
        }}
      />
      <label className="dropzone__button" htmlFor={inputId}>
        Choose a file
      </label>
    </div>
  )
}
