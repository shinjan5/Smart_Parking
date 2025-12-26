# 🚗 Smart Parking System (Agentic AI)

An end-to-end **AI-powered smart parking system** that automatically detects vehicle license plates, validates pre-bookings, assigns the optimal parking slot using an agentic workflow, and applies **dynamic pricing** based on real-time occupancy.

---

## 🧠 System Architecture

```mermaid
flowchart TD
    A[📷 Gate Camera / Video / Image] -->|Frames| B[Camera Ingest<br/>camera_ingest.py]

    B -->|POST /vision/detect_plate| C[Flask Backend API]

    C --> D[Vision Agent<br/>YOLO + EasyOCR]
    D -->|License Plate| E[Entry Recognition Agent<br/>LangGraph]

    E --> F[Booking Validation<br/>SQLite]
    F -->|Valid Booking| G[Slot Assignment Agent<br/>LLM + Rules]

    G --> H[Digital Twin<br/>mock_digital_twin.json]
    G --> I[Dynamic Pricing Engine]

    I --> J[Persist Entry<br/>SQLite DB]
    J --> K[✅ Entry Confirmed]

    %% Frontends
    L[🧑 Customer Portal<br/>Streamlit] -->|Pre-Booking / Status| F
    L --> J

    M[🛂 Security Dashboard<br/>Streamlit] -->|Live Monitoring| J
    M -->|Slot State| H


## ⚙️ Core Workflow

1. Camera / video / image feed is ingested at the parking gate  
2. YOLO detects license plates and EasyOCR extracts text  
3. Entry agent validates pre-booking from SQLite  
4. Slot assignment agent selects the **closest compatible free slot**  
5. Dynamic pricing is calculated using real-time occupancy  
6. Entry is persisted in the database  
7. Customer & security dashboards update instantly  

---

## 💰 Dynamic Pricing Formula

Dynamic pricing increases parking cost as occupancy rises beyond **50%**.

### Formula
```text
price = BASE_PRICE × (1 + ELASTICITY × max(0, occupancy_ratio − 0.5))

