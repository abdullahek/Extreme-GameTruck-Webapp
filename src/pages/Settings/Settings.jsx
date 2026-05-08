import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Header from '../../components/Header/Header'
import './Settings.css'

export default function Settings({ setIsAuthenticated }) {
  const [user, setUser] = useState(null)
  const [settings, setSettings] = useState({
    account_sid: '',
    account_token: '',
    sms_number: '',
    is_number_verified: false
  })
  const [originalSettings, setOriginalSettings] = useState({
    account_sid: '',
    account_token: '',
    sms_number: '',
    is_number_verified: false
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [testing, setTesting] = useState(false)
  const [message, setMessage] = useState('')
  const [showToken, setShowToken] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const userData = localStorage.getItem('user')
    if (userData) {
      setUser(JSON.parse(userData))
      fetchSettings()
    }
  }, [])

  const fetchSettings = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/settings', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        const data = await response.json()
        setSettings(data)
        setOriginalSettings(data)
      }
    } catch (error) {
      console.error('Error fetching settings:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e) => {
    setSettings({
      ...settings,
      [e.target.name]: e.target.value
    })

    // Reset verification if phone number changes
    if (e.target.name === 'sms_number' && e.target.value !== originalSettings.sms_number) {
      setSettings(prev => ({
        ...prev,
        is_number_verified: false
      }))
    }
  }


  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setMessage('')

    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
      })

      const data = await response.json()

      if (response.ok) {
        setMessage('Settings saved successfully! 🎮')
        fetchSettings() // Refresh to get masked token and updated verification status
      } else {
        setMessage(data.message || 'Failed to save settings')
      }
    } catch (error) {
      setMessage('Network error occurred')
    } finally {
      setSaving(false)
    }
  }

  const handleVerifyNumber = async () => {
    setVerifying(true)
    setMessage('')

    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/settings/verify-number', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          account_sid: settings.account_sid,
          account_token: settings.account_token, // Backend will handle masked tokens
          sms_number: settings.sms_number
        })
      })

      const data = await response.json()
      setMessage(data.message)

      if (response.ok && data.valid) {
        const updatedSettings = {
          ...settings,
          is_number_verified: true,
          sms_number: data.formatted_number || settings.sms_number
        }
        setSettings(updatedSettings)
        setOriginalSettings(updatedSettings)

        setMessage('Phone number verified successfully! You can now save your configuration.')
      }
    } catch (error) {
      setMessage('Verification failed - Network error')
    } finally {
      setVerifying(false)
    }
  }

  const handleTestConnection = async () => {
    if (!settings.account_sid || !settings.account_token) {
      setMessage('Please fill in Account SID and Account Token before testing')
      return
    }

    setTesting(true)
    setMessage('')

    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/settings/test-twilio', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          account_sid: settings.account_sid,
          account_token: settings.account_token
        })
      })

      const data = await response.json()
      setMessage(data.message)
    } catch (error) {
      setMessage('Connection test failed')
    } finally {
      setTesting(false)
    }
  }

  

  // Check if all fields are filled and number is verified
  const canSaveConfiguration = () => {
    return settings.account_sid && 
           settings.account_token && 
           settings.sms_number && 
           settings.is_number_verified
  }

  // Skeleton loading components
  const SkeletonSettingCard = () => (
    <div className="skeleton-setting-card">
      <div className="skeleton-card-header">
        <div className="skeleton-card-title"></div>
        <div className="skeleton-badge"></div>
      </div>
      <div className="skeleton-input"></div>
    </div>
  )

  const SkeletonStatusSection = () => (
    <div className="skeleton-status-section">
      <div className="skeleton-status-title"></div>
      <div className="skeleton-status-grid">
        <div className="skeleton-status-item">
          <div className="skeleton-status-label"></div>
          <div className="skeleton-status-value"></div>
        </div>
        <div className="skeleton-status-item">
          <div className="skeleton-status-label"></div>
          <div className="skeleton-status-value"></div>
        </div>
        <div className="skeleton-status-item">
          <div className="skeleton-status-label"></div>
          <div className="skeleton-status-value"></div>
        </div>
      </div>
    </div>
  )

  return (
    <div className="settings-container">
      <div className="settings-background"></div>

      <Header setIsAuthenticated={setIsAuthenticated} />

      <main className="settings-main">
        <div className="settings-content">
          <div className="settings-header-section">
            <h2>⚙️ Game Control Panel</h2>
            <p>Configure your extreme gaming system settings</p>
          </div>

          {message && (
            <div className={`message ${message.includes('successfully') || message.includes('verified') ? 'success' : 'error'}`}>
              {message}
            </div>
          )}

          {loading ? (
            <>
              <div className="settings-grid">
                <SkeletonSettingCard />
                <SkeletonSettingCard />
                <SkeletonSettingCard />
              </div>

              <div className="form-actions">
                <div className="skeleton-button"></div>
              </div>

              <div className="gaming-info">
                <SkeletonStatusSection />
              </div>
            </>
          ) : (
            <>
              <form onSubmit={handleSave} className="settings-form">
                <div className="settings-grid">
                  <div className="setting-card">
                <div className="card-header">
                  <h3>🔑 Account SID</h3>
                  <span className="gaming-badge">SYSTEM ID</span>
                </div>
                <input
                  type="text"
                  name="account_sid"
                  value={settings.account_sid}
                  onChange={handleChange}
                  placeholder="Enter your Account SID"
                  className="gaming-input"
                />
              </div>

              <div className="setting-card">
                <div className="card-header">
                  <h3>🛡️ Account Token</h3>
                  <span className="gaming-badge">SECURE KEY</span>
                </div>
                <div className="token-input-group">
                  <input
                    type={showToken ? "text" : "password"}
                    name="account_token"
                    value={settings.account_token}
                    onChange={handleChange}
                    placeholder="Enter your Account Token"
                    className="gaming-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowToken(!showToken)}
                    className="toggle-btn"
                  >
                    {showToken ? '🙈' : '👁️'}
                  </button>
                </div>
              </div>

              <div className="setting-card">
                <div className="card-header">
                  <h3>📱 SMS Number</h3>
                  <div className="status-section">
                    <span className="gaming-badge">COMM LINK</span>
                    {settings.is_number_verified && (
                      <span className="verified-badge">✅ VERIFIED</span>
                    )}
                  </div>
                </div>
                <div className="sms-input-group">
                  <input
                    type="tel"
                    name="sms_number"
                    value={settings.sms_number}
                    onChange={handleChange}
                    placeholder="+1234567890"
                    className="gaming-input"
                  />
                  {settings.sms_number && settings.account_sid && settings.account_token && !settings.is_number_verified && (
                    <button
                      type="button"
                      onClick={handleVerifyNumber}
                      disabled={verifying}
                      className="verify-btn"
                    >
                      {verifying ? '⏳ VERIFYING...' : '⚡ VERIFY'}
                    </button>
                  )}
                  {settings.is_number_verified && (
                    <button
                      type="button"
                      className="verified-btn"
                      disabled
                    >
                      ✅ VERIFIED
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="form-actions">
                <button
                  type="submit"
                  disabled={saving || !canSaveConfiguration()}
                  className="save-btn"
                >
                  {saving ? '⏳ SAVING...' : '💾 SAVE CONFIGURATION'}
                </button>
            </div>
          </form>

              <div className="gaming-info">
                <div className="info-card">
                  <h4>🎮 Gaming System Status</h4>
                  <div className="status-grid">
                    <div className="status-item">
                      <span>Account:</span>
                      <span className={settings.account_sid ? 'status-active' : 'status-inactive'}>
                        {settings.account_sid ? 'CONNECTED' : 'OFFLINE'}
                      </span>
                    </div>
                    <div className="status-item">
                      <span>Communication:</span>
                      <span className={settings.is_number_verified ? 'status-active' : 'status-inactive'}>
                        {settings.is_number_verified ? 'ONLINE' : 'PENDING'}
                      </span>
                    </div>
                    <div className="status-item">
                      <span>System:</span>
                      <span className="status-active">READY</span>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  )
}