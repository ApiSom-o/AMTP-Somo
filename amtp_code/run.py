"""Start the demo:  python run.py   then open http://127.0.0.1:5000"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"AMTP user demo → http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
