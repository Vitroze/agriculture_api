from bcrypt import gensalt as bcrypt_gensalt, hashpw as bcrypt_hashpw, checkpw as bcrypt_checkpw
from db import TABLE, INVENTORY, ACTIVITIES_TABLE
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
    
def exist_user(mail: str, siren: str = None, userId: str = None) -> bool:
    if siren is not None:
        formula = f"OR({{mail}}='{mail}', {{siren}}='{siren}')"
        record = TABLE.first(formula=formula)
    elif userId is not None:
        formula = f"AND({{id}}='{userId}', {{mail}}='{mail}')"
        record = TABLE.first(formula=formula)
    else:
        record = TABLE.first(formula=f"{{mail}}='{mail}'")

    return record is not None

ACCESS_TOKEN_EXPIRE_MINUTES = 1 * 60  # 1 hour
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt_encode(to_encode, os_getenv("TOKEN_GENERATION_SECRET"), algorithm="HS256")
    return encoded_jwt, expire

def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    try:
        print("Decoding token:", token)
        payload = jwt_decode(token.credentials, os_getenv("TOKEN_GENERATION_SECRET"), algorithms=["HS256"])
        mail: str = payload.get("mail")
        if mail is None:
            return None
        
        userId: str = payload.get("userId")
        if userId is None:
            return None
        
        user = TABLE.first(formula=f"AND({{mail}}='{mail}', RECORD_ID()='{userId}')")
        if not user:
            return None

        return user
    except Exception as e:
        print("Error decoding token:", e)
        return None
    
def isConnected(token: HTTPAuthorizationCredentials = Depends(security)):
    user = get_current_user(token)
    return user is not None

def create_user(siren: str, mail: str, password: str):
    if exist_user(mail=mail):
        return False
    
    hashed_password = _hash_password(password)
    TABLE.create({
        "siren": siren,
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
    
    print(current_user)

    return {
        "latitude": current_user["fields"].get("latitude"),
        "longitude": current_user["fields"].get("longitude")
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

def get_user_info(mail: str):
    user = TABLE.first(formula=f"{{mail}}='{mail}'")
    if not user:
        return None
    
    return user

types = [
    "Objet Electronique",
    "Fruits",
    "Légumes",
    "Animaux",
    "Autres"
]

def get_inventory(current_user=None):
    if current_user is None:
        current_user = get_current_user()
        if current_user is None:
            return None
    
    records = INVENTORY.all(formula=f"{{userMail}}='{current_user['fields']['mail']}'")
    inventory = []
    for record in records:
        fields = record.get("fields", {})
        inventory.append({
            "id": record.get("id"),
            "Title": fields.get("name", "N/A"),
            "Description": fields.get("description", "N/A"),
            "Quantity": fields.get("quantity", 0),
            "Total": fields.get("total", 0),
            "Type": types[fields.get("type", 0)] if fields.get("type") is not None and 0 <= fields.get("type") < len(types) else "N/A",
            "TypeNum": fields.get("type", "N/A"),
            "Date": fields.get("lastModify", "N/A")
        })
    return inventory

def get_exist_item(user_mail: str, name_item: str):
    record = INVENTORY.first(formula=f"AND({{userMail}}='{user_mail}', {{name}}='{name_item}')")
    return record

def add_inventory_item(current_user: dict, name: str, description: str, quantity: int, total: float, type: int):
    if current_user is None:
        current_user = get_current_user()
        if current_user is None:
            return False

    if not isinstance(quantity, int) or quantity < 0:
        return False

    if not isinstance(total, (float, int)) or total < 0:
        return False

    if type < 0 or type > 5:
        return False

    INVENTORY.create({
        "userMail": current_user["fields"]["mail"],
        "name": name,
        "description": description,
        "quantity": quantity,
        "total": total,
        "type": type
    })
    return True

def update_inventory_item(current_user: dict, item_id: str, name: str, description: str, quantity: int, total: float, type: int):
    if current_user is None:
        current_user = get_current_user()
        if current_user is None:
            return False

    if not isinstance(quantity, int) or quantity < 0:
        return False

    if not isinstance(total, (float, int)) or total < 0:
        return False

    if type < 0 or type > 5:
        return False

    item = INVENTORY.get(item_id)
    if not item or item["fields"].get("userMail") != current_user["fields"]["mail"]:
        return False

    nameItem = item["fields"].get("name", "")    
    if nameItem != name and get_exist_item(current_user["fields"]["mail"], name) is not None:
        return False

    INVENTORY.update(item_id, {
        "name": name,
        "description": description,
        "quantity": quantity,
        "total": total,
        "type": type
    })
    return True

def delete_inventory_item(current_user: dict, item_id: str):
    if current_user is None:
        current_user = get_current_user()
        if current_user is None:
            return False
    
    print(item_id)

    item = None
    try:
        item = INVENTORY.get(item_id)
    except Exception as e:
        print("Error fetching inventory item:", e)
        return False

    if not item or item["fields"].get("userMail") != current_user["fields"]["mail"]:
        return False
    
    INVENTORY.delete(item_id)
    return True

def get_last_activities(current_user=None):
    if current_user is None:
        current_user = get_current_user()
        if current_user is None:
            return None
    
    sTodayDate = datetime.now().date()
    sTodayDate = sTodayDate.strftime("%Y-%m-%d")

    print(f"Fetching activities for date: {sTodayDate} and user: {current_user['fields']['mail']}")

    # 1. Correction du paramètre sort
    records = ACTIVITIES_TABLE.all(
        formula=f"Date = '{sTodayDate}'", 
        sort=["-Date"], 
        max_records=1
    )
    
    # 2. Vérification si la liste est vide
    if not records:
        return []
        
    # 3. Récupération du premier enregistrement de la liste
    record = records[0]
    
    activities = [
        {
            "title": "Rappel activité du jour - Matin",
            "message": record["fields"].get("tache matin", "N/A"),
            "type": "rappel"
        },
        {
            "title": "Rappel activité du jour - Après-midi",
            "message": record["fields"].get("tache aprem", "N/A"),
            "type": "rappel"
        }
    ]

    return activities