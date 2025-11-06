from typing import Generator
from sqlalchemy import create_engine, Column, String
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from utils.schema import User

# Database Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# SQLAlchemy User ORM Model
class UserORM(Base):
    __tablename__ = "users"
    
    email = Column(String, primary_key=True, index=True, unique=True)
    hashed_password = Column(String)

# Database Session Dependency
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user_by_email(db: Session, email: str):
    return db.query(UserORM).filter(UserORM.email == email).first()

def create_db_user(db: Session, user: User, hashed_password: str):
    db_user = UserORM(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user