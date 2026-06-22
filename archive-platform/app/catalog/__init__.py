from flask import Blueprint
catalog_bp = Blueprint("catalog", __name__)
from app.catalog.routes import *
