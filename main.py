from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from fastapi import Query
from openai import OpenAI
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Load Supabase env variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

@app.get("/ping")
async def ping():
    return {"status": "alive"}


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
    


class ActionInput(BaseModel):
    user_id: str
    name: str
    points: int
    category: str
    description: str
    impact: str
    carbon_saved: float = 0
    water_saved: float = 0
    waste_saved: float = 0
    energy_saved: float = 0

@app.post("/log-action")
def log_action(data: ActionInput):
    try:
        # Check if user exists
        user_check = supabase.table("profiles").select("id, points").eq("id", data.user_id).execute()
        if not user_check.data:
            raise HTTPException(status_code=404, detail="User not found")

        # Insert the action
        insert_response = supabase.table("eco_actions").insert({
            "user_id": data.user_id,
            "name": data.name,
            "points": data.points,
            "category": data.category,
            "description": data.description,
            "impact": data.impact,
            "carbon_saved": data.carbon_saved,
            "water_saved": data.water_saved,
            "waste_saved": data.waste_saved,
            "energy_saved": data.energy_saved,
        }).execute()

        if not insert_response.data:
            raise HTTPException(status_code=500, detail="Failed to insert action.")

        # Update points
        current_points = user_check.data[0].get("points", 0)
        new_total = current_points + data.points

        update_response = supabase.table("profiles").update({
            "points": new_total
        }).eq("id", data.user_id).execute()

        if not update_response.data:
            raise HTTPException(status_code=500, detail="Failed to update user points.")

        return {
            "message": f"Logged '{data.name}' and updated user points.",
            "action": insert_response.data,
            "new_total_points": new_total
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None  # Add user_id to match the frontend payload

@app.post("/chat")
def chat_endpoint(chat: ChatRequest):
    try:
        # ✅ Get eco impact totals for the user
        eco_data = supabase.table("eco_actions") \
            .select("carbon_saved", "water_saved", "waste_saved", "energy_saved") \
            .eq("user_id", chat.user_id) \
            .execute()

        if not eco_data.data:
            raise HTTPException(status_code=404, detail="No eco actions found for user")

        # ✅ Sum each field
        totals = {
            "carbon_saved": sum([row.get("carbon_saved", 0) or 0 for row in eco_data.data]),
            "water_saved": sum([row.get("water_saved", 0) or 0 for row in eco_data.data]),
            "waste_saved": sum([row.get("waste_saved", 0) or 0 for row in eco_data.data]),
            "energy_saved": sum([row.get("energy_saved", 0) or 0 for row in eco_data.data]),
        }

        # ✅ Ask OpenAI using user's stats
        system_prompt = (
            f"You are an eco assistant. The user's eco savings so far are:\n"
            f"- Carbon Saved: {totals['carbon_saved']} kg\n"
            f"- Water Saved: {totals['water_saved']} liters\n"
            f"- Waste Saved: {totals['waste_saved']} kg\n"
            f"- Energy Saved: {totals['energy_saved']} kWh\n"
            f"Based on this, answer the following user question. Provide the stats of the user's eco savings but also provide your thoughts and insights as well"
        )

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chat.message}
            ]
        )

        return {
            "reply": response.choices[0].message.content,
            "totals": totals
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.post("/basic_chat")
def chat(request: ChatRequest):
    user_input = request.message.lower()

    # Sample logic (replace with OpenAI or real LLM call)
    if "bike" in user_input:
        response = "That's awesome! Biking is a great way to reduce your carbon footprint."
    elif "recycle" in user_input:
        response = "Recycling is key! Make sure to clean plastics before binning them."
    else:
        response = "I'm here to help you make eco-friendly choices! Ask me anything."

    return {"reply": response}
