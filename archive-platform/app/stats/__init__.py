from flask import Blueprint
stats_bp = Blueprint("stats", __name__)
from app.stats.routes import *
