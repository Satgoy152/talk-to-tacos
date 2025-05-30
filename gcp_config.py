import os
from google.cloud import secretmanager
from dotenv import load_dotenv

load_dotenv()

# GCP Configuration
PROJECT_ID = os.getenv('GCP_PROJECT_ID')
INSTANCE_CONNECTION_NAME = os.getenv('INSTANCE_CONNECTION_NAME')
DB_USER = os.getenv('DB_USER')
DB_NAME = os.getenv('DB_NAME')
REGION = os.getenv('GCP_REGION', 'us-central1')

def get_db_password():
    """Retrieve database password from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/db-password1/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Database connection configuration
DB_CONFIG = {
    'project_id': PROJECT_ID,
    'instance_connection_name': INSTANCE_CONNECTION_NAME,
    'database': DB_NAME,
    'user': DB_USER,
    'password': get_db_password,
    'region': REGION
} 