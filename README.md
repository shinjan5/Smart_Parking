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

