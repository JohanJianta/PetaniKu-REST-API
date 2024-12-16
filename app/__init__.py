from flask import Flask
from flask_restful import Api
from firebase_admin import credentials, initialize_app
from dotenv import load_dotenv
import os

def create_app():
    # Load environment variables from .env
    load_dotenv()
    
    # Initialize Flask app
    app = Flask(__name__)
    api = Api(app)

    # Initialize Firebase Admin
    cred = credentials.Certificate(os.getenv('FIREBASE_KEY'))
    initialize_app(cred)

    # Import and register resources
    from .models import UserModel, PredictionModel, LoginModel
    api.add_resource(UserModel, '/user')
    api.add_resource(PredictionModel, '/user/predictions/<string:prediction_id>', '/user/predictions')
    api.add_resource(LoginModel, '/user/login')

    return app
