from datetime import datetime
from firebase_admin import firestore

class FirestoreClient:
    def __init__(self):
        self.db = firestore.client()
        self.users_collection = self.db.collection('users')
    
    def get_user(self, user_id):
        """
        Retrieves a specific user by ID.
        """
        user_doc = self.users_collection.document(user_id).get()
        if not user_doc.exists:
            return None
        
        user_data = user_doc.to_dict()
        if user_data.get('is_deleted', True):
            return None
        
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

    def add_rice_fields(self, user_id, coordinates, area):
        """
        Add a new rice_fields for an user
        """
        user_ref = self.users_collection.document(user_id)
        if not user_ref.get().exists or user_ref.get().to_dict().get('is_deleted', True):
            return False
        
        if not coordinates:
            raise ValueError('coordinates tidak boleh kosong')
        
        if len(coordinates) < 3:
            raise ValueError('coordinates minimal berisikan 3 titik')
            
        if area == 0:
            raise ValueError('area tidak boleh bernilai 0')
        
        geopoints = []
        for coord in coordinates:
            geopoints.append(firestore.GeoPoint(coord['latitude'], coord['longitude']))

        user_ref.collection('rice_fields').add({'coordinates': geopoints, 'area': area, 'create_time': datetime.now()})
        return True
    
    def delete_user(self, user_id):
        """
        Soft-deletes an user by ID.
        """
        user_ref = self.users_collection.document(user_id)
        if not user_ref.get().exists or user_ref.get().to_dict().get('is_deleted', True):
            return False
        
        user_ref.update({'is_deleted': True})
        return True

    def get_prediction(self, user_id, prediction_id):
        """
        Retrieves a specific prediction document by ID.
        """
        prediction_doc = self.users_collection.document(user_id).collection('predictions').document(prediction_id).get()
        if not prediction_doc.exists:
            return None
        
        prediction_data = prediction_doc.to_dict()
        if prediction_data.get('is_deleted', True):
            return None
        
        prediction_data['create_time'] = prediction_data['create_time'].isoformat()
        rice_field = prediction_data['rice_field'].get().to_dict()
        prediction_data['area'] = rice_field['area']
                    
        coordinate_maps = []
        for coordinate in rice_field['coordinates']:
            coord_map = {
                "latitude": coordinate.latitude,
                "longitude": coordinate.longitude,
            }
            coordinate_maps.append(coord_map)
        prediction_data['rice_field'] = coordinate_maps
        
        images = []
        for image in prediction_data['images']:
            image_map = {
                'latitude': image['coordinate'].latitude,
                'longitude': image['coordinate'].longitude,
                'level': image['level'],
                'url': image['url'],
            }
            images.append(image_map)
        prediction_data['images'] = images

        prediction_data.pop('is_deleted', None)
        return prediction_data

    def get_all_predictions(self, user_id):
        """
        Retrieves all prediction documents for a specific user.
        """
        predictions_docs = self.users_collection.document(user_id).collection('predictions').where('is_deleted', '==', False).stream()

        prediction_data = []
        for doc in predictions_docs:
            data = doc.to_dict()
            data['create_time'] = data['create_time'].isoformat()
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
        images = []
        for url, lvl, coord in zip(secure_urls, levels, coordinates):
            img = {
                'url': url,
                'level': lvl,
                'coordinate': firestore.GeoPoint(coord['latitude'], coord['longitude'])
            }
            images.append(img)

        data = {**data, 'images': images, 'is_deleted': False, 'create_time': datetime.now()}
        prediction_id = self.users_collection.document(user_id).collection('predictions').add(data)[1].id
        
        prediction_data = self.get_prediction(user_id, prediction_id)
        if not prediction_data:
            raise Exception("Terjadi kesalahan ketika mengambil data pengecekan tanaman")
        
        return prediction_data

    def delete_prediction(self, user_id, prediction_id):
        """
        Soft-deletes a prediction document by ID.
        """
        prediction_ref = self.users_collection.document(user_id).collection('predictions').document(prediction_id)
        if not prediction_ref.get().exists or prediction_ref.get().to_dict().get('is_deleted', True):
            return False
        
        prediction_ref.update({'is_deleted': True})
        return True
    
    def get_latest_rice_fields(self, user_id):
        """
        Retrieves the most recent rice_fields document for a specific user based on create_time.
        """
        rice_fields_ref = self.users_collection.document(user_id).collection('rice_fields')
        rice_fields_doc = rice_fields_ref.order_by('create_time', direction=firestore.Query.DESCENDING).limit(1).stream()
        return next(rice_fields_doc, None)
    
    def get_all_predictions_by_rice_fields(self, user_id, rice_fields_doc):
        prediction_docs = self.users_collection.document(user_id).collection('predictions').where('is_deleted', '==', False).where('rice_field', '==', rice_fields_doc.reference).stream()

        prediction_data = []
        for doc in prediction_docs:
            prediction_data.append(self.get_prediction(user_id, doc.id))
        return prediction_data