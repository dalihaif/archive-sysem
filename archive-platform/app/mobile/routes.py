from flask import render_template
from app.mobile import mobile_bp

@mobile_bp.route("/borrow")
def borrow_form():
    return render_template("mobile/borrow_form.html")

@mobile_bp.route("/my-borrows")
def my_borrows():
    return render_template("mobile/my_borrows.html")
