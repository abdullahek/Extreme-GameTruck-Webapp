import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import Header from '../../components/Header/Header'
import './Dashboard.css'

export default function Dashboard({ setIsAuthenticated }) {
  const navigate = useNavigate()

  const user = JSON.parse(localStorage.getItem('user') || '{}')

  // Fetch dashboard stats using React Query with sticky caching
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/dashboard/stats', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.status === 401) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        setIsAuthenticated(false)
        navigate('/login')
        throw new Error('Unauthorized')
      }

      if (!response.ok) {
        throw new Error('Failed to fetch dashboard stats')
      }

      const data = await response.json()
      console.log('Dashboard stats:', data)
      return data
    },
    staleTime: 300000, // Keep data fresh for 5 minutes (sticky!)
    cacheTime: 600000, // Keep in cache for 10 minutes
    refetchInterval: false, // Don't auto-refetch (sticky stats)
    refetchOnWindowFocus: false, // Don't refetch on focus (sticky stats)
    refetchOnReconnect: false, // Don't refetch on reconnect
  })

  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A'
    return new Date(timestamp).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // Skeleton loading component
  const SkeletonCard = () => (
    <div className="skeleton-card">
      <div className="skeleton-icon"></div>
      <div className="skeleton-number"></div>
      <div className="skeleton-label"></div>
    </div>
  )

  const SkeletonContact = () => (
    <div className="skeleton-contact">
      <div className="skeleton-rank"></div>
      <div className="skeleton-details">
        <div className="skeleton-name"></div>
        <div className="skeleton-phone"></div>
      </div>
      <div className="skeleton-stats">
        <div className="skeleton-count"></div>
        <div className="skeleton-time"></div>
      </div>
    </div>
  )

  return (
    <div className="dashboard-container">
      <Header setIsAuthenticated={setIsAuthenticated} />

      <main className="dashboard-main">
        <div className="welcome-section">
          <h1>Welcome, {user.fullName || 'User'}!</h1>
          <p>Your extreme gaming experience starts here!</p>
        </div>

        {/* Stats Section */}
        <div className="stats-section">
          <div className="stats-row">
            {isLoading ? (
              <SkeletonCard />
            ) : (
              <div className="stat-card">
                <div className="stat-icon">👥</div>
                <div className="stat-number">{stats?.totalContacts || 0}</div>
                <div className="stat-label">Total Contacts</div>
              </div>
            )}

            <div className="top-contacts-card">
              <div className="contacts-header">
                <div className="contacts-icon">🏆</div>
                <h3>Top 5 Most Active Contacts</h3>
              </div>
              <div className="contacts-list">
                {isLoading ? (
                  <>
                    <SkeletonContact />
                    <SkeletonContact />
                    <SkeletonContact />
                  </>
                ) : !stats?.topContacts || stats.topContacts.length === 0 ? (
                  <div className="no-contacts-message">
                    <span>No conversations yet</span>
                  </div>
                ) : (
                  stats.topContacts.map((contact, index) => (
                    <div key={index} className="contact-item">
                      <div className="contact-rank">#{index + 1}</div>
                      <div className="contact-details">
                        <div className="contact-name">{contact.name}</div>
                        <div className="contact-phone">{contact.phone}</div>
                      </div>
                      <div className="contact-stats">
                        <span className="message-count">{contact.messageCount} messages</span>
                        <span className="last-contact">Last: {formatTime(contact.lastMessage)}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Main Navigation Buttons */}
        <div className="dashboard-quick-links">
          <button 
            className="nav-button conversations-btn"
            onClick={() => navigate('/responses')}
          >
            <div className="nav-button-icon">💬</div>
            <div className="nav-button-content">
              <h3>Conversations</h3>
              <p>Chat with your customers</p>
            </div>
            <div className="nav-button-arrow">→</div>
          </button>

          <button 
            className="nav-button settings-btn"
            onClick={() => navigate('/settings')}
          >
            <div className="nav-button-icon">⚙️</div>
            <div className="nav-button-content">
              <h3>Settings</h3>
              <p>Configure your system</p>
            </div>
            <div className="nav-button-arrow">→</div>
          </button>
        </div>
      </main>
    </div>
  )
}
