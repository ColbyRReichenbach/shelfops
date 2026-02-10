# Workflow: Build Dashboard

**Purpose**: Create React dashboard for viewing alerts and forecasts

**Agent**: full-stack-engineer

**Duration**: 8-12 hours

---

## Steps

### 1. Set Up React Project
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npm install @tanstack/react-query tailwindcss recharts
```

### 2. Implement Authentication
- Auth0 integration
- Protected routes
- Token refresh

### 3. Build Core Components
- AlertCard (display stockout alerts)
- ForecastChart (Recharts line chart)
- StoreSelector (dropdown filter)

### 4. Connect to API
- React Query for data fetching
- WebSocket for real-time alerts
- Error handling

---

**Checklist**:
- [ ] React project created
- [ ] Auth0 configured
- [ ] Dashboard components built
- [ ] API integration working
- [ ] Real-time alerts functional

**Last Updated**: 2026-02-09
