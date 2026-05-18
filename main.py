from fastapi import Depends, FastAPI, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from pyairtable import Api
from dotenv import load_dotenv
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
import feedparser
import bcrypt
import os
import httpx
import jwt
import uvicorn
import re

load_dotenv()
API = Api(os.getenv("AIRTABLE_TOKEN"))
TABLE = API.table(os.getenv("AIRTABLE_BASE_ID"), os.getenv("AIRTABLE_TABLE_USERS"))
RSS_TABLE = API.table(os.getenv("AIRTABLE_BASE_ID"), os.getenv("AIRTABLE_TABLE_NEWS"))

security = HTTPBearer()
app = FastAPI(
    title="Agriculture API",
    description="API for agriculture-related services, including user registration, authentication, location updates, and news retrieval.",
    version="1.0.0",
)

def hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # On compare les octets du mot de passe tapé avec ceux du hash de la base
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

@app.get("/", summary="Root Endpoint", description="Check if the development server is running and the API is ready.")
async def root():
    return {"message": "Development server is running! API is ready."}

class RegisterRequest(BaseModel):
    mail: str
    siret: str
    password: str

async def getSiret(siret: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://recherche-entreprises.api.gouv.fr/search?q={siret}&page=1&per_page=1")
        result = response.json()
        result = result["results"] or []
        if not result or len(result) == 0:
            print(f"No company information found for SIRET: {siret}")
            return {}
        
        result = result[0]

        return result

@app.post("/register", summary="User Registration", description="Register a new user with their SIRET number, email, and password.")
async def register(request: RegisterRequest):
    compagny_info = await getSiret(str(request.siret))
    if not compagny_info.get("siren") or compagny_info["siren"] != request.siret:
        return {"error": "Invalid SIRET number"}

    if TABLE.first(formula=f"{{siret}}='{request.siret}'"):
        return {"error": "SIRET number already registered"}
    
    TABLE.create({
        "siret": request.siret,
        "mail": request.mail,
        "password": hash_password(request.password)
    })

    return {"message": "Registration successful"}
    
class LoginRequest(BaseModel):
    mail: str
    password: str

ACCESS_TOKEN_EXPIRE_MINUTES = 1 * 60  # 1 hour
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, os.getenv("TOKEN_GENERATION_SECRET"), algorithm="HS256")
    return encoded_jwt

def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(token.credentials, os.getenv("TOKEN_GENERATION_SECRET"), algorithms=["HS256"])
        print("Decoded token payload:", payload)
        mail: str = payload.get("sub")
        print("Decoded token payload:", payload)
        if mail is None:
            return None
        
        return mail
    except Exception as e:
        print("Error decoding token:", e)
        return None

@app.post("/login", summary="User Login", description="Authenticate a user with their email and password.")
async def login(request: LoginRequest):
    user = TABLE.first(formula=f"{{mail}}='{request.mail}'")
    if not user:
        return {"error": "Invalid email or password"}
    
    if not verify_password(request.password, user["fields"]["password"]):
        return {"error": "Invalid email or password"}
    
    access_token = create_access_token(data={"sub": user["fields"]["mail"]})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
    }

class UpdateLocationRequest(BaseModel):
    latitude: float
    longitude: float

@app.post("/update_location", summary="Update User Location", description="Update the location of the authenticated user.", response_description="Location update status message.")
async def update_location(request: UpdateLocationRequest, current_user: str = Depends(get_current_user)):
    if not current_user:
        return {"error": "Unauthorized"}

    user = TABLE.first(formula=f"{{mail}}='{current_user}'")
    if not user:
        return {"error": "User not found"}
    
    TABLE.update(user["id"], {
        "latitude": request.latitude,
        "longitude": request.longitude
    })

    return {"message": "Location updated successfully"}

@app.get("/last_news", summary="Retrieve Last News", description="Get the latest news items from the agriculture website.")
async def last_news(current_user: str = Depends(get_current_user)):
    if not current_user:
        return {"error": "Unauthorized"}

    response = httpx.get("https://agriculture.gouv.fr/filieres-vegetales")
    if response.status_code != 200:
        return {"error": "Failed to retrieve news"}
    
    pattern = r'<div class="fr-card__body">.*?<h2 class="fr-card__title"><a class="fr-card__link" href="(.*?)">(.*?)</a></h2>.*?<p class="fr-card__desc">(.*?)</p>.*?<p class="fr-card__detail"><span class="fr-card__date">(.*?)</span>'
    matches = re.findall(pattern, response.text, re.DOTALL)
    
    news_items = []
    for match in matches[:5]:
        link, title, description, date = match
        news_items.append({
            "title": title.strip(),
            "link": "https://agriculture.gouv.fr" + link.strip(),
            "description": description.strip(),
            "date": date.strip()
        })
    # for match in matches:
    #     link, title, description, date = match
    #     news_items.append({
    #         "title": title.strip(),
    #         "link": "https://agriculture.gouv.fr" + link.strip(),
    #         "description": description.strip(),
    #         "date": date.strip()
    #     })

    return {"news": news_items}

def clear_esa(soup):
    div_intro = soup.find("div", class_="field--name-field-intro-bhv")
    
    if div_intro:
        # On extrait le texte brut en séparant les paragraphes par un espace
        description_propre = div_intro.get_text(separator=" ", strip=True)
    else:
        # Solution de secours si la structure change : on prend tout le texte sans la date
        description_propre = soup.get_text(separator=" ", strip=True)

    # 2. EXTRACTION DE LA DATE
    # On cible la div qui contient la date de publication
    div_date = soup.find("div", class_="field--name-node-post-date")
    date_propre = ""
    
    if div_date:
        texte_date = div_date.get_text(strip=True)
        # On utilise une expression régulière pour extraire uniquement le format DD/MM/YYYY
        match_date = re.search(r'(\d{2}/\d{2}/\d{4})', texte_date)
        if match_date:
            date_propre = match_date.group(1)
            
    return description_propre, date_propre    

def check_flux_epidemiologique():
    print("Checking flux epidemiologique...")
    rss = feedparser.parse("https://www.plateforme-esa.fr/fr/rss.xml")
    categories_especes = {
        "Bovins (Vaches, Taureaux, Buffles)": ["bovin", "bovine", "dermatose nodulaire", "tuberculose"],
        "Porcins (Porcs, Sangliers)": ["porc", "porcine", "peste porcine", "suidés", "grippe avariable", "influenza porcin"],
        "Ovins/Caprins (Moutons, Chèvres)": ["ovin", "caprin", "mouton", "fièvre catarrhale", "fco", "clavelée"],
        "Volaille (Poulets, Canards, Oiseaux)": ["volaille", "aviaire", "influenza aviaire", "grippe aviaire", "oiseau"]
    }

    for entry in rss.entries:
        titre = entry.title
        lien = entry.link or "Unknown"
        
        # 1. Nettoyage du HTML présent dans la description pour récupérer le texte brut
        soup = BeautifulSoup(entry.description, "html.parser")
        texte_brut = soup.get_text(separator=" ").strip()
        
        # 2. Détection automatique de l'espèce animale concernée
        espece_detectee = "Général / Non spécifié"
        contenu_pour_recherche = (titre + " " + texte_brut).lower()
        
        for espece, mots_cles in categories_especes.items():
            if any(mot in contenu_pour_recherche for mot in mots_cles):
                espece_detectee = espece
                break  # On a trouvé l'espèce principale, on arrête la boucle
        
        description, date_pub = clear_esa(soup)
        resume = description

        # LOGS DE TEST DANS LE TERMINAL
        print("\n--- NOUVELLE ALERTE DETECTÉE ---", flush=True)
        print(f"Titre ({date_pub}): {titre}", flush=True)
        print(f"Espèce ciblée : {espece_detectee}", flush=True)
        print(f"Résumé textuel : {resume}", flush=True)
        print(f"Lien officiel : {lien}", flush=True)
    
    if RSS_TABLE.first(formula=f"{{title}}='{titre}'") is None:
        RSS_TABLE.create({
            "title": titre,
            "link": lien,
            "description": resume,
            "date": entry.published,
            "espece": espece_detectee
        })

scheduler = BackgroundScheduler()
scheduler.add_job(check_flux_epidemiologique, 'interval', seconds=5)
scheduler.start()

if __name__ == "__main__":
    import uvicorn
    # uvicorn main:app --reload --port 8000 ; Refresh automatically when code changes
    # Stop the server before running the test file, otherwise the test will fail because the server is already running
    uvicorn.run(app, host="127.0.0.1", port=8000)