# React Dashboard Skill

**Purpose**: Build data-rich dashboards with React + TypeScript + Tailwind + shadcn/ui  
**When to use**: Creating dashboard pages, charts, tables, real-time data components

---

## Tech Stack

- **React 18** + TypeScript (strict mode)
- **Vite** (build tool)
- **Tailwind CSS** + **shadcn/ui** (styling + components)
- **React Query** (server state / data fetching)
- **Recharts** (data visualization)
- **React Router** (navigation)

---

## Core Patterns

### 1. Data Fetching (React Query)

```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

function useAlerts(storeId?: string) {
  return useQuery({
    queryKey: ['alerts', storeId],
    queryFn: () => api.get(`/api/v1/alerts?store_id=${storeId}`),
    refetchInterval: 30_000,  // 30s auto-refresh
    staleTime: 10_000,
  });
}

function useAcknowledgeAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) => api.patch(`/api/v1/alerts/${alertId}/acknowledge`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  });
}
```

### 2. Chart Components (Recharts)

```tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

function ForecastChart({ data }: { data: ForecastPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="date" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="actual" stroke="#22c55e" strokeWidth={2} />
        <Line type="monotone" dataKey="forecast" stroke="#3b82f6" strokeDasharray="5 5" />
        <Line type="monotone" dataKey="upper" stroke="#94a3b8" strokeDasharray="3 3" />
        <Line type="monotone" dataKey="lower" stroke="#94a3b8" strokeDasharray="3 3" />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

### 3. WebSocket Hook (Real-Time Alerts)

```tsx
function useWebSocket(customerId: string) {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/alerts/${customerId}`);
    ws.onmessage = (event) => {
      const alert = JSON.parse(event.data);
      setAlerts(prev => [alert, ...prev]);
    };
    ws.onerror = () => setTimeout(() => ws.close(), 1000);
    return () => ws.close();
  }, [customerId]);

  return alerts;
}
```

### 4. Layout Pattern

```tsx
function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Sidebar />
      <main className="ml-64 p-6">
        <Header />
        {children}
      </main>
    </div>
  );
}
```

### 5. Auth0 Integration

```tsx
import { Auth0Provider, useAuth0 } from '@auth0/auth0-react';

function App() {
  return (
    <Auth0Provider
      domain={import.meta.env.VITE_AUTH0_DOMAIN}
      clientId={import.meta.env.VITE_AUTH0_CLIENT_ID}
      authorizationParams={{ redirect_uri: window.location.origin }}
    >
      <Router />
    </Auth0Provider>
  );
}
```

---

## DO / DON'T

### DO
- ✅ Use React Query for all server data (no useState for API data)
- ✅ Use TypeScript interfaces for all props and API responses
- ✅ Use shadcn/ui for consistent component styling
- ✅ Make charts responsive with `ResponsiveContainer`
- ✅ Implement loading/error states for all data-fetching components

### DON'T
- ❌ Use `useEffect` for data fetching (use React Query)
- ❌ Store API data in local state (use React Query cache)
- ❌ Skip TypeScript types (any = bad)
- ❌ Use inline styles (use Tailwind classes)

---

**Last Updated**: 2026-02-09
