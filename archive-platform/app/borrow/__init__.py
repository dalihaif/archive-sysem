from flask import Blueprint
borrow_bp = Blueprint("borrow", __name__)
from app.borrow.routes import *
