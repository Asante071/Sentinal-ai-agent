"""Run: uvicorn api:app --reload   (docs at http://127.0.0.1:8000/docs)"""
from fastapi import FastAPI
from pydantic import BaseModel
import tools

app = FastAPI(title="SentinelAI Mock IT Backend")

class ToolCall(BaseModel):
    args: dict = {}

@app.get("/tools")
def list_tools():            
    return tools.get_declarations()

@app.post("/tools/{name}")
def call_tool(name: str, body: ToolCall):
    return tools.execute_tool(name, body.args)

@app.get("/tickets")
def tickets():
    return tools.STATE["tickets"]

@app.get("/audit")
def audit():
    return tools.STATE["audit_log"]

@app.post("/reset")
def reset():
    tools.reset_state()
    return {"status": "state reset"}
