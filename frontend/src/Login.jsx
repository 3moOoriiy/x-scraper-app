import { useState } from 'react'
import './Login.css'

/**
 * Simple email/password login screen.
 * Authentication is client-side only (stored in localStorage).
 * Demo credentials accepted: any non-empty email + password (min 4 chars).
 */
export default function Login({ onLogin, lang = 'ar', onToggleLang, theme = 'dark', onToggleTheme }) {
  const [mode, setMode]         = useState('signin')   // 'signin' | 'signup'
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [name, setName]         = useState('')
  const [showPwd, setShowPwd]   = useState(false)
  const [error, setError]       = useState('')
  const [busy, setBusy]         = useState(false)

  const t = lang === 'ar' ? {
    welcome:        'مرحباً بعودتك',
    subtitle:       'سجّل دخولك لاستكمال استخراج بوستات X',
    welcomeNew:     'إنشاء حساب جديد',
    subtitleNew:    'أنشئ حسابك للبدء',
    emailLabel:     'البريد الإلكتروني',
    emailPh:        'name@example.com',
    nameLabel:      'الاسم',
    namePh:         'محمد أحمد',
    pwdLabel:       'كلمة المرور',
    pwdPh:          '••••••••',
    signIn:         'تسجيل الدخول',
    signUp:         'إنشاء الحساب',
    loading:        '⏳ جاري التحقق...',
    noAccount:      'ليس لديك حساب؟',
    haveAccount:    'لديك حساب بالفعل؟',
    createOne:      'أنشئ حساباً',
    signInLink:     'تسجيل الدخول',
    invalidEmail:   'البريد الإلكتروني غير صحيح',
    invalidPwd:     'كلمة المرور قصيرة (4 أحرف على الأقل)',
    invalidName:    'من فضلك أدخل اسمك',
    forgotPwd:      'نسيت كلمة المرور؟',
    or:             'أو',
    appName:        'X Posts Scraper',
    tagline:        'استخراج آخر البوستات من حسابات X',
  } : {
    welcome:        'Welcome back',
    subtitle:       'Sign in to continue scraping X posts',
    welcomeNew:     'Create your account',
    subtitleNew:    'Get started in seconds',
    emailLabel:     'Email',
    emailPh:        'name@example.com',
    nameLabel:      'Full name',
    namePh:         'John Doe',
    pwdLabel:       'Password',
    pwdPh:          '••••••••',
    signIn:         'Sign in',
    signUp:         'Create account',
    loading:        '⏳ Verifying...',
    noAccount:      "Don't have an account?",
    haveAccount:    'Already have an account?',
    createOne:      'Sign up',
    signInLink:     'Sign in',
    invalidEmail:   'Invalid email address',
    invalidPwd:     'Password too short (min 4 chars)',
    invalidName:    'Please enter your name',
    forgotPwd:      'Forgot password?',
    or:             'or',
    appName:        'X Posts Scraper',
    tagline:        'Extract latest posts from X (Twitter) accounts',
  }

  const validate = () => {
    const emailRx = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRx.test(email.trim())) return t.invalidEmail
    if (password.length < 4)         return t.invalidPwd
    if (mode === 'signup' && !name.trim()) return t.invalidName
    return null
  }

  const submit = async (e) => {
    e.preventDefault()
    const err = validate()
    if (err) { setError(err); return }
    setBusy(true)
    setError('')
    // Simulated auth latency
    await new Promise(r => setTimeout(r, 600))
    const user = {
      email: email.trim().toLowerCase(),
      name: (name.trim() || email.split('@')[0]),
      loginAt: Date.now(),
    }
    localStorage.setItem('auth_user', JSON.stringify(user))
    setBusy(false)
    onLogin(user)
  }

  return (
    <div className="login-page">
      {/* Theme + language switches in top corner */}
      <div className="login-top-actions">
        {onToggleTheme && (
          <button
            type="button"
            className="login-icon-btn"
            onClick={onToggleTheme}
            title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        )}
        {onToggleLang && (
          <button
            type="button"
            className="login-icon-btn"
            onClick={onToggleLang}
            title="Language"
            aria-label="Toggle language"
          >
            <span>🌐</span>
            <span style={{ fontSize: '0.75rem', marginInlineStart: 4 }}>
              {lang === 'ar' ? 'EN' : 'ع'}
            </span>
          </button>
        )}
      </div>

      {/* Left: brand panel */}
      <div className="login-brand">
        <div className="login-brand-content">
          <div className="login-logo">
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.46 6c-.77.35-1.6.58-2.46.69.88-.53 1.56-1.37 1.88-2.38-.83.5-1.75.85-2.72 1.05C18.37 4.5 17.26 4 16 4c-2.35 0-4.27 1.92-4.27 4.29 0 .34.04.67.11.98C8.28 9.09 5.11 7.38 3 4.79c-.37.63-.58 1.37-.58 2.15 0 1.49.75 2.81 1.91 3.56-.71 0-1.37-.2-1.95-.5v.03c0 2.08 1.48 3.82 3.44 4.21a4.22 4.22 0 0 1-1.93.07 4.28 4.28 0 0 0 4 2.98 8.521 8.521 0 0 1-5.33 1.84c-.34 0-.68-.02-1.02-.06C3.44 20.29 5.7 21 8.12 21 16 21 20.33 14.46 20.33 8.79c0-.19 0-.37-.01-.56.84-.6 1.56-1.36 2.14-2.23z"/>
            </svg>
          </div>
          <h1 className="login-brand-title">{t.appName}</h1>
          <p className="login-brand-tagline">{t.tagline}</p>
          <ul className="login-features">
            <li>⚡ {lang === 'ar' ? 'سريع وموثوق' : 'Fast & reliable'}</li>
            <li>🎯 {lang === 'ar' ? 'بيانات دقيقة 100%' : '100% accurate data'}</li>
            <li>📊 {lang === 'ar' ? 'تحليلات تلقائية' : 'Built-in analytics'}</li>
            <li>📥 {lang === 'ar' ? 'تصدير CSV / Excel' : 'CSV / Excel export'}</li>
          </ul>
        </div>
      </div>

      {/* Right: form panel */}
      <div className="login-form-panel">
        <form className="login-form" onSubmit={submit}>
          <h2 className="login-title">
            {mode === 'signin' ? t.welcome : t.welcomeNew}
          </h2>
          <p className="login-subtitle">
            {mode === 'signin' ? t.subtitle : t.subtitleNew}
          </p>

          {mode === 'signup' && (
            <div className="login-field">
              <label>{t.nameLabel}</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">👤</span>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder={t.namePh}
                  autoComplete="name"
                />
              </div>
            </div>
          )}

          <div className="login-field">
            <label>{t.emailLabel}</label>
            <div className="login-input-wrap">
              <span className="login-input-icon">✉️</span>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder={t.emailPh}
                autoComplete="email"
                required
              />
            </div>
          </div>

          <div className="login-field">
            <label>{t.pwdLabel}</label>
            <div className="login-input-wrap">
              <span className="login-input-icon">🔒</span>
              <input
                type={showPwd ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder={t.pwdPh}
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                required
              />
              <button
                type="button"
                className="login-pwd-toggle"
                onClick={() => setShowPwd(!showPwd)}
                tabIndex={-1}
                aria-label="Show/Hide password"
              >
                {showPwd ? '🙈' : '👁'}
              </button>
            </div>
          </div>

          {error && <div className="login-error">⚠️ {error}</div>}

          <button type="submit" className="login-submit" disabled={busy}>
            {busy ? t.loading : (mode === 'signin' ? t.signIn : t.signUp)}
          </button>
        </form>
      </div>
    </div>
  )
}
