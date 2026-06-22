from flask import Blueprint
reg_bp = Blueprint("regulations", __name__)
from app.regulations.routes import *
