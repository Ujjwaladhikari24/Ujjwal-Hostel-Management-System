"""Application entry point.

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""
import os

from dotenv import load_dotenv

load_dotenv()

from hms import create_app  # noqa: E402  (needs .env loaded first)

app = create_app()


@app.shell_context_processor
def shell_context():
    from hms.extensions import db
    from hms import models

    return {"db": db, **{name: getattr(models, name) for name in dir(models) if name[0].isupper()}}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
