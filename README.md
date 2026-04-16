# Simulation Prediction Engine

An AI-powered simulation and prediction system built with modern web technologies and Groq Cloud's LLM.

## Overview

Simulation Prediction Engine is a full-stack application that combines artificial intelligence with an interactive dashboard for data analysis and predictions. The system uses Groq Cloud for high-speed AI inference and provides real-time visualization of simulation results.

## Tech Stack

Frontend:
- Next.js 14 - React framework
- Tailwind CSS - Styling
- Recharts - Data visualization

Backend:
- Python 3.10+ 
- FastAPI - Web framework
- Uvicorn - ASGI server
- Groq Cloud SDK - LLM inference

## Installation

### Prerequisites

- Python 3.10 or higher
- Node.js and npm
- Groq API key from https://console.groq.com

### Backend Setup

1. Navigate to backend folder:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Add your Groq API key to `backend/engine.py`:
```python
client = Groq(api_key="YOUR_GROQ_API_KEY")
```

4. Start the server in main directory:
```bash
uvicorn main:app --reload
```

Backend will run at http://localhost:8000

### Frontend Setup

1. Open a new terminal and navigate to frontend:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start development server:
```bash
npm run dev
```

Frontend will run at http://localhost:3000

## Configuration

### Change AI Model

Edit `backend/engine.py` and change the model parameter:
```python
model="llama-3.3-70b-versatile"
```

Available models:
- llama-3.3-70b-versatile (recommended)
- mixtral-8x7b-32768
- gemma-7b-it

### Environment Variables

Create `.env.local` in frontend directory:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Project Structure

```
Simulation-Prediction-Engine/
├── backend/
│   ├── engine.py          # Groq client and AI logic
│   ├── agents.py          # Agent configuration
│   ├── main.py            # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── app/               # Next.js pages
│   ├── components/        # React components
│   ├── package.json
│   └── tailwind.config.js
└── README.md
```

## API Endpoints

Base URL: http://localhost:8000

Main endpoints:
- `POST /api/simulate` - Run a simulation
- `GET /api/simulate/{id}` - Get simulation result
- `POST /api/predict` - Make predictions

View full API documentation at http://localhost:8000/docs

## Troubleshooting

Port already in use:
```bash
# Use different port
uvicorn main:app --reload --port 8001
```

Groq API error:
- Check your API key is correct
- Verify API key has not expired
- Ensure you have API quota remaining

Module not found:
```bash
pip install -r requirements.txt
```

Frontend port 3000 in use:
```bash
npm run dev -- -p 3001
```

## License

MIT License
