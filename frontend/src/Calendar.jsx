import { useState } from 'react'
import './Calendar.css'

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]

const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']

/**
 * Calendar component - matches the screenshot style exactly
 *
 * Props:
 *  value:    'YYYY-MM-DD' string
 *  onChange: (newDate: 'YYYY-MM-DD') => void
 */
export default function Calendar({ value, onChange }) {
  // Parse value into a Date object (or use today)
  const initialDate = value ? new Date(value) : new Date()
  const [viewYear, setViewYear]   = useState(initialDate.getFullYear())
  const [viewMonth, setViewMonth] = useState(initialDate.getMonth())

  // Today (for highlighting if needed)
  const today = new Date()
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`

  // Build the 6-week grid
  const firstOfMonth = new Date(viewYear, viewMonth, 1)
  const lastOfMonth  = new Date(viewYear, viewMonth + 1, 0)
  const daysInMonth  = lastOfMonth.getDate()
  const startWeekday = firstOfMonth.getDay()  // 0 = Sunday

  // Previous month's tail
  const prevMonthLast = new Date(viewYear, viewMonth, 0).getDate()

  // Build 42 cells (6 weeks × 7 days)
  const cells = []
  // Leading days (previous month)
  for (let i = startWeekday - 1; i >= 0; i--) {
    cells.push({
      day: prevMonthLast - i,
      currentMonth: false,
      date: null,
    })
  }
  // Current month
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    cells.push({
      day: d,
      currentMonth: true,
      date: dateStr,
    })
  }
  // Trailing days (next month)
  while (cells.length < 42) {
    const lastCurrent = cells[cells.length - 1]
    const nextDay = lastCurrent.currentMonth ? 1 : lastCurrent.day + 1
    cells.push({
      day: nextDay,
      currentMonth: false,
      date: null,
    })
  }

  const goPrev = () => {
    if (viewMonth === 0) {
      setViewMonth(11)
      setViewYear(viewYear - 1)
    } else {
      setViewMonth(viewMonth - 1)
    }
  }

  const goNext = () => {
    if (viewMonth === 11) {
      setViewMonth(0)
      setViewYear(viewYear + 1)
    } else {
      setViewMonth(viewMonth + 1)
    }
  }

  const handlePick = (cell) => {
    if (!cell.currentMonth || !cell.date) return
    onChange(cell.date)
  }

  return (
    <div className="cal" dir="ltr">
      <div className="cal-header">
        <div className="cal-title">
          {MONTHS[viewMonth]} {viewYear}
        </div>
        <div className="cal-nav">
          <button type="button" onClick={goPrev} aria-label="Previous month">▲</button>
          <button type="button" onClick={goNext} aria-label="Next month">▼</button>
        </div>
      </div>

      <div className="cal-weekdays">
        {WEEKDAYS.map((w) => (
          <div key={w} className="cal-weekday">{w}</div>
        ))}
      </div>

      <div className="cal-grid">
        {cells.map((cell, i) => {
          const isSelected = cell.currentMonth && cell.date === value
          const isToday    = cell.currentMonth && cell.date === todayStr
          const isFuture   = cell.currentMonth && cell.date > todayStr
          const cls = [
            'cal-day',
            cell.currentMonth ? '' : 'cal-day-outside',
            isSelected ? 'cal-day-selected' : '',
            isToday && !isSelected ? 'cal-day-today' : '',
            isFuture ? 'cal-day-disabled' : '',
          ].filter(Boolean).join(' ')

          return (
            <button
              type="button"
              key={i}
              className={cls}
              onClick={() => !isFuture && handlePick(cell)}
              disabled={isFuture}
            >
              {cell.day}
            </button>
          )
        })}
      </div>
    </div>
  )
}
