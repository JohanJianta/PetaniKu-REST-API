from flask_restful import Resource, abort
from flask import request
from functools import wraps
from .firestore import FirestoreClient
from .prediction_utils import PredictionUtils
from .auth_utils import verify_token, generate_token
from .upload_image import upload_to_cloudinary
from .geospatial_utils import GeospatialUtils
import json

# Initialize Firestore client
firestore_client = FirestoreClient()

# Initialize Prediction Utils
prediction_utils = PredictionUtils()

# Initialize Prediction Utils
geospatial_utils = GeospatialUtils()


def token_required(f):  # Decorator for token validation
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return {'pesan': 'Token tidak ditemukan'}, 401

        try:
            token = auth_header.split(' ')[1]
            decoded_token = verify_token(token)
            request.user_id = decoded_token['user_id']
        except ValueError as e:
            return {'pesan': str(e)}, 401

        return f(*args, **kwargs)
    return decorated


def _validate_points(points, field_name='points'):
    """
    Validate that points is a list containing list of valid latitude (first element) and longitude (second element).
    """
    if not isinstance(points, list):
        raise ValueError(f'{field_name} harus berupa list')

    for point in points:
        if not isinstance(point, list) or not (isinstance(point[0], (int, float)) and isinstance(point[1], (int, float))):
            raise ValueError(f'element {field_name} harus berupa list koordinat [latitude, longitude]')

        if not (-90 <= point[0] <= 90 and -180 <= point[1] <= 180):
            raise ValueError('Nilai latitude atau longitude tidak valid')


class LoginModel(Resource):
    def post(self):
        """
        Authenticate an user and return a JWT token.
        """
        data = request.get_json()
        if not data or 'phone' not in data:
            abort(400, pesan='phone diperlukan')

        phone = data.get('phone')
        if not isinstance(phone, str) or not phone.strip():
            abort(400, pesan='phone harus berupa string dan tidak boleh kosong')

        user_doc = firestore_client.get_user_by_phone(phone.strip())
        if not user_doc:
            abort(404, pesan='Akun tidak ditemukan')

        token = generate_token(user_doc.id)
        return {'pesan': 'Login berhasil', 'token': token}, 200


class UserModel(Resource):
    @token_required
    def get(self):
        """
        Get an user by user_id
        """
        user_id = request.user_id
        if not user_id:
            abort(400, pesan='user_id diperlukan')

        user_data = firestore_client.get_user(user_id)
        if not user_data:
            abort(404, pesan='Akun tidak ditemukan')

        rice_field_doc = firestore_client.get_latest_rice_field(user_id)
        if not rice_field_doc:
            user_data.update({
                'summary': None,
                'rice_field': None,
            })
            return user_data, 200

        result_dict = firestore_client.get_prediction_summary_by_rice_field(user_id, rice_field_doc)
        user_data.update({
            'rice_field': result_dict['rice_field'],
            'summary': result_dict['summary'],
        })
        return user_data, 200

    def post(self):
        """
        Add a new user if the phone number is unique.
        """
        data = request.get_json()
        if not data or 'name' not in data or 'phone' not in data:
            abort(400, pesan='name dan phone diperlukan')

        name = data.get('name')
        phone = data.get('phone')
        if not isinstance(name, str) or not isinstance(phone, str) or not name.strip() or not phone.strip():
            abort(400, pesan='name dan phone harus berupa string dan tidak boleh kosong')

        name = name.strip()
        phone = phone.strip()

        if firestore_client.get_user_by_phone(phone):
            abort(400, pesan='Nomor HP sudah terdaftar')

        user_id = firestore_client.add_user(name, phone)
        token = generate_token(user_id)
        return {'pesan': 'Pendaftaran akun berhasil', 'token': token}, 201

    @token_required
    def put(self):
        """
        Update user's rice_field (by creating a new document)
        """
        user_id = request.user_id
        if not user_id:
            abort(400, pesan='user_id diperlukan')

        data = request.get_json()
        if not data:
            abort(400, pesan='Payload JSON diperlukan')

        area = data.get('area')
        if area is None or not isinstance(area, (int, float)) or area <= 0:
            abort(400, pesan='area harus berupa angka positif')

        polygon = data.get('polygon')
        if not polygon or not isinstance(polygon, list) or len(polygon) < 4:
            abort(400, pesan='polygon harus berupa list dan minimal berisikan 4 titik')

        try:
            _validate_points(polygon, 'polygon')
        except ValueError as e:
            abort(400, pesan=str(e))

        max_yield = prediction_utils.predict_yield(area, [])
        success = firestore_client.add_rice_field(user_id, polygon, area, max_yield)
        if not success:
            abort(404, pesan='Akun tidak ditemukan')
        return {'pesan': 'Area lahan padi berhasil diperbarui'}, 200

    @token_required
    def delete(self):
        """
        Soft-delete an user by document ID.
        """
        user_id = request.user_id
        if not user_id:
            abort(400, pesan='user_id diperlukan')

        success = firestore_client.delete_user(user_id)
        if not success:
            abort(404, pesan='Akun tidak ditemukan')
        return {'pesan': 'Akun berhasil dihapus'}, 200


class PredictionModel(Resource):
    @token_required
    def get(self, prediction_id=None):
        """
        Get a specific prediction or all predictions for an user.
        """
        user_id = request.user_id
        if not user_id:
            abort(400, pesan='user_id diperlukan')

        user_data = firestore_client.get_user(user_id)
        if not user_data:
            abort(404, pesan='Akun tidak ditemukan')

        if prediction_id:
            prediction_data = firestore_client.get_prediction(user_id, prediction_id)
            if not prediction_data:
                abort(404, pesan='Pengecekan tanaman tidak ditemukan')
            return prediction_data, 200
        else:
            prediction_data = firestore_client.get_all_predictions(user_id)
            return prediction_data, 200

    @token_required
    def post(self):
        """
        Add a new prediction for an user.
        """
        user_id = request.user_id
        if not user_id:
            abort(400, pesan='user_id diperlukan')

        user_data = firestore_client.get_user(user_id)
        if not user_data:
            abort(404, pesan='Akun tidak ditemukan')

        rice_field_doc = firestore_client.get_latest_rice_field(user_id)
        if not rice_field_doc:
            abort(400, pesan='Anda perlu melakukan scan lahan terlebih dahulu')
        rice_field_data = rice_field_doc.to_dict()

        try:
            payload = json.loads(request.form.get('payload', '{}'))
            season = payload.get('season')
            planting_type = payload.get('planting_type')
            paddy_age = payload.get('paddy_age')
            points = payload.get('points')

            # Define expected field types
            expected_types = {
                'season': str,
                'planting_type': str,
                'paddy_age': int,
                'points': list
            }

            # Validate required fields and their types
            for field, expected_type in expected_types.items():
                value = payload.get(field)
                if value is None:
                    raise ValueError(f'{field} tidak boleh kosong')
                if not isinstance(value, expected_type):
                    raise ValueError(f'{field} harus berupa tipe {expected_type.__name__}')

            if not season == 'Dry' and not season == 'Wet':
                raise ValueError("season harus berupa Dry/Wet")
            if not planting_type == 'Transplanted' and not planting_type == 'Direct Seeded':
                raise ValueError("planting_type harus berupa Transplanted/Direct Seeded")
            _validate_points(points)

            # Validate uploaded images
            if 'images' not in request.files:
                raise ValueError(pesan='images diperlukan')
            images = request.files.getlist('images')
            if len(images) > 10:
                raise ValueError('Maksimal 10 gambar dapat diunggah')
            for image in images:
                if image.filename == '' or not image.filename.endswith(('.jpg', '.jpeg', '.png')):
                    raise ValueError('Format gambar harus berupa jpg, jpeg, atau png')
            if len(images) != len(points):
                raise ValueError('Jumlah gambar harus sama dengan jumlah koordinat')

            # Retrieve nutrition (nitrogen) prediction
            levels, urea_required = prediction_utils.predict_nutrition(
                images, season, planting_type, paddy_age, rice_field_data['area']
            )

            # Cluster points using dbscan
            point_levels = [[point[1], point[0], level] for point, level in zip(points, levels)]
            boundary_coords = [[point.longitude, point.latitude] for point in rice_field_data['polygon']]
            dbscan_result = geospatial_utils.cluster_points(point_levels, boundary_coords)

            # Retrieve yield prediction
            lcc_areas = [(dbscan_data["area"], dbscan_data["level"]) for dbscan_data in dbscan_result]
            current_yield = prediction_utils.predict_yield(rice_field_data['area'], lcc_areas, planting_type)

            # Upload all images to Cloudinary
            secure_urls = upload_to_cloudinary(images)
            # secure_urls = ['' for i in points]

            data = {
                'season': season,
                'planting_type': planting_type,
                'paddy_age': paddy_age,
                'urea_required': urea_required,
                'yield': current_yield,
                'rice_field': rice_field_doc.reference,
            }

            prediction_data = firestore_client.add_prediction(user_id, data, dbscan_result, secure_urls)
            return prediction_data, 201
        except ValueError as e:
            abort(400, pesan=str(e))
        except json.JSONDecodeError:
            abort(400, pesan='Payload harus berupa JSON yang valid')
        except Exception as e:
            abort(500, pesan=str(e))

    @token_required
    def delete(self, prediction_id=None):
        """
        Soft-delete a prediction for an user.
        """
        user_id = request.user_id
        if not user_id:
            abort(400, pesan='user_id diperlukan')

        user_data = firestore_client.get_user(user_id)
        if not user_data:
            abort(404, pesan='Akun tidak ditemukan')

        if not prediction_id:
            abort(404, pesan='prediction_id diperlukan')

        success = firestore_client.delete_prediction(user_id, prediction_id)
        if not success:
            abort(404, pesan='Pengecekan tanaman tidak ditemukan')

        return {'pesan': 'Pengecekan tanaman berhasil dihapus'}, 200
