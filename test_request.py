import requests
import re

sURL = "http://localhost:8000/"
def test_register():
    payload = {
        "siret": "356000000",
        "mail": "test@example.com",
        "password": "testpassword"
    }
    response = requests.post(sURL + "register", json=payload)
    if response.status_code == 200:
        print("Test passed: Received response:", response.json())
    else:
        print("Test failed: Status code", response.status_code, "Response:", response.text)

#test_register()

def test_login():
    payload = {
        "mail": "test@example.com",
        "password": "testpassword"
    }
    response = requests.post(sURL + "login", json=payload)
    if response.status_code == 200:
        print("Test passed: Received response:", response.json())

        response = response.json()
        sType = response.get("token_type")
        sToken = response.get("access_token")

        return sType, sToken
    else:
        print("Test failed: Status code", response.status_code, "Response:", response.text)

# sType,sToken = test_login()
# print("Token type:", sType, "Token:", sToken)

def last_news(sType, sToken):
    # Error decoding token: 'HTTPBearer' object has no attribute 'credentials'
    headers = {
        "Authorization": f"{sType} {sToken}",
        "Content-Type": "application/json",
    }

    print(headers)
    response = requests.get(sURL + "last_news", headers=headers)
    if response.status_code == 200:
        print("Test passed: Received response:", response.json())
    else:
        print("Test failed: Status code", response.status_code, "Response:", response.text)

#last_news(sType, sToken)

def update_location(sType, sToken):
    headers = {
        "Authorization": f"{sType} {sToken}",
    }

    payload = {
        "latitude": 48.8566,
        "longitude": 2.3522
    }

    response = requests.post(sURL + "update_location", json=payload, headers=headers)
    if response.status_code == 200:
        print("Test passed: Received response:", response.json())
    else:
        print("Test failed: Status code", response.status_code, "Response:", response.text)
# update_location(sType, sToken)

from bs4 import BeautifulSoup
import re

# Ton texte brut issu du flux XML
html_description = """
<div data-history-node-id="2214" class="layout layout--onecol"> 
    <div class="layout__region layout__region--content"> 
        <div class="clearfix text-formatted field field--name-field-intro-bhv field--type-text-long field--label-hidden field__item">
            <p><strong>Le Bulletin hebdomadaire de veille sanitaire internationale en santé animale (BHVSI-SA)</strong> est élaboré...</p> 
            <p>Le BHVSI-SA rapporte et met en perspective des signaux...</p> 
            <p><em>Ce bulletin n’engage que son comité de rédaction...</em></p> 
        </div> 
        <div class="field field--name-field-numero-du-bulletin field--type-integer field--label-inline clearfix"> 
            <div class="field__label">Numéro du bulletin</div> 
            <div class="field__item">18</div> 
        </div> 
        <div class="field field--name-node-post-date field--type-ds field--label-hidden field__item">05/05/2026 - 16:36</div> 
    </div> 
</div>
"""

def nettoyer_donnees_esa(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    
    # 1. EXTRACTION DE LA DESCRIPTION PURE
    # On cible la div qui contient spécifiquement l'introduction textuelle
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

# Test du script
description, date_pub = nettoyer_donnees_esa(html_description)

print("=== DESCRIPTION PROPRE ===")
print(description)
print("\n=== DATE SÉPARÉE ===")
print(date_pub)