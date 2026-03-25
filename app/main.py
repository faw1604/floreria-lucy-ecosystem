# Florería Lucy Ecosystem - Main Application
from fastapi import FastAPI

app = FastAPI(title="Florería Lucy Ecosystem", version="0.1.0")


@app.get("/")
def root():
    return {"message": "Bienvenido a Florería Lucy Ecosystem"}
