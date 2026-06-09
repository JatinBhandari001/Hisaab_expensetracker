"""Entry point — run with: python app.py"""
from expense import app

if __name__ == "__main__":
    app.run(debug=False, port=4848)
