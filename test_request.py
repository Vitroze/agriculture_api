import requests
import re

sURL = "http://localhost:8000/"
def test_register():
    payload = {
        "siren": "356000000",
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

sType,sToken = test_login()
# print("Token type:", sType, "Token:", sToken)

def testWebhook():

    headers = {
        "Authorization": f"{sType} {sToken}",
    }

    response = requests.get(sURL + "receive_activities", headers=headers)
    if response.status_code == 200:
        print("Test passed: Received response:", response.json())
    else:
        print("Test failed: Status code", response.status_code, "Response:", response.text)

testWebhook()

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

def get_disease(sType, sToken):
    headers = {
        "Authorization": f"{sType} {sToken}",
    }

    response = requests.get(sURL + "get_alertes_temps_reel", headers=headers)
    if response.status_code == 200:
        print("Test passed: Received response:", response.json())
    else:        
        print("Test failed: Status code", response.status_code, "Response:", response.text)
get_disease(sType, sToken)

# from bs4 import BeautifulSoup
# import re

# # Ton texte brut issu du flux XML
# html_description = """
# <div data-history-node-id="2201" class="layout layout--onecol">
#   <div class="layout__region layout__region--content">
#     <div class="field field--name-field-image-logo-vsi field--type-entity-reference field--label-hidden field__item">
#       <img loading="lazy" src="https://www.plateforme-esa.fr/sites/default/files/styles/medium/public/2021-09/VSI%20Plateforme%20ESA%20-%20Copie.png?itok=MhJlI8KS" width="220" height="72" alt="Logo VSI" class="img-fluid image-style-medium"> 
#     </div> 
    
#     <div class="clearfix text-formatted field field--name-field-intro-bhv field--type-text-long field--label-hidden field__item">
#       <p><strong>Le Bulletin hebdomadaire de veille sanitaire internationale en santé animale (BHVSI-SA)</strong> est élaboré dans le cadre de la thématique Veille Sanitaire Internationale (VSI) de la Plateforme. Il est produit par un comité de rédaction regroupant des personnes de l’Anses, du Cirad, de la DGAl et de INRAE. Les informations, systématiquement sourcées, sont issues des notifications officielles des Etats,&nbsp;de sources non officielles (presse, internet) ainsi que d’un réseau national et international d’experts.</p> <p>Le BHVSI-SA rapporte et met en perspective des signaux et des alertes en santé animale au niveau national et international. Il est publié chaque mardi et concerne les événements de la semaine précédente.</p> 
#       <p><em>Ce bulletin n’engage que son comité de rédaction et non les organismes membres de la Plateforme. Pour toutes questions: <a href="mailto:plateforme.esa@anses.fr">plateforme-esa@anses.fr</a></em></p> 
#       <p><a class="btn btn-info btn-lg" href="https://www.plateforme-esa.fr/bulletins-hebdomadaires-de-veille-sanitaire-internationale-" target="_blank">
#         <span class="text">Accédez à tous les BHVSI-SA </span>&nbsp;
#         <i class="fa fa-icon-right fa-chevron-right" style="word-spacing: -1em;">&nbsp;</i> 
#       </a></p> 
#     </div> 
    
#     <div class="field field--name-field-fichier-pdf-associe field--type-file field--label-hidden field__item">
#       <iframe class="pdf" webkitallowfullscreen mozallowfullscreen allowfullscreen frameborder="no" width="100%" height="1300px" src="https://www.plateforme-esa.fr/libraries/pdf.js/web/viewer.html?file=https%3A%2F%2Fwww.plateforme-esa.fr%2Fsites%2Fdefault%2Ffiles%2F2026-04%2F2026-04-28-BHVSI-SA_0.pdf#page=1&amp;zoom=auto&amp;pagemode=bookmarks" data-src="https://www.plateforme-esa.fr/sites/default/files/2026-04/2026-04-28-BHVSI-SA_0.pdf" title="2026-04-28-BHVSI-SA_0.pdf"></iframe> 
#     </div> 
    
#     <div class="field field--name-field-numero-du-bulletin field--type-integer field--label-inline clearfix"> 
#       <div class="field__label">Numéro du bulletin</div> 
#       <div class="field__item">17</div> 
#     </div> 
    
#     <div class="field field--name-node-post-date field--type-ds field--label-hidden field__item">28/04/2026 - 16:10</div> 
#   </div> 
# </div> 
# """

# import html
# def nettoyer_donnees_esa(html_content):
#     # Regex d'origine qui cible la div complète pour ne rien rater
#     r = re.compile(
#         r'<div[^>]*class=["\']clearfix text-formatted field field--name-field-intro-bhv field--type-text-long field--label-hidden field__item["\'][^>]*>([\s\S]*?)<\/div>', 
#         re.DOTALL
#     )
#     match = r.search(html_content)
    
#     if match:
#         raw_description = match.group(1).strip()
        
#         # 1. Nettoyage initial des balises et entités HTML
#         description = re.sub(r'<[^>]+>', '', raw_description)
#         description = html.unescape(description)
#         description = re.sub(r'\s+', ' ', description).strip()
        
#         # 2. Suppression stricte des phrases demandées
#         phrase_engagement = "Ce bulletin n’engage que son comité de rédaction et non les organismes membres de la Plateforme. Pour toutes questions: plateforme-esa@anses.fr"
#         phrase_acces = "Accédez à tous les BHVSI-SA"
        
#         description = description.replace(phrase_engagement, "")
#         description = description.replace(phrase_acces, "")
        
#         # Nettoyage final des espaces superflus créés par la suppression
#         description = re.sub(r'\s+', ' ', description).strip()
        
#         print("=== DESCRIPTION PROPRE ===")
#         print(description)
#     else:
#         description = "Description non trouvée"
#         print(description)

#     # Extraction de la date (inchangée)
#     r_date = re.compile(
#         r'<div[^>]*class=["\']field field--name-node-post-date field--type-ds field--label-hidden field__item["\'][^>]*>(.*?)<\/div>', 
#         re.DOTALL
#     )
#     match_date = r_date.search(html_content)
#     date_pub = match_date.group(1).strip() if match_date else "Date de publication non trouvée"

#     return description, date_pub
# # Test du script
# description = nettoyer_donnees_esa(html_description)

# print("=== DESCRIPTION PROPRE ===")
# print(description)
