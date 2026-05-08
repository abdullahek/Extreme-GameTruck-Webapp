# Extreme Game Truck - Customer Communication Platform

## Overview
This full-stack customer communication platform, built for "Extreme Game Truck," enables SMS-based customer communications with AI-powered intelligent responses using OpenAI's assistant API and Twilio integration. Its primary purpose is to manage customer SMS conversations in real-time, provide automated AI responses, track conversation history and analytics, and manage Twilio settings and contacts. The project aims to enhance customer engagement and streamline communication processes for Extreme Game Truck.

## User Preferences
- Black and dark red color theme (pure black #000000 backgrounds with red accents #cc0000, #ff0000)
- Minimal, compact UI design with reduced padding and margins
- Single-row header layout with all navigation in one compact row
- Standard React and Flask conventions followed

## System Architecture

### UI/UX Decisions
The frontend, built with React 18 and Vite 5, features a modern, compact, and professional aesthetic with a black and dark red theme. Key UI/UX decisions include:
- **Compact Design:** Medium-sized headers (50px fixed height), minimal typography, and reduced padding/margins for space efficiency.
- **Consistent Styling:** Streamlined look with ultra-thin borders, fully rounded (pill-shaped) buttons, and refined gradients.
- **Interactive Elements:** Smooth transitions, pure black backgrounds with dark red borders for hover/active states.
- **Real-time Feedback:** Optimistic UI updates, skeleton loading states, pulsing dot loaders, and instant visual feedback on actions.
- **Responsive Layout:** Components are designed to be visible and functional across various screen sizes.
- **Theming:** A pure black UI (#000000) with dark red accents (#cc0000, #ff0000) and borders, consistent with a professional gaming aesthetic.
- **Fixed Header:** Single-row header (50px) with logo left, logout right - fixed positioning with proper z-index for consistent layout.

### Technical Implementations
The platform is a full-stack application using a React frontend and a Flask backend.
- **Frontend:** React 18, Vite 5, React Router DOM 7, TanStack Query, and Socket.IO Client.
- **Backend:** Flask 3.1, Flask-SQLAlchemy, Flask-CORS, Flask-SocketIO, and PyJWT.
- **Real-time Updates:** Socket.IO facilitates live message updates and notifications.
- **Authentication:** JWT-based authentication with secure password hashing.
- **Performance:** Optimized API endpoints with SQL aggregations, pagination, HTTP caching, and React Query caching.

### Feature Specifications
- **SMS Integration:** Twilio webhook handling for incoming messages, message queuing, and manual message sending.
- **AI Integration:** OpenAI assistant API integration for context-aware response generation.
- **User Management:** User registration, login, and profile management.
- **Analytics Dashboard:** Provides pre-calculated dashboard statistics such as total contacts, messages, and top contacts.
- **Conversation Management:** Real-time conversation display, message history, and contact management.

### System Design Choices
- **Database:** PostgreSQL (via Neon) with connection pooling and auto-retry logic.
- **API Endpoints:** Structured RESTful API for authentication, user management, settings, dashboard, SMS, logs, and health checks.
- **Message Flow:** Twilio webhooks trigger message processing, AI response generation, and delivery, with all activities logged.
- **AI Thread Management:** Each contact has a unique `thread_id` to maintain conversation context, including retry logic and fallback handling.

## External Dependencies
- **Twilio:** Used for SMS messaging capabilities.
- **OpenAI:** Provides AI-powered intelligent responses through its assistant API.
- **PostgreSQL (via Neon):** The primary database for storing all application data.
- **External AI Endpoint:** `extreme-game-truck-graelonbrown.replit.app` for AI processing.

## Deployment Configuration
- **Deployment Target:** Autoscale (suitable for stateless web applications)
- **Build Command:** `npm run build` (compiles frontend with Vite)
- **Run Command:** `python3 app.py` (simplified, no bash wrapper)
- **Port Configuration:** Flask dynamically uses PORT environment variable (for deployment) with fallback to 5000 (for development)
- **Production Server:** Flask runs on 0.0.0.0 with threaded mode, port auto-detected from environment

## Recent Changes
- **Oct 10, 2025 (Deployment Port Fix):**
  - **Port configuration**: Fixed Flask app to use PORT environment variable (for deployment) with fallback to 5000
  - **Deployment setup**: Configured Autoscale deployment with proper build and run commands
  - **Development mode**: App runs on port 5000 in development, automatically uses correct port in production
  - **Result**: Deployment now works correctly with proper port configuration

- **Oct 10, 2025 (Header Navigation Fix):**
  - **Navigation buttons**: Fixed navigation buttons to exactly match logout button styling
  - **CSS conflict resolution**: Removed duplicate `.main-navigation` class from Dashboard.css causing style conflicts
  - **Dashboard refactoring**: Renamed dashboard quick links container to `.dashboard-quick-links` to avoid naming conflicts
  - **Result**: Header navigation buttons now perfectly match logout button in size, styling, and hover effects

- **Oct 10, 2025 (Header, Loader, and Error Handling):**
  - **Header enhancements**: Increased header height to 50px with larger logo (1rem) and improved visual presence
  - **Navigation simplification**: Removed navigation buttons from header - now shows only logo (left) and logout (right)
  - **Syncing loader upgrade**: Replaced rotating emoji with sleek pulsing red dots animation matching black/red theme
  - **Error handling improvements**: Added proper error message styling with retry functionality and detailed error reporting
  - **Layout fixes**: Fixed Responses page layout to use calc(100vh - 50px) preventing header collapse with sidebar
  - **Result**: Clean, professional header with better visual hierarchy, smooth loaders, and robust error handling
