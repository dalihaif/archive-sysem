from flask import Blueprint
destroy_bp = Blueprint("destroy", __name__)
from app.destroy.routes import *
