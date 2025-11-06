import os
from langchain_google_genai import ChatGoogleGenerativeAI
import uvicorn
import shutil
from typing import Annotated
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, UploadFile, Form, HTTPException, Depends, status
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from sqlalchemy.orm import Session
from utils.prompt import PROMPT
from utils.schema import User, Token, UserInDB
from langchain_core.prompts import ChatPromptTemplate
from utils.auth import (
    get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, verify_password, 
    get_current_user
)
from utils.orm import get_db, get_user_by_email, create_db_user, Base, engine

from datetime import timedelta

# Define the lifespan function to handle startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create database tables
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables created.")
        yield
    except Exception as e:
        print(f"Error during startup: {e}")
        yield

app = FastAPI(lifespan=lifespan)

@app.post("/signup", response_model=Token)
async def signup(user: User, db: Annotated[Session, Depends(get_db)]):
    db_user = get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    create_db_user(db, user, hashed_password)
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", response_model=Token)
async def login(form_data: User, db: Annotated[Session, Depends(get_db)]):
    db_user = get_user_by_email(db, email=form_data.email)
    
    if not db_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    if not verify_password(form_data.password, db_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/chat/")
async def upload_file_and_question(
    file: UploadFile, 
    question: str = Form(...),
    current_user: Annotated[UserInDB, Depends(get_current_user)] = None
):  
    try:
        temp_file_path = f"/tmp/{file.filename}"
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()
        raw_text = "\n\n".join([doc.page_content for doc in documents])
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.0,
            api_key=GEMINI_API_KEY
            # api_key is often read from the environment
        )
        prompt = ChatPromptTemplate.from_template(template=PROMPT)
        chain = prompt | llm

        response = chain.invoke({
            "context": raw_text,
            "question": question
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")
    return {
        "result": response.content,
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
