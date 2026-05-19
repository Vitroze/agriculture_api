from dotenv import load_dotenv
from pyairtable import Api
import os

load_dotenv()
API = Api(os.getenv("AIRTABLE_TOKEN"))
TABLE = API.table(os.getenv("AIRTABLE_BASE_ID"), os.getenv("AIRTABLE_TABLE_USERS"))
RSS_TABLE = API.table(os.getenv("AIRTABLE_BASE_ID"), os.getenv("AIRTABLE_TABLE_NEWS"))
TOKEN_API_METEO_FRANCE = os.getenv("TOKEN_API_METEO_FRANCE")
