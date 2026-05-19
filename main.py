from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
from db import RSS_TABLE, TOKEN_API_METEO_FRANCE

import users as Users
import feedparser
import os
import httpx
import uvicorn
import re
import html

def createEnv():
    with open(".env", "w") as f:
        f.write("AIRTABLE_TOKEN=your_airtable_token_here\n")
        f.write("AIRTABLE_BASE_ID=your_airtable_base_id_here\n")
        f.write("AIRTABLE_TABLE_USERS=your_airtable_table_users_name_here\n")
        f.write("AIRTABLE_TABLE_NEWS=your_airtable_table_news_name_here\n")
        f.write("TOKEN_GENERATION_SECRET=your_jwt_secret_here\n")

if not os.path.exists(".env"):
    print("No .env file found. Creating a template .env file...")
    createEnv()
    print("Please fill in the .env file with your actual configuration values and restart the application.")
    exit(1)

load_dotenv()

security = HTTPBearer()
app = FastAPI(
    title="Agriculture API",
    description="API for agriculture-related services, including user registration, authentication, location updates, and news retrieval.",
    version="1.0.0",
)

@app.get("/", summary="Root Endpoint", description="Check if the development server is running and the API is ready.")
async def root():
    return {"message": "Development server is running! API is ready."}

class RegisterRequest(BaseModel):
    mail: str
    siren: str
    password: str

async def getSiren(siren: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://recherche-entreprises.api.gouv.fr/search?q={siren}&page=1&per_page=1")
        result = response.json()
        result = result["results"] or []
        if not result or len(result) == 0:
            print(f"No company information found for SIREN: {siren}")
            return {}
        
        result = result[0]

        return result

@app.post("/register", summary="User Registration", description="Register a new user with their SIREN number, email, and password.")
async def register(request: RegisterRequest):
    compagny_info = await getSiren(str(request.siren))
    if not compagny_info.get("siren") or compagny_info["siren"] != request.siren:
        return {"error": "Invalid SIREN number"}

    if Users.isConnected():
        print("User already connected. Please log out before registering a new account.")
        return {"error": "User already connected. Please log out before registering a new account."}

    if Users.exist_user(request.mail, request.siren):
        return {"error": "Email already registered with this SIREN number"}
    
    Users.create_user(request.siren, request.mail, request.password)

    return {"message": "Registration successful"}
    
class LoginRequest(BaseModel):
    mail: str
    password: str

@app.post("/login", summary="User Login", description="Authenticate a user with their email and password.")
async def login(request: LoginRequest):
    user = Users.exist_user(request.mail)
    if not user:
        return {"error": "Invalid email or password"}

    if not Users.verify_password(request.password, user["fields"]["password"]):
        return {"error": "Invalid email or password"}
    
    access_token = Users.create_access_token(data={"mail": user["fields"]["mail"], "userId": user["id"]})
    return {
        "access_token": access_token, 
        "token_type": "bearer",
    }

class UpdateLocationRequest(BaseModel):
    latitude: float
    longitude: float

@app.post("/update_location", summary="Update User Location", description="Update the location of the authenticated user.", response_description="Location update status message.")
async def update_location(request: UpdateLocationRequest, current_user: dict = Depends(Users.get_current_user)):
    if not current_user:
        return {"error": "Unauthorized"}
    
    if not Users.update_location(current_user, request.latitude, request.longitude):
        return {"error": "Failed to update location"}

    return {"message": "Location updated successfully"}

@app.get("/last_news", summary="Retrieve Last News", description="Get the latest news items from the agriculture website.")
async def last_news(current_user: dict = Depends(Users.get_current_user)):
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

    return {"news": news_items}

def clear_esa(html_content): 
    r = re.compile(
        r'<div[^>]*class=["\']clearfix text-formatted field field--name-field-intro-bhv field--type-text-long field--label-hidden field__item["\'][^>]*>([\s\S]*?)<\/div>', 
        re.DOTALL
    )
    match = r.search(html_content)
    
    if match:
        raw_description = match.group(1).strip()
        
        description = re.sub(r'<[^>]+>', '', raw_description)
        description = html.unescape(description)
        description = re.sub(r'\s+', ' ', description).strip()
        
        phrase_engagement = "Ce bulletin n’engage que son comité de rédaction et non les organismes membres de la Plateforme. Pour toutes questions: plateforme-esa@anses.fr"
        phrase_acces = "Accédez à tous les BHVSI-SA"
        
        description = description.replace(phrase_engagement, "")
        description = description.replace(phrase_acces, "")
        
        description = re.sub(r'\s+', ' ', description).strip()
    else:
        description = "Description non trouvée"

    return description

categories_especes = {
    "Bovins (Vaches, Taureaux, Buffles)": ["bovin", "bovine", "dermatose nodulaire", "tuberculose"],
    "Porcins (Porcs, Sangliers)": ["porc", "porcine", "peste porcine", "suidés", "grippe avariable", "influenza porcin"],
    "Ovins/Caprins (Moutons, Chèvres)": ["ovin", "caprin", "mouton", "fièvre catarrhale", "fco", "clavelée"],
    "Volaille (Poulets, Canards, Oiseaux)": ["volaille", "aviaire", "influenza aviaire", "grippe aviaire", "oiseau"]
}
def check_flux_epidemiologique():
    for record in RSS_TABLE.all():
        RSS_TABLE.delete(record["id"])

    rss = feedparser.parse("https://www.plateforme-esa.fr/fr/rss.xml")

    for entry in rss.entries:
        titre = entry.title
        lien = entry.link or "Unknown"
        
        # 1. Nettoyage du HTML présent dans la description pour récupérer le texte brut
        soup = BeautifulSoup(entry.description, "html.parser")
        texte_brut = soup.get_text(separator=" ").strip()
        
        # 2. Détection automatique de l'espèce animale concernée
        espece_detectee = "N/A"
        contenu_pour_recherche = (titre + " " + texte_brut).lower()
        
        for espece, mots_cles in categories_especes.items():
            if any(mot in contenu_pour_recherche for mot in mots_cles):
                espece_detectee = espece
                break
        
        description = clear_esa(entry.description)
        resume = description

        if RSS_TABLE.first(formula=f"{{title}}='{titre}'") is None:
            RSS_TABLE.create({
                "title": titre,
                "link": lien,
                "description": resume,
                "date": entry.published,
                "espece": espece_detectee
            })

scheduler = BackgroundScheduler()
scheduler.add_job(check_flux_epidemiologique, 'interval', minutes=1)
scheduler.start()

@app.get("/get_all_disease", summary="Get All Disease Alerts", description="Retrieve all disease alerts stored in the database.")
async def get_disease(current_user: dict = Depends(Users.get_current_user)):
    if not current_user:
        return {"error": "Unauthorized"}

    records = RSS_TABLE.all()
    diseases = []
    for record in records:
        fields = record.get("fields", {})
        diseases.append({
            "title": fields.get("title", "N/A"),
            "link": fields.get("link", "N/A"),
            "description": fields.get("description", "N/A"),
            "date": fields.get("date", "N/A"),
            "espece": fields.get("espece", "N/A")
        })

    return {"diseases": diseases}

def verifier_risques_technologiques(latitude: float, longitude: float):
    """
    Interroge l'API Géorisques pour obtenir les risques technologiques et chimiques
    (Seveso, nucléaire, ICPE) à une position GPS précise.
    """

    # URL officielle de l'API Géorisques pour les risques par coordonnées
    url = "https://www.georisques.gouv.fr/api/v1/risques/technologiques"
    
    # Paramètres requis par l'API
    params = {
        "lat": latitude,
        "lon": longitude,
        "page": 1,
        "page_size": 10
    }
    
    try:
        # Envoi de la requête GET
        response = httpx.get(url, params=params, timeout=10)
        
        # Si la requête réussit (Code 200)
        if response.status_code == 200:
            data = response.json()
            
            # Extraction des résultats
            etablissements = data.get("data", [])
            
            if not etablissements:
                return {
                    "statut": "Ok",
                    "message": "Aucun site industriel à risque technologique ou chimique détecté à ces coordonnées."
                }
            
            # Structure de retour propre pour ton API / FlutterFlow
            liste_risques = []
            for site in etablissements:
                liste_risques.append({
                    "nom_etablissement": site.get("nom_etablissement"),
                    "commune": site.get("commune"),
                    # Ex: "Seveso seuil haut", "Seveso seuil bas", "Installation classée"
                    "type_risque": site.get("type_activite_ss_techno"), 
                    "description": site.get("textes_presentation_risques")
                })
                
            return {
                "statut": "Alerte_Potentielle",
                "nb_sites_proches": len(liste_risques),
                "sites": liste_risques
            }
            
        else:
            print(f"Erreur API Géorisques: Code {response.status_code}")
            return {"statut": "Erreur", "message": "Impossible de contacter le service de cartographie."}
            
    except httpx.HTTPError as e:
        print(f"Erreur de connexion: {e}")
        return {"statut": "Erreur", "message": "Erreur réseau lors de la vérification des risques."}

def verifier_risques_naturels(latitude: float, longitude: float):
    """
    Interroge l'API Géorisques pour obtenir les risques naturels 
    (inondations, séismes, mouvements de terrain, argiles) à une position GPS précise.
    """
    # URL officielle de l'API Géorisques pour les risques naturels
    url = "https://www.georisques.gouv.fr/api/v1/risques/naturels"
    
    params = {
        "lat": latitude,
        "lon": longitude,
        "page": 1,
        "page_size": 10
    }
    
    try:
        response = httpx.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            risques_bruts = data.get("data", [])
            
            if not risques_bruts:
                return {
                    "statut": "Ok",
                    "message": "Aucun risque naturel majeur répertorié à ces coordonnées."
                }
            
            # Structuration d'une réponse propre pour ton application
            liste_risques_detectes = []
            for item in risques_bruts:
                liste_risques_detectes.append({
                    "nom_commune": item.get("nom_commune"),
                    "code_insee": item.get("code_insee"),
                    # Ex: "Inondation", "Mouvement de terrain", "Séisme"
                    "libelle_risque": item.get("libelle_risque_long"), 
                    # Informations ou descriptif de l'aléa si disponible
                    "description": item.get("textes_presentation_risques", "Risque réglementé sur la commune.")
                })
                
            return {
                "statut": "Risques_Existants",
                "nb_risques": len(liste_risques_detectes),
                "risques": liste_risques_detectes
            }
            
        else:
            print(f"Erreur API Géorisques: Code {response.status_code}")
            return {"statut": "Erreur", "message": "Impossible de contacter le service de cartographie."}
            
    except httpx.HTTPError as e:
        print(f"Erreur de connexion: {e}")
        return {"statut": "Erreur", "message": "Erreur réseau lors de la vérification des risques."}

@app.get("/get_zone_risques_naturels", summary="Check Natural and Technological Risks", description="Check for natural risks (floods, earthquakes, landslides, clay) at specific GPS coordinates.")
async def verifier_risques_naturels_et_technologiques(current_user: dict = Depends(Users.get_current_user)):
    if not current_user:
        return {"error": "Unauthorized"}

    latitude = current_user["fields"].get("latitude")
    longitude = current_user["fields"].get("longitude")

    if latitude is None or longitude is None:
        return {"error": "User location not set. Please update your location first."}

    risques_technologiques = verifier_risques_technologiques(latitude, longitude)
    risques_naturels = verifier_risques_naturels(latitude, longitude)

    return {
        "risques_technologiques": risques_technologiques,
        "risques_naturels": risques_naturels
    }

async def verifier_alertes_temps_reel(latitude: float, longitude: float):
    """
    Trouve le département via les coordonnées GPS, puis extrait 
    les alertes exactes depuis l'API Météo-France (Format V6 /encours).
    """
    url_geo = f"https://api-adresse.data.gouv.fr/reverse/?lon={longitude}&lat={latitude}"
    
    async with httpx.AsyncClient() as client:
        try:
            response_geo = await client.get(url_geo, timeout=5)
            if response_geo.status_code != 200 or not response_geo.json().get("features"):
                return {"statut": "Erreur", "message": "Impossible de géolocaliser le département."}
            
            context = response_geo.json()["features"][0]["properties"].get("context", "")
            departement = context.split(",")[0].strip()
            
            if len(departement) == 1:
                departement = f"0{departement}"

            url_vigilance = "https://public-api.meteofrance.fr/public/DPVigilance/v1/cartevigilance/encours"
            headers = {
                "apikey": TOKEN_API_METEO_FRANCE
            }
            
            response_vigi = await client.get(url_vigilance, headers=headers, timeout=10)

            if response_vigi.status_code == 200:
                data = response_vigi.json()
                
                couleurs_map = {1: "Vert", 2: "Jaune", 3: "Orange", 4: "Rouge"}
                phenomenes_map = {
                    1: "Vent violent", 2: "Pluie-Inondation", 3: "Orages", 
                    4: "Inondation (Crues)", 5: "Neige-Verglas", 6: "Canicule", 
                    7: "Grand Froid", 8: "Avalanches", 9: "Vagues-Submersion"
                }
                
                alertes_actives = []
                couleur_max_commune = "Vert"
                
                periods = data.get("product", {}).get("periods", [])
                if not periods:
                    return {"statut": "Ok", "message": "Aucune donnée de vigilance disponible."}
                
                timelaps_items = periods[0].get("timelaps", {}).get("domain_ids", [])
                
                bloc_departement = None
                for item in timelaps_items:
                    if str(item.get("domain_id")) == str(departement):
                        bloc_departement = item
                        break
                
                if bloc_departement:
                    max_color_id = bloc_departement.get("max_color_id", 1)
                    couleur_max_commune = couleurs_map.get(max_color_id, "Vert")
                    
                    phenomenes = bloc_departement.get("phenomenon_items", [])
                    for p in phenomenes:
                        p_id = int(p.get("phenomenon_id", 0))
                        p_color = int(p.get("phenomenon_max_color_id", 1))
                        
                        if p_color > 1:
                            alertes_actives.append({
                                "phenomene": phenomenes_map.get(p_id, f"Autre Risque ({p_id})"),
                                "niveau": couleurs_map.get(p_color, "Inconnu"),
                                "conseil": f"Alerte {couleurs_map.get(p_color)}. Suivez les consignes de sécurité."
                            })
                
                return {
                    "statut": "Ok",
                    "departement": departement,
                    "alerte_maximale_commune": couleur_max_commune,
                    "risques_en_cours": alertes_actives if alertes_actives else "Aucune alerte en cours. Situation normale."
                }
                
            elif response_vigi.status_code == 401:
                raise HTTPException(status_code=401, detail="Token Météo-France expiré ou invalide.")
            else:
                raise HTTPException(status_code=response_vigi.status_code, detail="Erreur lors de la récupération du flux Météo-France.")
                
        except httpx.HTTPError as e:
            print(f"Erreur réseau HTTPX: {e}")
            raise HTTPException(status_code=503, detail="Le serveur Météo-France ne répond pas ou est inaccessible.")

@app.get("/get_alertes_temps_reel", summary="Check Real-Time Alerts", description="Check for real-time natural disaster alerts and weather warnings at specific GPS coordinates.")
async def get_alertes_temps_reel(current_user: dict = Depends(Users.get_current_user)):
    if not current_user:
        return {"error": "Unauthorized"}

    latitude = current_user["fields"].get("latitude")
    longitude = current_user["fields"].get("longitude")

    if latitude is None or longitude is None:
        return {"error": "User location not set. Please update your location first."}

    alertes = await verifier_alertes_temps_reel(latitude, longitude)
    return alertes

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)