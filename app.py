from flask import Flask, request, jsonify
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]

app = Flask(__name__)

# -----------------------
# GET all pharmacies
# -----------------------
@app.route("/pharmacies", methods=["GET"])
def get_pharmacies():
    pharmacies = list(db.pharmacies.find({}, {"_id": 0}))
    return jsonify(pharmacies)


# -----------------------
# GET unique medicines
# -----------------------
@app.route("/medicines", methods=["GET"])
def get_medicines():
    pipeline = [
        {"$unwind": "$inventory"},
        {"$group": {"_id": "$inventory.medicine"}},
        {"$sort": {"_id": 1}}
    ]
    meds = [doc["_id"] for doc in db.pharmacies.aggregate(pipeline)]
    return jsonify(meds)


# -----------------------
# POST search medicine (case-insensitive)
# -----------------------
@app.route("/search", methods=["POST"])
def search_medicine():
    data = request.json
    med_name = data.get("medicine", "").strip()

    if not med_name:
        return jsonify([])

    regex_query = {"inventory.medicine": {"$regex": f"^{med_name}$", "$options": "i"}}
    pharmacies = db.pharmacies.find(regex_query)

    results = []
    for p in pharmacies:
        for item in p["inventory"]:
            if item["medicine"].lower() == med_name.lower() and item["stock"] > 0:
                results.append({
                    "pharmacy": p["name"],
                    "stock": item["stock"],
                    "address": p["address"]
                })
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
