from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from fastapi import Query

# Load Supabase env variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing Supabase credentials")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ✅ Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # React ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScoreInput(BaseModel):
    user_id: str
    points: int

@app.post("/initialize-score")
def initialize_score(data: ScoreInput):
    try:
        # Force set the points to a value (e.g., 0)
        response = supabase.table("profiles").update({
            "points": data.points
        }).eq("id", data.user_id).execute()

        if len(response.data) == 0:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "message": f"Points initialized to {data.points}",
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/add-score")
def add_score(data: ScoreInput):
    try:
        # Fetch current score
        result = supabase.table("profiles").select("points").eq("id", data.user_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        current = result.data[0].get("points", 0)
        new_total = current + data.points

        # Update score
        update = supabase.table("profiles").update({
            "points": new_total
        }).eq("id", data.user_id).execute()

        return {
            "message": f"Added {data.points} points",
            "old_points": current,
            "new_points": new_total,
            "data": update.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/get-score")
def get_score(user_id: str = Query(..., description="User UUID")):
    try:
        response = supabase.table("profiles").select("points").eq("id", user_id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "user_id": user_id,
            "points": response.data[0]["points"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

