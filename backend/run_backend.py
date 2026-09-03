import uvicorn
from app.config import PORT, HOST

if __name__ == "__main__":
    print(f"Starting Razorpay Agentic Commerce API on http://{HOST}:{PORT}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
