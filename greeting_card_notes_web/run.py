"""
Runner script for "Rooting For You" FastAPI Modern Stack Web App.
"""

import os
import sys
from pathlib import Path
import uvicorn
from dotenv import load_dotenv

# Load environment variables
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY is not set in your .env file.")
        print("Please create or edit your .env file at the repository root and add your Google API key:")
        print('GOOGLE_API_KEY = "your-actual-api-key"')
        sys.exit(1)

    print("======================================================================")
    print(" Starting 'Rooting For You' Modern Stack Web App (FastAPI)")
    print(" URL: http://127.0.0.1:8000")
    print("======================================================================")
    
    # Run the uvicorn server pointing to our main module
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
