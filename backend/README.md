# ShelfOps Backend

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Seed test data
python scripts/seed_test_data.py

# Start development server
uvicorn api.main:app --reload
```
