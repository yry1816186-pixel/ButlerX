# Butler Smart Home Frontend

A modern Vue.js 3 + TypeScript frontend for Butler (Smart Butler) smart home system.

## Features

- 🏠 **Dashboard** - Overview of system status and quick controls
- 📱 **Device Management** - Control and monitor all smart devices
- ⚡ **Automations** - Create and manage automation rules
- 🎭 **Scenarios** - One-tap scene activation
- 🔌 **Integrations** - Connect third-party smart home platforms
- 👁️ **Vision Monitoring** - Real-time camera feed with AI detection
- ⚙️ **Settings** - Configure system preferences

## Tech Stack

- **Framework**: Vue 3 with Composition API
- **Language**: TypeScript
- **Build Tool**: Vite
- **State Management**: Pinia
- **Routing**: Vue Router 4
- **HTTP Client**: Axios
- **Styling**: CSS Variables (Dark mode ready)

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

The application will be available at `http://localhost:5173`

### Build for Production

```bash
npm run build
```

### Type Checking

```bash
npm run type-check
```

### Linting

```bash
npm run lint
```

## Project Structure

```
src/
├── assets/           # CSS styles and static assets
├── api/              # API client and endpoint definitions
├── components/       # Vue components
│   ├── dashboard/    # Dashboard components
│   ├── devices/      # Device components
│   ├── automations/  # Automation components
│   ├── scenarios/    # Scenario components
│   ├── integrations/ # Integration components
│   └── layout/      # Layout components
├── router/           # Vue Router configuration
├── stores/           # Pinia stores
├── views/            # Page components
├── App.vue           # Root component
└── main.ts           # Application entry point
```

## API Integration

The frontend communicates with the backend via REST API:

- Base URL: `/api`
- Proxy configured for development (localhost:8000)

### API Endpoints

- `GET /api/devices` - List all devices
- `POST /api/devices/:id/control` - Control a device
- `GET /api/automations` - List automations
- `POST /api/automations` - Create automation
- `GET /api/camera/stream` - Camera video stream

## State Management

### Pinia Stores

- `useAppStore` - Main application state
  - Devices, automations, scenarios, integrations
  - Loading states, errors, notifications
  - UI state (sidebar, etc.)

## Component Architecture

### Layout Components

- `AppHeader` - Navigation header
- `AppFooter` - Footer with copyright

### Feature Components

- `StatCard` - Dashboard statistics card
- `DeviceCard` - Device control card
- `AutomationCard` - Automation rule card
- `ScenarioCard` - Scene activation card
- `IntegrationCard` - Integration status card

## Styling

The project uses CSS variables for theming:

- Light mode (default)
- Dark mode (via `prefers-color-scheme`)
- Customizable via `assets/variables.css`

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## License

MIT License
