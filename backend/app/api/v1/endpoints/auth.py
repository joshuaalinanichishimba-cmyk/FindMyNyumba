from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.utils.response import success_response, error_response

router = APIRouter()

@router.post("/register")
async def register():
    return success_response("Registration endpoint active")

@router.post("/login")
async def login():
    return success_response("Login endpoint active")
