import { useState, useMemo, useEffect } from 'react'
import './App.css'
import DateDropdown from './DateDropdown'
import DateRangePicker from './DateRangePicker'
import MagicRings from './MagicRings'
import Login from './Login'
import { translations } from './i18n'

// Reads from Vite env (VITE_API_URL) in production; falls back to localhost for dev
const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

const buildDateOptions = (daysBack = 120, lang = 'ar') => {
  const t = translations[lang]
  const locale = lang === 'ar' ? 'ar-EG' : 'en-US'
  const opts = []
  const now = new Date()
  for (let i = 0; i < daysBack; i++) {
    const d = new Date(now)
    d.setDate(now.getDate() - i)
    const yyyy = d.getFullYear()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    const iso = `${yyyy}-${mm}-${dd}`
    const label = d.toLocaleDateString(locale, {
      weekday: 'short',
      day: 'numeric',
      month: 'long',
    })
    const sublabel = i === 0 ? t.today : i === 1 ? t.yesterday : t.daysAgo(i, yyyy)
    opts.push({ value: iso, label, sublabel })
  }
  return opts
}

function App() {
  // Language state (persists in localStorage)
  const [lang, setLang] = useState(() => localStorage.getItem('app-lang') || 'ar')
  const t = translations[lang]

  // Theme state (light / dark)
  const [theme, setTheme] = useState(() => localStorage.getItem('app-theme') || 'dark')
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('app-theme', theme)
  }, [theme])
  const toggleTheme = () => setTheme(theme === 'dark' ? 'light' : 'dark')

  // Auth state
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem('auth_user')
      return raw ? JSON.parse(raw) : null
    } catch { return null }
  })
  const handleLogout = () => {
    localStorage.removeItem('auth_user')
    setUser(null)
  }

  // Apply <html> direction/lang based on selected language
  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr'
    localStorage.setItem('app-lang', lang)
  }, [lang])

  const toggleLang = () => setLang(lang === 'ar' ? 'en' : 'ar')

  // Search type: 'user' | 'keyword' | 'hashtag'
  const [searchType, setSearchType] = useState('user')
  const [username, setUsername] = useState('achetou_tah')
  const [limit, setLimit] = useState(10)
  const dateOptions = useMemo(() => buildDateOptions(120, lang), [lang])
  const [fromDate, setFromDate] = useState(dateOptions[6].value)
  const [toDate, setToDate]     = useState(dateOptions[0].value)
  const [loading, setLoading] = useState(false)
  const [posts, setPosts] = useState([])
  const [error, setError] = useState('')

  // Build URL based on search type
  const buildRequestUrl = (forExport = false, format = 'csv') => {
    const [s, e] = fromDate <= toDate ? [fromDate, toDate] : [toDate, fromDate]
    const base = new URLSearchParams({
      limit: String(limit),
      start_date: s,
      end_date: e,
    })
    if (searchType === 'user') {
      const cleanU = username.trim().replace(/^@/, '')
      base.set('username', cleanU)
      const path = forExport ? '/api/export' : '/api/posts'
      if (forExport) base.set('format', format)
      return `${API_URL}${path}?${base.toString()}`
    }
    // keyword or hashtag
    const cleanQ = username.trim().replace(/^[@#]/, '')
    base.set('query', cleanQ)
    base.set('mode', searchType)  // 'keyword' or 'hashtag'
    // No export endpoint for search yet - use /api/search for both
    return `${API_URL}/api/search?${base.toString()}`
  }

  const buildQuery = () => buildRequestUrl(false)

  const sleep = (ms) => new Promise(r => setTimeout(r, ms))
  const tryFetch = async () => {
    const res = await fetch(buildRequestUrl(false))
    return await res.json()
  }

  const fetchPosts = async () => {
    if (!username.trim()) {
      setError(searchType === 'user' ? t.enterUsername : t.enterQuery)
      return
    }
    setLoading(true)
    setError('')
    setPosts([])

    const maxAttempts = 3
    let lastError = ''
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        const data = await tryFetch()
        if (!data.error && data.posts && data.posts.length > 0) {
          setPosts(data.posts)
          setError('')
          setLoading(false)
          return
        }
        if (!data.error && (!data.posts || data.posts.length === 0)) {
          setError(t.noPosts)
          setLoading(false)
          return
        }
        const errStr = String(data.error || '')
        lastError = errStr
        if (/Suspended|موقوف|not found|غير موجود|Protected|خاص|الكوكيز/.test(errStr)) {
          setError(errStr)
          setLoading(false)
          return
        }
        if (attempt < maxAttempts) {
          await sleep(attempt * 4000)
          continue
        }
      } catch (err) {
        lastError = t.backendError
        if (attempt < maxAttempts) {
          await sleep(2000)
          continue
        }
      }
    }
    setError(lastError || t.fetchFailed)
    setLoading(false)
  }

  const downloadFile = (format) => {
    if (!username.trim()) return
    if (searchType !== 'user') {
      // No export for search yet - download what we already have on client
      const rows = posts.map(p => ({
        username: p.username, post_url: p.post_url,
        caption: p.caption, likes: p.likes, retweets: p.retweets,
        comments: p.comments, views: p.views, created_at: p.created_at,
      }))
      if (format === 'csv') {
        const header = Object.keys(rows[0] || {}).join(',')
        const csv = [header, ...rows.map(r => Object.values(r).map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(','))].join('\n')
        const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' })
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `search_${searchType}_${username}.csv`
        a.click()
      } else {
        const json = JSON.stringify(rows, null, 2)
        const blob = new Blob([json], { type: 'application/json' })
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `search_${searchType}_${username}.json`
        a.click()
      }
      return
    }
    // user mode → use backend export endpoint
    const url = buildRequestUrl(true, format)
    window.open(url, '_blank')
  }

  // Show the FULL number (e.g. 1900 instead of "1.9K", 2,500,000 instead of "2.5M")
  // with grouping separators for readability.
  const formatNumber = (n) => {
    const num = Number(n) || 0
    return num.toLocaleString('en-US')
  }

  const formatDate = (iso) => {
    if (!iso) return ''
    try {
      const d = new Date(iso)
      return d.toLocaleString('ar-EG', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    } catch { return iso }
  }

  const detectDir = (text) => {
    if (!text) return 'ltr'
    const rtl = (text.match(/[\u0591-\u07FF\uFB1D-\uFDFD\uFE70-\uFEFC]/g) || []).length
    const ltr = (text.match(/[A-Za-z]/g) || []).length
    if (rtl === 0 && ltr === 0) return 'ltr'
    return rtl > ltr ? 'rtl' : 'ltr'
  }

  // ----- Split posts into 3 categories -----
  const videoPosts   = posts.filter(p => p.has_video)
  const retweetPosts = posts.filter(p => !p.has_video && (p.is_retweet || p.is_quote))
  const regularPosts = posts.filter(p => !p.has_video && !p.is_retweet && !p.is_quote)

  // ----- Analytics -----
  const analytics = useMemo(() => {
    if (posts.length === 0) return null
    const totals = posts.reduce((acc, p) => ({
      likes:    acc.likes    + (p.likes    || 0),
      retweets: acc.retweets + (p.retweets || 0),
      comments: acc.comments + (p.comments || 0),
      views:    acc.views    + (p.views    || 0),
    }), { likes: 0, retweets: 0, comments: 0, views: 0 })

    const avg = {
      likes:    Math.round(totals.likes    / posts.length),
      retweets: Math.round(totals.retweets / posts.length),
      comments: Math.round(totals.comments / posts.length),
      views:    Math.round(totals.views    / posts.length),
    }

    const maxViews = Math.max(...posts.map(p => p.views || 0)) || 1
    const engagement = totals.views > 0
      ? ((totals.likes + totals.retweets + totals.comments) / totals.views * 100).toFixed(2)
      : '0'

    return { totals, avg, maxViews, engagement }
  }, [posts])

  const periodLabel = (() => {
    try {
      const locale = lang === 'ar' ? 'ar-EG' : 'en-US'
      const s = new Date(fromDate).toLocaleDateString(locale, { day: 'numeric', month: 'short' })
      const e = new Date(toDate).toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' })
      if (fromDate === toDate) return e
      return t.periodFrom(s, e)
    } catch { return `${fromDate} - ${toDate}` }
  })()

  // (legacy card renderer removed - we now render posts in a single table)
  /* eslint-disable */
  const _legacy_renderPostCard = (post, i) => (
    <div
      className="post-card"
      key={`${post.post_url}-${i}`}
    >
      <div className="post-header">
        <span className="username">@{post.username}</span>
        <span className="date">{formatDate(post.created_at)}</span>
      </div>

      {(post.is_retweet || post.is_quote || post.has_video) && (
        <div className="type-badges">
          {post.has_video && <span className="badge badge-video">{t.badgeVideo}</span>}
          {post.is_retweet && <span className="badge badge-rt">{t.badgeRetweet}</span>}
          {post.is_quote && !post.is_retweet && <span className="badge badge-quote">{t.badgeQuote}</span>}
        </div>
      )}

      {post.caption && (
        <p className="caption" dir={detectDir(post.caption)}>{post.caption}</p>
      )}

      {post.quoted_caption && post.quoted_author && (
        <div className="quoted-box" dir={detectDir(post.quoted_caption)}>
          <div className="quoted-author">@{post.quoted_author}</div>
          <div className="quoted-text">
            {post.quoted_caption.slice(0, 200)}{post.quoted_caption.length > 200 ? '…' : ''}
          </div>
        </div>
      )}

      {post.image_urls && post.image_urls.length > 0 && (
        <div className="images-container">
          {post.image_urls.map((img, j) => (
            <img key={j} src={img} alt="post" loading="lazy" />
          ))}
        </div>
      )}

      {post.video_urls && post.video_urls.length > 0 && (
        <a href={post.video_urls[0]} target="_blank" rel="noreferrer" className="video-link">
          {t.watchVideo}
        </a>
      )}

      <div className="stats" dir="ltr">
        <div className="stat" title={t.statLikes}>
          <span>❤️</span><span>{formatNumber(post.likes)}</span>
        </div>
        <div className="stat" title={t.statComments}>
          <span>💬</span><span>{formatNumber(post.comments)}</span>
        </div>
        <div className="stat" title={t.statRetweets}>
          <span>🔁</span><span>{formatNumber(post.retweets)}</span>
        </div>
        <div className="stat" title={t.statViews}>
          <span>📊</span><span>{formatNumber(post.views || 0)}</span>
        </div>
      </div>

      {post.post_url && (
        <a href={post.post_url} target="_blank" rel="noreferrer" className="post-link">
          {t.openOnX}
        </a>
      )}
    </div>
  )

  const renderSection = (title, icon, items) => {
    if (items.length === 0) return null
    return (
      <section className="results-section">
        <h3 className="section-title">
          <span className="section-icon">{icon}</span>
          {title}
          <span className="section-count">({items.length})</span>
        </h3>
        <div className="posts-grid">
          {items.map(renderPostCard)}
        </div>
      </section>
    )
  }

  // ── Show login page if not authenticated ──
  // (Placed AFTER all hooks to respect Rules of Hooks)
  if (!user) {
    return (
      <Login
        onLogin={setUser}
        lang={lang}
        onToggleLang={toggleLang}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
    )
  }

  return (
    <div className="app">
      {/* MagicRings as full-page background (fixed, behind everything) */}
      <div className="page-rings-bg" aria-hidden="true">
        <MagicRings
          color="#38bdf8"
          colorTwo="#f472b6"
          ringCount={8}
          speed={0.4}
          attenuation={9}
          lineThickness={1.5}
          baseRadius={0.3}
          radiusStep={0.09}
          scaleRate={0.08}
          opacity={0.55}
          noiseAmount={0.05}
          ringGap={1.5}
          followMouse={true}
          mouseInfluence={0.08}
          hoverScale={1.05}
          parallax={0.05}
          clickBurst={false}
        />
      </div>

      <header className="hero">
        {/* Top action toolbar (theme + lang + logout grouped together) */}
        <div className="hero-actions">
          <button
            className="hero-action-btn lang-switch"
            onClick={toggleLang}
            title={t.langSwitchLabel}
            aria-label={t.langSwitchLabel}
          >
            <span className="lang-switch-flag">🌐</span>
            <span className="lang-switch-text">{t.langSwitch}</span>
          </button>

          <button
            className="hero-action-btn theme-switch"
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>

          <button
            className="hero-action-btn logout-btn"
            onClick={handleLogout}
            title={lang === 'ar' ? 'تسجيل الخروج' : 'Logout'}
          >
            <span>🚪</span>
            <span>{lang === 'ar' ? 'خروج' : 'Logout'}</span>
          </button>
        </div>

        <div className="hero-dots-pattern" aria-hidden="true"></div>
        <div className="hero-content">
          <h1 className="hero-title">
            <span className="hero-title-x">X</span>
            <span className="hero-title-rest"> Posts Scraper</span>
            <span className="hero-version">v1.0</span>
          </h1>
          <p className="hero-subtitle">{t.appTagline}</p>
          <div className="hero-badges">
            <span className="hero-badge">{t.badgeFast}</span>
            <span className="hero-badge">{t.badgeAccurate}</span>
            <span className="hero-badge">{t.badgeSafe}</span>
            <span className="hero-badge">{t.badgeReliable}</span>
          </div>
          <div className="hero-progress">
            <span className="hero-progress-bar hero-progress-bar-1"></span>
            <span className="hero-progress-bar hero-progress-bar-2"></span>
            <span className="hero-progress-bar hero-progress-bar-3"></span>
          </div>
        </div>
        <div className="hero-logo" aria-hidden="true">
          <div className="hero-logo-glow"></div>
          <div className="hero-logo-card">
            <svg viewBox="0 0 24 24" className="hero-logo-svg" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.46 6c-.77.35-1.6.58-2.46.69.88-.53 1.56-1.37 1.88-2.38-.83.5-1.75.85-2.72 1.05C18.37 4.5 17.26 4 16 4c-2.35 0-4.27 1.92-4.27 4.29 0 .34.04.67.11.98C8.28 9.09 5.11 7.38 3 4.79c-.37.63-.58 1.37-.58 2.15 0 1.49.75 2.81 1.91 3.56-.71 0-1.37-.2-1.95-.5v.03c0 2.08 1.48 3.82 3.44 4.21a4.22 4.22 0 0 1-1.93.07 4.28 4.28 0 0 0 4 2.98 8.521 8.521 0 0 1-5.33 1.84c-.34 0-.68-.02-1.02-.06C3.44 20.29 5.7 21 8.12 21 16 21 20.33 14.46 20.33 8.79c0-.19 0-.37-.01-.56.84-.6 1.56-1.36 2.14-2.23z" />
            </svg>
          </div>
        </div>
      </header>

      <div className="search-card">
        <div className="input-group">
          <label>{t.searchTypeLabel}</label>
          <select
            className="search-type-select"
            value={searchType}
            onChange={(e) => setSearchType(e.target.value)}
          >
            <option value="user">👤 {t.searchTypeUser}</option>
            <option value="keyword">🔤 {t.searchTypeKeyword}</option>
            <option value="hashtag"># {t.searchTypeHashtag}</option>
          </select>
        </div>

        <div className="input-group">
          <label>
            {searchType === 'user' ? t.queryLabelUser
              : searchType === 'hashtag' ? t.queryLabelHashtag
              : t.queryLabelKeyword}
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder={
              searchType === 'user' ? t.queryPhUser
              : searchType === 'hashtag' ? t.queryPhHashtag
              : t.queryPhKeyword
            }
            onKeyDown={(e) => e.key === 'Enter' && fetchPosts()}
          />
        </div>

        <div className="input-group input-group-wide">
          <label>📅 {t.fromDate.replace('📅 ', '')} — {t.toDate.replace('📅 ', '')}</label>
          <DateRangePicker
            startDate={fromDate}
            endDate={toDate}
            onApply={(s, e) => {
              setFromDate(s)
              setToDate(e)
            }}
            labels={{
              start:   lang === 'ar' ? 'تاريخ البداية' : 'Start Date',
              end:     lang === 'ar' ? 'تاريخ النهاية' : 'End Date',
              apply:   lang === 'ar' ? 'تطبيق' : 'Apply',
              cancel:  lang === 'ar' ? 'إلغاء' : 'Cancel',
            }}
          />
        </div>

        <div className="input-group">
          <label>{t.postsCount}</label>
          <input
            type="number"
            value={limit}
            min="1"
            max="2000"
            onChange={(e) => setLimit(Number(e.target.value))}
          />
        </div>

        <button className="fetch-btn" onClick={fetchPosts} disabled={loading}>
          {loading ? t.loadingBtn : t.startBtn}
        </button>
      </div>

      {loading && (
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <div className="loading-text">
            {t.loadingText}
            <span className="loading-dots">
              <span></span><span></span><span></span>
            </span>
          </div>
        </div>
      )}

      {!loading && error && <div className="error-msg">⚠️ {error}</div>}

      {!loading && posts.length > 0 && (
        <>
          <div className="results-header">
            <h2>
              ✅ {t.extracted} {posts.length} {t.post}
              <span className="filter-badge"> · {periodLabel}</span>
            </h2>
            <div className="export-buttons">
              <button onClick={() => downloadFile('csv')}>{t.downloadCsv}</button>
              <button onClick={() => downloadFile('xlsx')}>{t.downloadExcel}</button>
            </div>
          </div>

          {/* Posts table */}
          <div className="posts-table-wrap">
            <table className="posts-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{lang === 'ar' ? 'النص' : 'Text'}</th>
                  <th>{lang === 'ar' ? 'الصورة' : 'Image'}</th>
                  <th title={t.statLikes}>❤️</th>
                  <th title={t.statComments}>💬</th>
                  <th title={t.statRetweets}>🔁</th>
                  <th title={t.statViews}>📊</th>
                  <th>{lang === 'ar' ? 'التاريخ' : 'Date'}</th>
                  <th>{lang === 'ar' ? 'النوع' : 'Type'}</th>
                  <th>{lang === 'ar' ? 'الرابط' : 'Link'}</th>
                </tr>
              </thead>
              <tbody>
                {posts.map((post, i) => {
                  const typeLabel = post.has_video
                    ? (lang === 'ar' ? 'فيديو' : 'Video')
                    : post.is_retweet
                      ? (lang === 'ar' ? 'إعادة' : 'Retweet')
                      : post.is_quote
                        ? (lang === 'ar' ? 'اقتباس' : 'Quote')
                        : (lang === 'ar' ? 'بوست' : 'Post')
                  const typeClass = post.has_video
                    ? 'pt-video'
                    : post.is_retweet ? 'pt-rt' : post.is_quote ? 'pt-quote' : 'pt-post'

                  return (
                    <tr key={`${post.post_url}-${i}`}>
                      <td className="td-num">{i + 1}</td>
                      <td className="td-caption">
                        <div className="td-caption-inner" dir={detectDir(post.caption)}>
                          {post.caption || <span className="td-empty">—</span>}
                        </div>
                      </td>
                      <td className="td-thumb">
                        {post.image_urls && post.image_urls.length > 0 ? (
                          <a href={post.image_urls[0]} target="_blank" rel="noreferrer">
                            <img src={post.image_urls[0]} alt="" loading="lazy" />
                            {post.image_urls.length > 1 && (
                              <span className="td-thumb-count">+{post.image_urls.length - 1}</span>
                            )}
                          </a>
                        ) : (
                          <span className="td-empty">—</span>
                        )}
                      </td>
                      <td className="td-num">{formatNumber(post.likes || 0)}</td>
                      <td className="td-num">{formatNumber(post.comments || 0)}</td>
                      <td className="td-num">{formatNumber(post.retweets || 0)}</td>
                      <td className="td-num">{formatNumber(post.views || 0)}</td>
                      <td className="td-date">{formatDate(post.created_at)}</td>
                      <td className="td-type">
                        <span className={`pt-badge ${typeClass}`}>{typeLabel}</span>
                      </td>
                      <td className="td-link">
                        {post.post_url && (
                          <a href={post.post_url} target="_blank" rel="noreferrer" className="td-link-btn" title={t.openOnX}>
                            🔗
                          </a>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

export default App
