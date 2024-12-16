# PetaniKu REST API
Summary : Layanan REST API untuk aplikasi PetaniKu  
Language : Python  
Database : Firestore  
Framework : Flask

## Cara penggunaan
1. Pastikan file dan folder relevan sudah ditambahkan di root project (`.env`, `key.json`, `saved_model`)
2. Buat Virtual Environment dengan menjalakan command `python -m venv venv` (Windows) pada root project
3. Aktifkan Virtual Environment dengan menjalankan command `venv\Scripts\activate` (Windows) pada root project
4. Install library dari `requirements.txt` dengan menjalankan command `pip install -r requirements.txt` (Windows) pada root project
5. Mulai program REST API dengan menjalankan command `python app.py`

## Daftar Endpoint
Terdapat 9 endpoint yang tersedia pada REST API. Seluruh endpoint, kecuali *login* dan *daftar akun*, membutuhkan **Bearer Token** untuk diakses.
### Login
- Endpoint :  `POST  /user/login`
- Request :  JSON  
  ```json
  {
	"phone": "081111111111"
  }
  ```
- Response :  
  ```json
  {
	"pesan": "Login berhasil",
	"token": "Token"
  }
  ```

### Daftar akun
- Endpoint :  `POST  /user`
- Request :  JSON
  ```json
  {
	"name": "John Doe",
	"phone": "081111111111"
  }
  ```
- Response :  
  ```json
  {
	"pesan": "Akun berhasil dibuat",
	"token": "Token"
  }
  ```

### Dashboard
- Endpoint :  `GET  /user`
- Request :  none
- Response :  
  ```json
  [
	{
		"urea_required": 40,
		"season": "Wet",
		"nitrogen_required": 10,
		"planting_type": "Transplanted",
		"images": [
			{
				"latitude": 16.4328151,
				"longitude": 100.5521142,
				"level": 3,
				"url": "https://res.cloudinary.com/dfz5oiipg/image/upload/v1733814648/krolf2l05fuqbolmoaom.jpg"
			},
			{
				"latitude": -37.7758475,
				"longitude": -67.7134201,
				"level": 3,
				"url": "https://res.cloudinary.com/dfz5oiipg/image/upload/v1733814647/tooj0wrokovctygnwatj.jpg"
			},
			{
				"latitude": 51.7192247,
				"longitude": 20.5223046,
				"level": 3,
				"url": "https://res.cloauadinary.com/dfz5oiipg/image/upload/v1733814646/d4r8xgdp8kuttuvr4tn9.jpg"
			},
			{
				"latitude": 27.028446,
				"longitude": 106.461061,
				"level": 2,
				"url": "https://res.cloudinary.com/dfz5oiipg/image/upload/v1733814649/mt30lfit4h72jk5lccqy.jpg"
			},
			{
				"latitude": 8.1104639,
				"longitude": -67.6095967,
				"level": 2,
				"url": "https://res.cloudinary.com/dfz5oiipg/image/upload/v1733814649/x0obgeu9wbyhmy1eidom.jpg"
			}
		],
		"paddy_age": 3,
		"create_time": "2024-12-10T15:10:53.622000+00:00",
		"rice_field": [
			{
				"latitude": 51.9309719,
				"longitude": 19.190298
			},
			{
				"latitude": 44.4528239,
				"longitude": 19.0902035
			},
			{
				"latitude": 6.2958736,
				"longitude": 101.7296049
			},
			{
				"latitude": -0.3052095,
				"longitude": 109.1463836
			}
		],
		"fertilizer_required": 0.8695652173913043,
		"yields": 6,
		"area": 2
	}
  ]
  ```

### Perbarui peta lahan padi
- Endpoint :  `PUT  /user`
- Request :  JSON  
  ```json
  {
	"coordinates": [
		{
			"latitude": 1.0,
			"longitude": 2.0
		},
		{
			"latitude": 1.0,
			"longitude": 2.0
		},
		{
			"latitude": 1.0,
			"longitude": 2.0
		}
	],
	"area": 1
  }
  ```
- Response :  
  ```json
  {
	"pesan": "Area lahan padi berhasil diperbarui"
  }
  ```

### Hapus akun
- Endpoint :  `DELETE  /user`
- Request :  none
- Response :
  ```json
  {
	"pesan": "Akun berhasil dihapus"
  }
  ```

### Pengecekan tanaman
- Endpoint :  `POST  /predictions`
- Request :  Multipart Form  
  ```
  payload = {  "season": "Dry",  "planting_type": "Direct Seeded",  "paddy_age": 3,  "coordinates": [    {"latitude": -7.797068, "longitude": 110.370529},    {"latitude": -7.798068, "longitude": 110.371529}  ]}
  images = ["path_to_image1.jpg", "path_to_image2.jpg"]
  ```
- Response :  
  ```json
  {
	"urea_required": 32.608695652173914,
	"yields": 6,
	"nitrogen_required": 7.5,
	"planting_type": "Direct Seeded",
	"images": [
		{
			"latitude": -7.797068,
			"longitude": 110.370529,
			"level": 4,
			"url": "https://res.cloudinary.com/dfz5oiipg/image/upload/v1733814647/tooj0wrokovctygnwatj.jpg"
		},
		{
			"latitude": -7.798068,
			"longitude": 110.371529,
			"level": 4,
			"url": "https://res.cloudinary.com/dfz5oiipg/image/upload/v1733814647/tooj0wrokovctygnwatj.jpg"
		}
	],
	"paddy_age": 3,
	"create_time": "2024-12-15T14:28:03.365007+00:00",
	"rice_field": [
		{
			"latitude": 51.9309719,
			"longitude": 19.190298
		},
		{
			"latitude": 44.4528239,
			"longitude": 19.0902035
		},
		{
			"latitude": 6.2958736,
			"longitude": 101.7296049
		},
		{
			"latitude": -0.3052095,
			"longitude": 109.1463836
		}
	],
	"fertilizer_required": 0.6521739130434783,
	"season": "Dry",
	"area": 2
  }
  ```

### Daftar pengecekan tanaman (ringkasan)
- Endpoint :  `GET  /predictions`
- Request :  none
- Response :  
  ```json
  [
	{
		"urea_required": 40,
		"season": "Wet",
		"nitrogen_required": 10,
		"planting_type": "Transplanted",
		"paddy_age": 3,
		"create_time": "2024-12-10T15:10:53.622000+00:00",
		"fertilizer_required": 0.8695652173913043,
		"yields": 6,
		"prediction_id": "2XSGCkviJKsHYPWea4Oz"
	}
  ]
  ```

### Informasi detail pengecekan tanaman
- Endpoint :  `GET  /predictions/<string:prediction_id>`
- Request :  none
- Response :  
  ```json
  {
	"urea_required": 40,
	"season": "Wet",
	"nitrogen_required": 10,
	"planting_type": "Transplanted",
	"images": [
		{
			"latitude": 16.4328151,
			"longitude": 100.5521142,
			"level": 3,
			"url": "https://res.cloudinary.com/dfz5oiipg/image/upload/v1733814648/krolf2l05fuqbolmoaom.jpg"
		},
		{
			"latitude": -37.7758475,
			"longitude": -67.7134201,
			"level": 3,
			"url": "https://res.cloudinary.com/dfz5oiipg/image/upload/v1733814647/tooj0wrokovctygnwatj.jpg"
		},
		{
			"latitude": 51.7192247,
			"longitude": 20.5223046,
			"level": 3,
			"url": "https://res.cloauadinary.com/dfz5oiipg/image/upload/v1733814646/d4r8xgdp8kuttuvr4tn9.jpg"
		},
		{
			"latitude": 27.028446,
			"longitude": 106.461061,
			"level": 2,
			"url": "https://res.cloudinary.com/dfz5oiipg/image/upload/v1733814649/mt30lfit4h72jk5lccqy.jpg"
		},
		{
			"latitude": 8.1104639,
			"longitude": -67.6095967,
			"level": 2,
			"url": "https://res.cloudinary.com/dfz5oiipg/image/upload/v1733814649/x0obgeu9wbyhmy1eidom.jpg"
		}
	],
	"paddy_age": 3,
	"create_time": "2024-12-10T15:10:53.622000+00:00",
	"rice_field": [
		{
			"latitude": 51.9309719,
			"longitude": 19.190298
		},
		{
			"latitude": 44.4528239,
			"longitude": 19.0902035
		},
		{
			"latitude": 6.2958736,
			"longitude": 101.7296049
		},
		{
			"latitude": -0.3052095,
			"longitude": 109.1463836
		}
	],
	"fertilizer_required": 0.8695652173913043,
	"yields": 6,
	"area": 2
  }
  ```

### Hapus pengecekan tanaman
- Endpoint :  `DELETE  /predictions/<string:prediction_id>`
- Request :  none
- Response :  
  ```json
  {
	"pesan": "Pengecekan tanaman berhasil dihapus"
  }
  ```
