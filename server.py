"""
Module: server.py
Purpose: Server entry point for the HQGE Enterprise API.
         Runs the FastAPI app from api.py with uvicorn.
"""

import uvicorn

if __name__ == "__main__":
    # Run with: python server.py
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)