from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from dotenv import load_dotenv
import os
import mimetypes
from pymongo import MongoClient
from azure.storage.blob import BlobServiceClient

load_dotenv()

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
client = MongoClient(mongo_uri)
db = client.productdb
collection = db.products

# Azure Blob Config
BLOB_CONN_STR = os.getenv("BLOB_CONN_STR")
CONTAINER_NAME = "product-images"

# --- SEED DATA ---
def seed_data():
    if collection.count_documents({}) == 0:
        initial_products = [
            {"id": 1, "name": "UltraSlim X1 Laptop", "price": 1299.99, "description": "Experience peak performance...", "category": "Computers & Tablets", "brand": "Apex"},
            {"id": 2, "name": "NoiseGuard Pro Headphones", "price": 349.99, "description": "Immerse yourself...", "category": "Audio", "brand": "Aura"},
            {"id": 3, "name": "Visionary 4K Monitor", "price": 499.99, "description": "See every detail...", "category": "Computer Accessories", "brand": "OptiMax"},
            {"id": 4, "name": "GamerZ Console 5", "price": 499.99, "description": "Next-gen gaming...", "category": "Video Games", "brand": "Nexus"},
            {"id": 5, "name": "SmartWatch Series 7", "price": 399.99, "description": "Track your fitness...", "category": "Wearable Technology", "brand": "Vital"},
            {"id": 6, "name": "BlueBeat Portable Speaker", "price": 129.99, "description": "Take the party anywhere...", "category": "Audio", "brand": "Roam"},
            {"id": 7, "name": "ProTab Air Tablet", "price": 599.99, "description": "Power and portability...", "category": "Computers & Tablets", "brand": "Forge"},
            {"id": 8, "name": "MechKey RGB Keyboard", "price": 149.99, "description": "Dominate the competition...", "category": "Computer Accessories", "brand": "Zenith"},
            {"id": 9, "name": "CineView 65\" OLED TV", "price": 1999.99, "description": "Experience true blacks...", "category": "TV & Home Theater", "brand": "Luminos"},
            {"id": 10, "name": "Bolt External SSD 1TB", "price": 159.99, "description": "Transfer files in seconds...", "category": "Computer Accessories", "brand": "Velocity"}
        ]
        collection.insert_many(initial_products)
        print("Database seeded successfully.")

seed_data()

# --- ROUTES ---

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/', methods=['GET'])
def get_products():
    products = list(collection.find({}, {'_id': 0}).sort('id', 1))
    return jsonify(products)

@app.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = collection.find_one({"id": product_id}, {'_id': 0})
    return jsonify(product) if product else ("Product not found", 404)

@app.route('/', methods=['POST'])
def add_product():
    if not request.json:
        return "Invalid input", 400
    last_product = collection.find_one(sort=[("id", -1)])
    new_id = (last_product['id'] + 1) if last_product else 1
    new_product = request.json
    new_product['id'] = new_id
    collection.insert_one(new_product)
    del new_product['_id']
    return jsonify(new_product)

@app.route('/', methods=['PUT'])
def update_product():
    if not request.json or 'id' not in request.json:
        return "Invalid input", 400
    update_data = request.json
    target_id = update_data['id']
    result = collection.update_one({"id": target_id}, {"$set": update_data})
    if result.matched_count == 0:
        return "Product not found", 404
    updated_product = collection.find_one({"id": target_id}, {'_id': 0})
    return jsonify(updated_product)

@app.route('/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    result = collection.delete_one({"id": product_id})
    return ("", 200) if result.deleted_count > 0 else ("Product not found", 404)

# --- IMAGE HANDLING ---

@app.route('/upload', methods=['POST'])
def upload_image():
    file = request.files.get('file')
    product_id = request.form.get('productId')

    if not file or not product_id:
        return "File and productId required", 400

    try:
        blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
        container_client = blob_service.get_container_client(CONTAINER_NAME)
        
        if not container_client.exists():
            container_client.create_container()

        old_blobs = container_client.list_blobs(name_starts_with=f"{product_id}.")
        for blob in old_blobs:
            container_client.delete_blob(blob.name)

        ext = os.path.splitext(file.filename)[1].lower()
        if not ext:
            ext = ".jpg" 
            
        filename = f"{product_id}{ext}"
        blob_client = container_client.get_blob_client(filename)
        blob_client.upload_blob(file, overwrite=True)

        return jsonify({"status": "uploaded", "filename": filename})

    except Exception as e:
        print(f"Upload Error: {e}")
        return "Upload failed", 500

@app.route('/<int:product_id>/image', methods=['GET'])
def get_product_image(product_id):
    try:
        blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
        container_client = blob_service.get_container_client(CONTAINER_NAME)

        blobs = list(container_client.list_blobs(name_starts_with=f"{product_id}."))
        
        if not blobs:
            return "Image not found", 404

        # Take the first match
        blob_name = blobs[0].name
        blob_client = container_client.get_blob_client(blob_name)
        
        image_data = blob_client.download_blob().readall()
        
        mime_type, _ = mimetypes.guess_type(blob_name)
        return Response(image_data, mimetype=mime_type or "image/jpeg")

    except Exception:
        return "Image not found", 404

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3002))
    print(f"Listening on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port)