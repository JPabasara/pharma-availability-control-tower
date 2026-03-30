Full Platform Build — Task Tracker
Macro-Phase A: Backend Services
 Package inits for integrations
 manifest_reader
 warehouse_stock_reader
 dc_stock_reader
 sales_history_reader
 lorry_state_reader
 eta_provider
 M1 stub
 M2 stub
 M3 stub
 Engine bridge
 Orchestration service
 Planner flow service + math-bound validation
 Demo state service
Macro-Phase B: FastAPI Routes
 main.py (app + CORS)
 /api/v1/inputs
 /api/v1/orchestration
 /api/v1/planner
 /api/v1/demo-state
 /api/v1/reports
 /api/v1/mock/eta
 /api/v1/dashboard
 Verify: all endpoints working
Macro-Phase C: Demo CLI Scripts
 simulate_vessel_arrival.py
 simulate_lorry_arrival.py
Macro-Phase D: Next.js Frontend
 Initialize Next.js project
 Design system (globals.css)
 Layout + Sidebar
 API client lib
 Shared components
 Dashboard page
 Inputs page
 Priorities page (M1)
 Requests page (M2)
 Dispatch page (M3)
 History page
 Demo State page
 Reports page
 Verify: full flow works
