from flask import Blueprint
transfer_bp = Blueprint("transfer", __name__)
from app.transfer.routes import *
