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
BLOB_CONNECTION_STRING = os.getenv("BLOB_CONNECTION_STRING")
CONTAINER_NAME = "product-images"

# --- SEED DATA ---
# Function to seed initial product data
def seed_data():
    if collection.count_documents({}) == 0:
        initial_products = [
            {
                "id": 1, 
                "name": "UltraSlim X1 Laptop", 
                "price": 1299.99, 
                "description": "Experience peak performance in a featherlight package. The UltraSlim X1 features the latest i7 processor, 16GB RAM, and a stunning 14-inch 4K InfinityEdge display. With 12 hours of battery life and a carbon fiber chassis, it's built for professionals on the go.", 
                "category": "Computers & Tablets", 
                "brand": "Apex"
            },
            {
                "id": 2, 
                "name": "NoiseGuard Pro Headphones", 
                "price": 349.99, 
                "description": "Immerse yourself in silence with industry-leading Active Noise Cancellation. These over-ear headphones offer 30 hours of playtime, plush memory foam earcups for all-day comfort, and transparency mode to hear the world when you need to.", 
                "category": "Audio", 
                "brand": "Aura"
            },
            {
                "id": 3, 
                "name": "Visionary 4K Monitor", 
                "price": 499.99, 
                "description": "See every detail with the OptiMax 27-inch IPS panel. Boasting 99% sRGB color accuracy, HDR10 support, and a virtually borderless design, this monitor is perfect for content creators and multitaskers alike. Includes USB-C connectivity.", 
                "category": "Computer Accessories", 
                "brand": "OptiMax"
            },
            {
                "id": 4, 
                "name": "GamerZ Console 5", 
                "price": 499.99, 
                "description": "Next-gen gaming is here. The Console 5 delivers lightning-fast load times with its custom SSD, ray-tracing support for realistic lighting, and up to 120fps gameplay on supported titles. Includes one wireless haptic controller.", 
                "category": "Video Games", 
                "brand": "Nexus"
            },
            {
                "id": 5, 
                "name": "SmartWatch Series 7", 
                "price": 399.99, 
                "description": "Track your fitness, monitor your heart rate, and take calls from your wrist. The Series 7 features an always-on Retina display, ECG app, and water resistance up to 50 meters. The perfect companion for a healthy lifestyle.", 
                "category": "Wearable Technology", 
                "brand": "Vital"
            },
            {
                "id": 6, 
                "name": "BlueBeat Portable Speaker", 
                "price": 129.99, 
                "description": "Take the party anywhere with 360-degree sound and deep bass. The BlueBeat is IPX7 waterproof, making it pool-party proof. Features 15 hours of battery life and allows you to pair two speakers for stereo sound.", 
                "category": "Audio", 
                "brand": "Roam"
            },
            {
                "id": 7, 
                "name": "ProTab Air Tablet", 
                "price": 599.99, 
                "description": "Power and portability combined. The ProTab Air features a 10.9-inch Liquid Retina display and the blazing fast M1 chip, making it powerful enough for video editing yet light enough to hold in one hand. Supports the 2nd Gen Stylus.", 
                "category": "Computers & Tablets", 
                "brand": "Forge"
            },
            {
                "id": 8, 
                "name": "MechKey RGB Keyboard", 
                "price": 149.99, 
                "description": "Dominate the competition with ultra-responsive mechanical red switches. The MechKey features per-key RGB lighting fully customizable via software, a durable aluminum top plate, and a detachable wrist rest for ergonomic comfort.", 
                "category": "Computer Accessories", 
                "brand": "Zenith"
            },
            {
                "id": 9, 
                "name": "CineView 65\" OLED TV", 
                "price": 1999.99, 
                "description": "Experience true blacks and infinite contrast. The CineView OLED features 4K resolution, Dolby Vision IQ, and Dolby Atmos sound for a cinematic home theater experience. Smart features include built-in voice assistants.", 
                "category": "TV & Home Theater", 
                "brand": "Luminos"
            },
            {
                "id": 10, 
                "name": "Bolt External SSD 1TB", 
                "price": 159.99, 
                "description": "Transfer files in seconds with read speeds up to 1050MB/s. The Bolt SSD is shock-resistant, fits in the palm of your hand, and includes encryption software to keep your data safe. Compatible with PC, Mac, and consoles.", 
                "category": "Computer Accessories", 
                "brand": "Velocity"
            }
        ]
        collection.insert_many(initial_products)
        print("Database seeded successfully.")

seed_data()

# --- ROUTES ---

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

# Get all products
@app.route('/', methods=['GET'])
def get_products():
    products = list(collection.find({}, {'_id': 0}).sort('id', 1))
    return jsonify(products)

# Get a single product by ID
@app.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = collection.find_one({"id": product_id}, {'_id': 0})
    return jsonify(product) if product else ("Product not found", 404)

# Add a new product
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

# Update a product
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

# Delete a product
@app.route('/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    result = collection.delete_one({"id": product_id})
    return ("", 200) if result.deleted_count > 0 else ("Product not found", 404)

# --- IMAGE HANDLING ---
# Uploads or updates a product image
@app.route('/upload', methods=['POST'])
def upload_image():
    file = request.files.get('file')
    product_id = request.form.get('productId')

    if not file or not product_id:
        return "File and productId required", 400

    try:
        blob_service = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
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

# Retrieves a product image
@app.route('/<int:product_id>/image', methods=['GET'])
def get_product_image(product_id):
    try:
        blob_service = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
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