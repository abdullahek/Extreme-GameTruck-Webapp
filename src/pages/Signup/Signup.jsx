import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import './Signup.css'

export default function Signup({ setIsAuthenticated }) {
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    password: '',
    confirmPassword: ''
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [agreedToTerms, setAgreedToTerms] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match')
      setLoading(false)
      return
    }

    if (!agreedToTerms) {
      setError('Please agree to the Terms of Service and Privacy Policy')
      setLoading(false)
      return
    }

    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      })

      const data = await response.json()

      if (response.ok) {
        // Auto login after successful registration
        const loginResponse = await fetch('/api/auth/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            email: formData.email,
            password: formData.password
          }),
        })

        const loginData = await loginResponse.json()
        if (loginResponse.ok) {
          localStorage.setItem('token', loginData.token)
          localStorage.setItem('user', JSON.stringify(loginData.user))
          setIsAuthenticated(true)
          navigate('/dashboard')
        }
      } else {
        setError(data.message || 'Registration failed')
      }
    } catch (error) {
      setError('Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
  }

  return (
    <div className="signup-container">
      <div className="signup-background"></div>
      <div className="signup-content">
        <div className="signup-left">
          <div className="brand-section">
            <h1 className="brand-title">E<span className="highlight-x">X</span>TREME GAME TRUCK</h1>
            <p className="brand-subtitle">Join the Ultimate Gaming Experience</p>
            <div className="gaming-features">
              <div className="feature-item">
                <span className="feature-icon">🎮</span>
                <span>Premium Gaming</span>
              </div>
              <div className="feature-item">
                <span className="feature-icon">🚛</span>
                <span>Mobile Gaming Truck</span>
              </div>
              <div className="feature-item">
                <span className="feature-icon">⚡</span>
                <span>High Performance</span>
              </div>
              <div className="feature-item">
                <span className="feature-icon">🏆</span>
                <span>Tournament Ready</span>
              </div>
            </div>
          </div>
        </div>

        <div className="signup-right">
          <div className="signup-form-container">
            <h2>Sign Up</h2>
            <p>Create an account to access the platform</p>

            {error && <div className="error-message">{error}</div>}

            <form onSubmit={handleSubmit} className="signup-form">
              <div className="input-group">
                <input
                  type="text"
                  name="fullName"
                  placeholder="Full Name"
                  value={formData.fullName}
                  onChange={handleChange}
                  required
                />
                <span className="input-icon">👤</span>
              </div>

              <div className="input-group">
                <input
                  type="email"
                  name="email"
                  placeholder="Email Address"
                  value={formData.email}
                  onChange={handleChange}
                  required
                />
                <span className="input-icon">📧</span>
              </div>



              <div className="input-group">
                <input
                  type="password"
                  name="password"
                  placeholder="Password"
                  value={formData.password}
                  onChange={handleChange}
                  required
                />
                <span className="input-icon">🔒</span>
              </div>

              <div className="input-group">
                <input
                  type="password"
                  name="confirmPassword"
                  placeholder="Confirm Password"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  required
                />
                <span className="input-icon">🔐</span>
              </div>

              <div className="terms-section">
                <label className="terms-checkbox">
                  <input 
                    type="checkbox" 
                    checked={agreedToTerms}
                    onChange={(e) => setAgreedToTerms(e.target.checked)}
                  />
                  <span>I agree to the <a href="#">Terms of Service</a> and <a href="#">Privacy Policy</a></span>
                </label>
              </div>

              <button type="submit" className="signup-btn" disabled={loading}>
                {loading ? <span className="spinner"></span> : 'CREATE ACCOUNT'}
              </button>
            </form>

            <div className="login-link">
              Already have an account? <Link to="/login">Sign In</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}