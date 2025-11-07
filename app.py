from flask import Flask, request, jsonify
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from urllib.parse import unquote

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]

app = Flask(__name__)

# -----------------------
# GET all pharmacies (with basic info + subscription count)
# -----------------------
@app.route("/pharmacies", methods=["GET"])
def get_pharmacies():
    pharmacies = list(db.pharmacies.find({}, {"_id": 0}))
    for p in pharmacies:
        total_stock = sum(m["stock"] for m in p["inventory"])
        total_subs = db.customers.count_documents({
            "subscriptions.pharmacy": {"$regex": f"^{p['name']}$", "$options": "i"}
        })
        p["total_stock"] = total_stock
        p["total_subscriptions"] = total_subs
    return jsonify(pharmacies)


# -----------------------
# GET a single pharmacy’s inventory (detailed view)
# -----------------------
@app.route("/pharmacy/<name>", methods=["GET"])
def get_pharmacy(name):
    # Decode URL-encoded string
    name = unquote(name)
    
    pharmacy = db.pharmacies.find_one(
        {"name": {"$regex": f"^{name}$", "$options": "i"}},
        {"_id": 0}
    )
    
    if not pharmacy:
        return jsonify({"error": "Pharmacy not found"}), 404

    for med in pharmacy["inventory"]:
        med["subscriptions"] = db.customers.count_documents({
            "subscriptions.medicine": {"$regex": f"^{med['medicine']}$", "$options": "i"},
            "subscriptions.pharmacy": {"$regex": f"^{pharmacy['name']}$", "$options": "i"}
        })
    return jsonify(pharmacy)


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

# -----------------------
# POST update stock for a medicine in a pharmacy
# -----------------------
@app.route("/update_stock", methods=["POST"])
def update_stock():
    data = request.json
    pharmacy_name = data.get("pharmacy")
    medicine_name = data.get("medicine")
    new_stock = data.get("stock")

    if not all([pharmacy_name, medicine_name, isinstance(new_stock, int)]):
        return jsonify({"error": "Invalid data"}), 400

    # Find the pharmacy and update the stock for the specific medicine
    result = db.pharmacies.update_one(
        {
            "name": {"$regex": f"^{pharmacy_name}$", "$options": "i"},
            "inventory.medicine": {"$regex": f"^{medicine_name}$", "$options": "i"}
        },
        {"$set": {"inventory.$.stock": new_stock}}
    )

    if result.modified_count == 0:
        return jsonify({"error": "Pharmacy or medicine not found"}), 404

    return jsonify({"message": f"Stock updated to {new_stock} for {medicine_name} at {pharmacy_name}"}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
