# FindMyNyumba Execution Guide

## 1. Start PostgreSQL Backend
cd D:\FindMyNyumba\backend
uvicorn main:app --reload

## 2. Start Orange Frontend
cd D:\FindMyNyumba\frontend
python -m http.server 5500
