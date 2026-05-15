import { useState, useEffect, useRef } from 'react'
import './DateRangePicker.css'

const MONTHS_EN = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
const MONTHS_LONG_EN = ['January','February','March','April','May','June','July','August','September','October','November','December']
const WEEKDAYS = ['S','M','T','W','T','F','S']

/**
 * Two-month side-by-side date range picker - matches the screenshot.
 * Glass / transparent dark theme.
 *
 * Props:
 *   startDate, endDate: 'YYYY-MM-DD'
 *   onApply: (start, end) => void
 *   trigger: optional element to render as the trigger button (otherwise default)
 *   labels: { start, end, apply, cancel } for i18n
 */
export default function DateRangePicker({
  startDate,
  endDate,
  onApply,
  labels = {
    start: 'Start Date',
    end:   'End Date',
    apply: 'Apply',
    cancel: 'Cancel',
    trigger: 'Select date range',
  },
}) {
  const [open, setOpen] = useState(false)
  const [openDirection, setOpenDirection] = useState('down') // 'down' | 'up'
  const wrapperRef = useRef(null)
  const triggerRef = useRef(null)

  // Temp selections inside the popover (committed only on Apply)
  const [tempStart, setTempStart] = useState(startDate)
  const [tempEnd, setTempEnd]     = useState(endDate)

  // Visible month for each pane
  const initStart = new Date(startDate)
  const initEnd   = new Date(endDate)
  const [startView, setStartView] = useState({
    y: initStart.getFullYear(),
    m: initStart.getMonth(),
  })
  const [endView, setEndView] = useState({
    y: initEnd.getFullYear(),
    m: initEnd.getMonth(),
  })

  // Reset temp values when the picker opens
  useEffect(() => {
    if (open) {
      setTempStart(startDate)
      setTempEnd(endDate)
      const s = new Date(startDate)
      const e = new Date(endDate)
      setStartView({ y: s.getFullYear(), m: s.getMonth() })
      setEndView({ y: e.getFullYear(), m: e.getMonth() })
    }
  }, [open, startDate, endDate])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handle = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  // Decide whether to open up or down based on available viewport space
  useEffect(() => {
    if (!open || !triggerRef.current) return
    const POPOVER_HEIGHT = 380  // approx height of the popover
    const rect = triggerRef.current.getBoundingClientRect()
    const spaceBelow = window.innerHeight - rect.bottom
    const spaceAbove = rect.top
    if (spaceBelow < POPOVER_HEIGHT && spaceAbove > spaceBelow) {
      setOpenDirection('up')
    } else {
      setOpenDirection('down')
    }
  }, [open])

  // Today (ISO)
  const today = new Date()
  const todayISO = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`

  // Build cells for one month
  const buildCells = (year, month) => {
    const firstOfMonth = new Date(year, month, 1)
    const lastOfMonth  = new Date(year, month + 1, 0)
    const daysInMonth  = lastOfMonth.getDate()
    const startWeekday = firstOfMonth.getDay()

    const cells = []
    // Leading empties for grid alignment
    for (let i = 0; i < startWeekday; i++) cells.push(null)
    for (let d = 1; d <= daysInMonth; d++) {
      const iso = `${year}-${String(month+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`
      cells.push({ day: d, iso })
    }
    return cells
  }

  const handleDayClick = (iso, which) => {
    if (iso > todayISO) return  // disallow future
    if (which === 'start') {
      setTempStart(iso)
      // If start is after end, push end to start
      if (iso > tempEnd) setTempEnd(iso)
    } else {
      setTempEnd(iso)
      if (iso < tempStart) setTempStart(iso)
    }
  }

  const apply = () => {
    onApply(tempStart, tempEnd)
    setOpen(false)
  }

  const cancel = () => setOpen(false)

  const navMonth = (which, delta) => {
    const v = which === 'start' ? startView : endView
    let m = v.m + delta
    let y = v.y
    if (m < 0) { m = 11; y -= 1 }
    if (m > 11) { m = 0; y += 1 }
    if (which === 'start') setStartView({ y, m })
    else                   setEndView({ y, m })
  }

  // Pretty display for the trigger button
  const fmt = (iso) => {
    try {
      const d = new Date(iso)
      return `${MONTHS_EN[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`
    } catch { return iso }
  }

  const renderMonth = (which) => {
    const v = which === 'start' ? startView : endView
    const cells = buildCells(v.y, v.m)
    const selected = which === 'start' ? tempStart : tempEnd
    const monthName = MONTHS_EN[v.m]

    return (
      <div className="drp-month">
        <div className="drp-month-title">{which === 'start' ? labels.start : labels.end}</div>
        <div className="drp-month-nav">
          <button type="button" className="drp-month-label" onClick={() => navMonth(which, 0)}>
            {monthName} {v.y} <span className="drp-month-caret">▾</span>
          </button>
          <div className="drp-month-arrows">
            <button type="button" onClick={() => navMonth(which, -1)} aria-label="Previous">‹</button>
            <button type="button" onClick={() => navMonth(which, +1)} aria-label="Next">›</button>
          </div>
        </div>

        <div className="drp-weekdays">
          {WEEKDAYS.map((w, i) => (<div key={i} className="drp-weekday">{w}</div>))}
        </div>

        <div className="drp-month-label-row">{monthName}</div>

        <div className="drp-grid">
          {cells.map((c, i) => {
            if (!c) return <div key={i} className="drp-cell drp-cell-empty"></div>
            const isSel = c.iso === selected
            const inRange = c.iso >= tempStart && c.iso <= tempEnd && tempStart !== tempEnd
            const isFuture = c.iso > todayISO
            const isToday = c.iso === todayISO

            const cls = [
              'drp-cell',
              isSel ? 'drp-cell-selected' : '',
              !isSel && inRange ? 'drp-cell-inrange' : '',
              isFuture ? 'drp-cell-disabled' : '',
              isToday && !isSel ? 'drp-cell-today' : '',
            ].filter(Boolean).join(' ')

            return (
              <button
                type="button"
                key={i}
                className={cls}
                onClick={() => !isFuture && handleDayClick(c.iso, which)}
                disabled={isFuture}
              >
                {c.day}
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="drp" ref={wrapperRef}>
      <button
        type="button"
        className="drp-trigger"
        onClick={() => setOpen(!open)}
        ref={triggerRef}
      >
        <span className="drp-trigger-icon">📅</span>
        <span className="drp-trigger-text">
          <span>{fmt(startDate)}</span>
          <span className="drp-trigger-sep">—</span>
          <span>{fmt(endDate)}</span>
        </span>
        <span className={`drp-trigger-caret ${open ? 'drp-trigger-caret-up' : ''}`}>▾</span>
      </button>

      {open && (
        <div className={`drp-popover drp-popover-${openDirection}`}>
          <div className="drp-header">
            <div className="drp-mode">
              <span>Fixed</span>
              <span className="drp-mode-caret">▾</span>
            </div>
          </div>

          <div className="drp-months">
            {renderMonth('start')}
            {renderMonth('end')}
          </div>

          <div className="drp-footer">
            <button type="button" className="drp-btn drp-btn-cancel" onClick={cancel}>
              {labels.cancel}
            </button>
            <button type="button" className="drp-btn drp-btn-apply" onClick={apply}>
              {labels.apply}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
