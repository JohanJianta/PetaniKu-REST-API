from datetime import datetime
from firebase_admin import firestore

def _get_document(ref, check_deleted=True):
    """
    Retrieves a document reference and optionally checks if it's deleted.
    """
    doc = ref.get()
    if not doc.exists:
        return None
    doc_data = doc.to_dict()
    if check_deleted and doc_data.get('is_deleted', True):
        return None
    return doc_data

def _serialize_rice_field_coordinates(coordinates):                        
    rice_field_coordinates = []
    for coordinate in coordinates:
        coord_map = {
            "latitude": coordinate.latitude,
            "longitude": coordinate.longitude,
        }
        rice_field_coordinates.append(coord_map)
    return rice_field_coordinates

def _serialize_images(images):
    serialized_images = []
    for image in images:
        image_map = {
            'latitude': image['coordinate'].latitude,
            'longitude': image['coordinate'].longitude,
            'level': image['level'],
            'url': image['url'],
        }
        serialized_images.append(image_map)
    return serialized_images

class FirestoreClient:
    def __init__(self):
        self.db = firestore.client()
        self.users_collection = self.db.collection('users')
    
    def get_user(self, user_id):
        """
        Retrieves a specific user by ID.
        """
        user_data = _get_document(self.users_collection.document(user_id))
        if user_data:
            user_data.pop('is_deleted', None)
        return user_data

    def get_user_by_phone(self, phone):
        """
        Check if an user with the given phone number exists.
        """
        user_docs = self.users_collection.where('phone', '==', phone).where('is_deleted', '==', False).stream()
        return next(user_docs, None)

    # def get_all_users(self):
    #     users = self.users_collection.where('is_deleted', '==', False).stream()
    #     return [user.to_dict() for user in users]

    def add_user(self, name, phone):
        """
        Add a new user if the phone number is unique.
        """
        if name == '':
            raise ValueError('Nama tidak boleh kosong')
        if phone == '':
            raise ValueError('Nomor HP tidak boleh kosong')
        if self.get_user_by_phone(phone):
            raise ValueError('Nomor HP sudah terdaftar')

        data = {'name': name, 'phone': phone, 'is_deleted': False}
        return self.users_collection.add(data)[1].id

    def add_rice_field(self, user_id, coordinates, area):
        """
        Add a new rice_field for an user
        """
        user_ref = self.users_collection.document(user_id)
        if not _get_document(user_ref):
            return False
        
        if not coordinates or len(coordinates) < 3:
            raise ValueError('coordinates minimal berisikan 3 titik')
        if area == 0:
            raise ValueError('area tidak boleh bernilai 0')

        geopoints = [firestore.GeoPoint(coord['latitude'], coord['longitude']) for coord in coordinates]
        user_ref.collection('rice_fields').add({'coordinates': geopoints, 'area': area, 'created_time': datetime.now()})
        return True
    
    def delete_user(self, user_id):
        """
        Soft-deletes an user by ID.
        """
        user_ref = self.users_collection.document(user_id)
        if not _get_document(user_ref):
            return False
        
        user_ref.update({'is_deleted': True})
        return True

    def get_prediction(self, user_id, prediction_id):
        """
        Retrieves a specific prediction document by ID.
        """
        prediction_data = _get_document(self.users_collection.document(user_id).collection('predictions').document(prediction_id))
        if not prediction_data:
            return None
        
        rice_field = prediction_data['rice_field'].get().to_dict()
        prediction_data['area'] = rice_field['area']
        prediction_data['rice_field'] = _serialize_rice_field_coordinates(rice_field['coordinates'])
        prediction_data['images'] = _serialize_images(prediction_data['images'])
        prediction_data['created_time'] = prediction_data['created_time'].isoformat()

        prediction_data.pop('is_deleted', None)
        return prediction_data

    def get_all_predictions(self, user_id, limit=10):
        """
        Retrieves all prediction documents for a specific user.
        """
        predictions_docs = self.users_collection.document(user_id).collection('predictions').where('is_deleted', '==', False).order_by('created_time', direction=firestore.Query.DESCENDING).limit(limit).stream()

        prediction_data = []
        for doc in predictions_docs:
            data = doc.to_dict()
            data['created_time'] = data['created_time'].isoformat()
            data['prediction_id'] = doc.id
            data.pop('rice_field', None)
            data.pop('is_deleted', None)
            data.pop('images', None)
            prediction_data.append(data)

        return prediction_data
    
    def add_prediction(self, user_id, data, secure_urls, levels, coordinates):
        """
        Adds a new prediction document to a specific user.
        """
        images = [
            {
                'url': url,
                'level': lvl,
                'coordinate': firestore.GeoPoint(coord['latitude'], coord['longitude'])
            } for url, lvl, coord in zip(secure_urls, levels, coordinates)
        ]

        data = {**data, 'images': images, 'is_deleted': False, 'created_time': datetime.now()}
        prediction_data = self.users_collection.document(user_id).collection('predictions').add(data)[1].get().to_dict()

        rice_field = prediction_data['rice_field'].get().to_dict()
        prediction_data['area'] = rice_field['area']
        prediction_data['rice_field'] = _serialize_rice_field_coordinates(rice_field['coordinates'])
        prediction_data['images'] = _serialize_images(prediction_data['images'])
        prediction_data['created_time'] = prediction_data['created_time'].isoformat()
        return prediction_data

    def delete_prediction(self, user_id, prediction_id):
        """
        Soft-deletes a prediction document by ID.
        """
        prediction_ref = self.users_collection.document(user_id).collection('predictions').document(prediction_id)
        if not _get_document(prediction_ref):
            return False
        
        prediction_ref.update({'is_deleted': True})
        return True
    
    def get_latest_rice_field(self, user_id):
        """
        Retrieves the most recent rice_fields document for a specific user based on created_time.
        """
        rice_field_doc = self.users_collection.document(user_id).collection('rice_fields').order_by('created_time', direction=firestore.Query.DESCENDING).limit(1).stream()
        return next(rice_field_doc, None)
    
    def get_prediction_summary_by_rice_field(self, user_id, rice_field_doc):
        rice_field_data = rice_field_doc.to_dict()
        rice_field_data['created_time'] = rice_field_data['created_time'].isoformat()
        rice_field_data['coordinates'] = _serialize_rice_field_coordinates(rice_field_data['coordinates'])

        prediction_docs = list(self.users_collection.document(user_id).collection('predictions').where('is_deleted', '==', False).where('rice_field', '==', rice_field_doc.reference).order_by('created_time', direction=firestore.Query.DESCENDING).stream())
        if not prediction_docs:
            return None, rice_field_data
        
        summary_keys = ["season", "paddy_age", "planting_type", "images", "created_time"]
        statistic_keys = ["nitrogen_required", "urea_required", "fertilizer_required", "yields", "created_time"]
        
        statistic_list = []
        for doc in prediction_docs:
            data = doc.to_dict()
            data['created_time'] = data['created_time'].isoformat()

            if len(statistic_list) == 0:
                summary_data = {key: data[key] for key in summary_keys}
                summary_data['images'] = _serialize_images(summary_data['images'])
            
            sub_data = {key: data[key] for key in statistic_keys}
            statistic_list.append(sub_data)
        summary_data['statistics'] = statistic_list

        return summary_data, rice_field_data