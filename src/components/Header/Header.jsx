
import { useNavigate, useLocation } from 'react-router-dom'
import './Header.css'

export default function Header({ setIsAuthenticated }) {
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setIsAuthenticated(false)
    navigate('/login')
  }

  const navigationItems = [
    { name: 'Dashboard', path: '/dashboard', icon: '🎮' },
    { name: 'Conversations', path: '/responses', icon: '💬' },
    { name: 'Settings', path: '/settings', icon: '⚙️' }
  ]

  return (
    <header className="app-header">
      <div className="header-content">
        <h1 className="brand-title">E<span className="highlight-x">X</span>TREME GAME TRUCK</h1>

        <nav className="main-navigation">
          {navigationItems.map((item) => (
            <button
              key={item.path}
              className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
              onClick={() => navigate(item.path)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-text">{item.name}</span>
            </button>
          ))}
        </nav>

        <button onClick={handleLogout} className="logout-btn">
          <span className="logout-icon">🚪</span>
          <span className="logout-text">Logout</span>
        </button>
      </div>
    </header>
  )
}
