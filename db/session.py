import os, logging
from datetime import datetime, timedelta
from typing import Optional, Annotated
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from sqlmodel import Field, SQLModel, create_engine, Session, select
from jose import JWTError, jwt
from db.model.user import User, UserResponse, Token, TokenData

## logger
logger = logging.getLogger("app")

###### Database setup ######
# move lifespan
# logger.info("DATABASE SETUP")
# DATABASE_URL = os.environ["DATABASE_URL"]
# engine = create_engine(DATABASE_URL, echo=True)
# Database functions
def create_db_and_tables(engine):
    SQLModel.metadata.create_all(engine)
def get_session(request: Request):
    ## use lifespan
    with Session(request.app.state.engine) as session:
    # with Session() as session:
        yield session
SessionDep = Annotated[Session, Depends(get_session)]
# Database table initialize
# if os.environ["DATABASE_INIT"] == 0:
#     logger.info("DATABASE Table initialization start")
#     create_db_and_tables()
#     logger.info("ATABASE Table initialization end")

###### JWT setup ######
logger.info("JWT SETUP")
SECRET_KEY = os.environ['SECRET_KEY']
ALGORITHM = os.environ['ALGORITHM']
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ['ACCESS_TOKEN_EXPIRE_MINUTES'])
# Password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

###### Utility ######
logger.info("JWT Utility Function")
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else: ## Default 15 minute
        expire = datetime.now() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
def get_user_by_username(session: Session, username: str) -> Optional[User]:
    statement = select(User).where(User.username == username)
    return session.exec(statement).first()
def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(session, username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_username(session, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user