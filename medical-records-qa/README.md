# Medical Records QA 🩺

> **Clinical document retrieval and patient chart question-answering microservice with strict medical grounding and patient-scoped isolation.**

---

## 📌 Overview

**Medical Records QA** provides privacy-first question answering over clinical summaries, lab reports, and patient records.

### 🌟 Features
- **Patient Partitioning**: Ingestion and retrieval are strictly scoped by `patient_id` namespace, guaranteeing cross-patient isolation.
- **Strict Clinical Grounding**: Rejects speculative reasoning, medical self-diagnosis, or ungrounded claims. Answers quote exact figures, units, and dates from clinical notes.
- **Reference Guidance Linking**: Contextually associates lab terms (CBC, Hemoglobin, Creatinine, etc.) with verified reference guidance links (MedlinePlus/NIH).
- **Sub-3s Response Caching**: Caches patient chart token context for high-speed clinician interactions.

---

## 🚀 Quick Start

### 1. Installation
```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 2. Configuration (`.env`)
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
EMBEDDING_MODEL=all-MiniLM-L6-v2
PORT=8200
```

### 3. Run the Service
```bash
python main.py
```
API runs on `http://localhost:8200` with Swagger docs at `http://localhost:8200/docs`.

---

## 📚 Endpoints

- `POST /patients/{patient_id}/ingest`: Ingest lab reports or patient clinical history.
- `POST /patients/{patient_id}/query`: Query the patient chart.
- `GET /patients/{patient_id}/query/stream`: Real-time streaming response via SSE.
- `GET /health`: Health and status check.

