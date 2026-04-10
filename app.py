from flask import Flask

app = Flask(__name__)


@app.route("/")
def index():
    return "Mock Message Center — Phase 0 OK"


if __name__ == "__main__":
    app.run(debug=True, port=8080)
