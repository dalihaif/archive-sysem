from flask import Blueprint
import_bp = Blueprint("import_data", __name__)
from app.import_data.routes import *
