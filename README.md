 How to run the full pipeline manually:

  Open your terminal (Command Prompt or PowerShell) and run:

  cd C:\Users\user\financebot
  venv\Scripts\activate

  # Step 1: Update holdings (only needed if you have a new Nordnet PDF)
  python src/ingestion.py

  # Step 2: Fetch latest news (~30 seconds, rate limited)
  python src/researcher.py

  # Step 3: Generate analysis via Ollama (~30-60 seconds)
  python src/analyst.py

  # Step 4: Send to Telegram
  python src/delivery.py

  Or as a one-liner (runs all steps sequentially):

  python src/ingestion.py && python src/researcher.py && python src/analyst.py && python src/delivery.py

  Typical daily use:
  - Skip step 1 unless you have a new portfolio PDF
  - Steps 2-4 are what you'd run daily