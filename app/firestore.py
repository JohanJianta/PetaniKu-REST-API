from datetime import datetime
from firebase_admin import firestore
from google.cloud.firestore import GeoPoint


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
    doc_data.pop('is_deleted', None)
    return doc_data


def _convert_to_geopoints(coordinates):
    return [GeoPoint(coord[0], coord[1]) for coord in coordinates]


def _serialize_geopoints(geopoints):
    return [[point.latitude, point.longitude] for point in geopoints]


def _serialize_prediction_data(prediction):
    for leaf in prediction['rice_leaves']:
        leaf['polygon'] = _serialize_geopoints(leaf['polygon'])
        leaf['points'] = _serialize_geopoints(leaf['points'])
    rice_field = prediction['rice_field'].get().to_dict()
    rice_field['polygon'] = _serialize_geopoints(rice_field['polygon'])
    rice_field.pop('created_time', None)
    prediction['rice_field'] = rice_field
    prediction['created_time'] = prediction['created_time'].isoformat()
    prediction.pop('is_deleted', None)
    return prediction


class FirestoreClient:
    def __init__(self):
        self.db = firestore.client()
        self.users_collection = self.db.collection('users')
        self.statistic_keys = ['urea_required', 'yield', 'created_time']
        self.summary_keys = ['season', 'paddy_age', 'planting_type', 'rice_leaves', 'image_urls', 'created_time']

    def get_user(self, user_id):
        """
        Retrieves a specific user by ID.
        """
        return _get_document(self.users_collection.document(user_id))

    def get_user_by_phone(self, phone):
        """
        Check if an user with the given phone number exists.
        """
        user_docs = self.users_collection.where('phone', '==', phone).where('is_deleted', '==', False).stream()
        return next(user_docs, None)

    def add_user(self, name, phone):
        """
        Add a new user if the phone number is unique.
        """
        data = {'name': name, 'phone': phone, 'is_deleted': False}
        return self.users_collection.add(data)[1].id

    def add_rice_field(self, user_id, polygon, area, max_yield):
        """
        Add a new rice_field for an user
        """
        user_ref = self.users_collection.document(user_id)
        if not _get_document(user_ref):
            return False

        geopoints = _convert_to_geopoints(polygon)
        data = {'polygon': geopoints, 'area': area, 'max_yield': max_yield, 'created_time': datetime.now()}
        user_ref.collection('rice_fields').add(data)
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
        prediction_data = _get_document(self.users_collection.document(user_id)
                                        .collection('predictions').document(prediction_id))
        return _serialize_prediction_data(prediction_data) if prediction_data else None

    def get_all_predictions(self, user_id, limit=10):
        """
        Retrieves all prediction documents for a specific user.
        """
        predictions_docs = self.users_collection.document(user_id).collection('predictions').where(
            'is_deleted', '==', False).order_by('created_time', direction=firestore.Query.DESCENDING).limit(limit).stream()

        prediction_data = []
        for doc in predictions_docs:
            data = doc.to_dict()
            data['prediction_id'] = doc.id
            data['image_url'] = data['image_urls'][0]
            data['created_time'] = data['created_time'].isoformat()
            data.pop('season', None)
            data.pop('paddy_age', None)
            data.pop('image_urls', None)
            data.pop('is_deleted', None)
            data.pop('rice_field', None)
            data.pop('rice_leaves', None)
            data.pop('planting_type', None)
            prediction_data.append(data)
        return prediction_data

    def add_prediction(self, user_id, data, cluster_data, urls):
        """
        Adds a new prediction document to a specific user.
        """
        rice_leaves = []
        for cluster in cluster_data:
            rice_leaves.append({
                'polygon': _convert_to_geopoints(cluster['polygon']),
                'points': _convert_to_geopoints(cluster['points']),
                'level': cluster['level'],
            })
        data.update({
            'rice_leaves': rice_leaves,
            'image_urls': urls,
            'is_deleted': False,
            'created_time': datetime.now()
        })
        prediction_data = self.users_collection.document(user_id).collection('predictions').add(data)[1].get().to_dict()
        return _serialize_prediction_data(prediction_data)

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
        rice_field_doc = self.users_collection.document(user_id).collection('rice_fields').order_by(
            'created_time', direction=firestore.Query.DESCENDING).limit(1).stream()
        return next(rice_field_doc, None)

    def get_prediction_summary_by_rice_field(self, user_id, rice_field_doc):
        rice_field_data = rice_field_doc.to_dict()
        rice_field_data.update({
            'created_time': rice_field_data['created_time'].isoformat(),
            'polygon': _serialize_geopoints(rice_field_data['polygon']),
        })

        prediction_docs = list(self.users_collection.document(user_id).collection('predictions').where('is_deleted', '==', False).where(
            'rice_field', '==', rice_field_doc.reference).order_by('created_time', direction=firestore.Query.DESCENDING).stream())
        if not prediction_docs:
            return {'rice_field': rice_field_data, 'summary': None, 'history': None}

        statistic_data = []
        for doc in prediction_docs:
            data = doc.to_dict()
            data['created_time'] = data['created_time'].isoformat()
            statistic_data.append({key: data[key] for key in self.statistic_keys})
            if doc == prediction_docs[0]:
                for leaf in data['rice_leaves']:
                    leaf['polygon'] = _serialize_geopoints(leaf['polygon'])
                    leaf['points'] = _serialize_geopoints(leaf['points'])
                summary_data = {key: data[key] for key in self.summary_keys}
        summary_data['statistic'] = statistic_data
        return {'rice_field': rice_field_data, 'summary': summary_data}
