import { useState, useEffect, useRef } from 'react'
import './DateDropdown.css'

/**
 * Custom date dropdown - clean, styled, and consistent.
 *
 * Props:
 *  value:    selected value string
 *  onChange: (newValue) => void
 *  options:  [{ value, label, sublabel }]
 */
export default function DateDropdown({ value, onChange, options }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  // Close when clicking outside
  useEffect(() => {
    const handle = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener('mousedown', handle)
      return () => document.removeEventListener('mousedown', handle)
    }
  }, [open])

  const selected = options.find(o => o.value === value)

  return (
    <div className={`dd ${open ? 'dd-open' : ''}`} ref={ref}>
      <button
        type="button"
        className="dd-trigger"
        onClick={() => setOpen(!open)}
      >
        <div className="dd-trigger-content">
          <span className="dd-trigger-main">
            {selected?.label || 'اختر'}
          </span>
          {selected?.sublabel && (
            <span className="dd-trigger-sub">{selected.sublabel}</span>
          )}
        </div>
        <span className={`dd-arrow ${open ? 'dd-arrow-up' : ''}`}>▾</span>
      </button>

      {open && (
        <div className="dd-menu">
          {options.map((opt) => {
            const isSelected = opt.value === value
            return (
              <button
                key={opt.value}
                type="button"
                className={`dd-option ${isSelected ? 'dd-option-selected' : ''}`}
                onClick={() => {
                  onChange(opt.value)
                  setOpen(false)
                }}
              >
                <div className="dd-option-main">{opt.label}</div>
                {opt.sublabel && (
                  <div className="dd-option-sub">{opt.sublabel}</div>
                )}
                {isSelected && <span className="dd-check">✓</span>}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
