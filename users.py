from bcrypt import gensalt as bcrypt_gensalt, hashpw as bcrypt_hashpw, checkpw as bcrypt_checkpw
from db import TABLE
from datetime import datetime, timedelta, timezone
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from os import getenv as os_getenv
from jwt import encode as jwt_encode, decode as jwt_decode

security = HTTPBearer()

def _hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')
    salt = bcrypt_gensalt()
    hashed = bcrypt_hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt_checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False
    
def exist_user(mail: str, siren: str=None, userId: str=None) -> bool:
    if siren is not None:
        record = TABLE.first(formula=f"{{mail}}='{mail}', {{siren}}='{siren}'")
    elif userId is not None:
        record = TABLE.first(formula=f"{{id}}='{userId}', {{mail}}='{mail}'")
    else:
        record = TABLE.first(formula=f"{{mail}}='{mail}'")

    return record is not None

ACCESS_TOKEN_EXPIRE_MINUTES = 1 * 60  # 1 hour
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt_encode(to_encode, os_getenv("TOKEN_GENERATION_SECRET"), algorithm="HS256")
    return encoded_jwt

def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt_decode(token.credentials, os_getenv("TOKEN_GENERATION_SECRET"), algorithms=["HS256"])
        mail: str = payload.get("mail")
        if mail is None:
            return None
        
        userId: str = payload.get("userId")
        if userId is None:
            return None
        
        user = TABLE.first(formula=f"{{mail}}='{mail}', {{id}}='{userId}'")
        if not user:
            return None

        return user
    except Exception as e:
        print("Error decoding token:", e)
        return None
    
def isConnected(token: HTTPAuthorizationCredentials = Depends(security)):
    user = get_current_user(token)
    return user is not None

def create_user(siret: str, mail: str, password: str):
    if exist_user(mail=mail):
        return False
    
    hashed_password = _hash_password(password)
    TABLE.create({
        "siren": siret[:9],
        "siret": siret,
        "mail": mail,
        "password": hashed_password
    })
    return True

def update_location(current_user: dict, latitude: float, longitude: float):
    if current_user is None:
        current_user = get_current_user()
        if current_user is None:
            return False
    
    if not isinstance(latitude, (float, int)) or not isinstance(longitude, (float, int)):
        return False
    
    TABLE.update(current_user["id"], {
        "latitude": latitude,
        "longitude": longitude
    })
    return True

def get_user_location(current_user=None):
    if current_user is None:
        current_user = get_current_user()
        if current_user is None:
            return None
    
    return {
        "latitude": current_user.get("latitude"),
        "longitude": current_user.get("longitude")
    }

def update_plots(current_user: dict, plots: int):
    if current_user is None:
        current_user = get_current_user()
        if current_user is None:
            return False
    
    if not isinstance(plots, int) or plots < 0:
        return False
    
    TABLE.update(current_user["id"], {
        "plots": plots
    })

    return True

def get_user_plots(current_user=None):
    if current_user is None:
        current_user = get_current_user()
        if current_user is None:
            return None
    
    return current_user.get("plots")