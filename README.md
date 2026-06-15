# 🎬 Hệ Thống Hỗ Trợ Ra Quyết Định Chọn Phim

> Ứng dụng Machine Learning và điện toán đám mây AWS để gợi ý phim phù hợp với sở thích cá nhân.

---

## Giới thiệu

Đây là đồ án môn học xây dựng hệ thống **Decision Support System (DSS)** cho bài toán chọn phim. Người dùng nhập các tiêu chí như thể loại, quốc gia, năm phát hành, thời lượng và từ khóa — hệ thống trả về danh sách phim phù hợp nhất được xếp hạng theo điểm tương đồng.

Hệ thống sử dụng **Content-Based Filtering** với TF-IDF và Cosine Similarity, triển khai hoàn toàn **serverless trên AWS**.

---

## Kiến trúc hệ thống

```
Trình duyệt
    │  HTTPS
    ▼
Amazon CloudFront  ──────►  S3 (frontend)
    │                       index.html / style.css / app.js
    │  POST /recommend
    ▼
Amazon API Gateway
    │  Lambda proxy
    ▼
AWS Lambda (Python 3.11)
    │  s3:GetObject
    ▼
S3 (artifacts)
    model/vectorizer.pkl
    model/movie_vectors.pkl
    model/movies_clean.json

──────────────────────────────────
Offline (máy cá nhân):
  data/netflix_full.csv
      └─► model/train_model.py
              └─► tạo 3 file artifacts ở trên
```

**Công thức tính điểm phù hợp:**
```
Điểm = 0.7 × cosine_similarity
     + 0.1 × year_score
     + 0.1 × duration_score
     + 0.1 × metadata_score
```

---

## Cấu trúc thư mục

```
Movie_DSS/
├── frontend/
│   ├── index.html          ← Giao diện người dùng
│   ├── style.css           ← CSS + loading spinner
│   └── app.js              ← Gọi API, hiển thị kết quả
│
├── backend/
│   ├── lambda_function.py  ← Lambda handler + toàn bộ logic ML
│   └── requirements.txt    ← Thư viện Python cho Lambda
│
├── model/
│   ├── train_model.py      ← Script xử lý dữ liệu offline
│   ├── vectorizer.pkl      ← TF-IDF Vectorizer đã huấn luyện
│   ├── movie_vectors.pkl   ← Ma trận vector phim
│   └── movies_clean.json   ← Dataset đã làm sạch
│
├── data/
│   └── netflix_full.csv    ← Dataset gốc
│
├── tests/
│   ├── unit/               ← Unit test + property-based test
│   └── integration/        ← Smoke test sau khi deploy
│
├── terraform/              ← Infrastructure as Code (IaC)
│   ├── main.tf
│   ├── variables.tf
│   ├── s3.tf
│   ├── iam.tf
│   ├── lambda.tf
│   ├── apigateway.tf
│   ├── cloudfront.tf
│   └── outputs.tf
│
├── docs/
│   └── deployment.md       ← Hướng dẫn deploy thủ công (AWS CLI)
│
└── Architecture.md         ← Tài liệu kiến trúc chi tiết
```

---

## Yêu cầu cài đặt

| Công cụ | Phiên bản |
|---------|-----------|
| Python  | 3.11      |
| AWS CLI | ≥ 2.x, đã cấu hình `aws configure` |
| Terraform | ≥ 1.5.0 (nếu dùng IaC) |
| pip | Đi kèm Python 3.11 |

---

## Cách chạy

### 1. Cài đặt thư viện phát triển

```bash
pip install -r requirements-dev.txt
```

### 2. Huấn luyện mô hình (offline, chạy 1 lần)

```bash
python model/train_model.py
```

Kiểm tra kết quả:

```bash
ls -lh model/vectorizer.pkl model/movie_vectors.pkl model/movies_clean.json
```

### 3. Build Lambda deployment package

```bash
pip install -r backend/requirements.txt -t backend/package/
cp backend/lambda_function.py backend/package/
cd backend/package && zip -r ../../lambda_deployment.zip . && cd ../..
```

---

## Deploy lên AWS

Có **hai cách** để deploy:

### Cách A — Terraform (khuyến nghị)

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Sau khi apply xong, Terraform in ra:

```
api_endpoint      = "https://<id>.execute-api.<region>.amazonaws.com/prod/recommend"
cloudfront_url    = "https://<domain>.cloudfront.net"


api_endpoint = "https://v7bzd8fpr6.execute-api.ap-southeast-1.amazonaws.com/prod/recommend"
artifacts_bucket = "movie-dss-artifacts-650251726830"
cloudfront_url = "https://d287o4kd4hdhx.cloudfront.net"
frontend_bucket = "movie-dss-frontend-650251726830"
lambda_arn = "arn:aws:lambda:ap-southeast-1:650251726830:function:movie-dss-recommender"
lambda_function_name = "movie-dss-recommender"
```

Cập nhật `API_URL` trong `frontend/app.js` bằng `api_endpoint` ở trên, rồi chạy lại:

```bash
terraform apply   # upload lại app.js đã cập nhật
```

### Cách B — AWS CLI thủ công

Xem hướng dẫn chi tiết từng bước tại [`docs/deployment.md`](docs/deployment.md).

---

## Chạy kiểm thử

### Unit test + Property-based test

```bash
# Tất cả unit test
pytest tests/unit/ -v

# Chỉ test preprocessor
pytest tests/unit/test_preprocessor.py -v

# Chỉ test recommender
pytest tests/unit/test_recommender.py -v
```

### Integration / Smoke test (cần đã deploy)

```bash
export API_URL="https://<id>.execute-api.<region>.amazonaws.com/prod/recommend"
pytest tests/integration/ -v
```

---

## API

**Endpoint:** `POST /recommend`

**Request body:**

```json
{
  "type":         "Movie",
  "genre":        "Action",
  "country":      "United States",
  "release_year": 2018,
  "duration":     "Medium",
  "keyword":      "hero adventure",
  "top_k":        10
}
```

- `type` và `genre`: bắt buộc
- Các trường còn lại: tùy chọn

**Response thành công (HTTP 200):**

```json
{
  "status": "success",
  "results": [
    {
      "rank":      1,
      "name":      "Inception",
      "type":      "Movie",
      "country":   "United States",
      "year":      "2010",
      "time":      "148 min",
      "genres":    "Action & Adventure, Sci-Fi, Thrillers",
      "describle": "A thief who steals corporate secrets...",
      "score":     0.934
    }
  ]
}
```

**Response lỗi (HTTP 400):**

```json
{ "error": "Missing required field: genre" }
```

---

## Công nghệ sử dụng

| Tầng | Công nghệ |
|------|-----------|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Backend | Python 3.11, AWS Lambda |
| ML | scikit-learn (TF-IDF, Cosine Similarity), numpy, joblib |
| API | Amazon API Gateway HTTP API |
| Lưu trữ | Amazon S3 |
| CDN | Amazon CloudFront |
| Bảo mật | AWS IAM (least-privilege) |
| Quan sát | Amazon CloudWatch Logs |
| IaC | Terraform ≥ 1.5 |
| Test | pytest, Hypothesis (property-based testing) |

---

## Biến môi trường

| Biến | Dùng ở | Giá trị mẫu |
|------|--------|-------------|
| `ARTIFACTS_BUCKET` | Lambda | `movie-dss-artifacts` |
| `MODEL_PREFIX` | Lambda | `model/` |
| `API_URL` | Smoke test | `https://<id>.execute-api.<region>.amazonaws.com/prod/recommend` |

---

## Lưu ý

- Thư mục `backend/package/` không được commit vào git — chỉ commit `lambda_deployment.zip`.
- File `terraform/terraform.tfstate` chứa thông tin hạ tầng, **không commit** lên repository công khai.
- Dataset `data/netflix_full.csv` có thể lớn — cân nhắc thêm vào `.gitignore` nếu vượt quá giới hạn của git.

---

## Tài liệu tham khảo

- [Architecture.md](Architecture.md) — Tài liệu kiến trúc chi tiết, luồng hoạt động, mô tả ML
- [docs/deployment.md](docs/deployment.md) — Hướng dẫn deploy thủ công từng bước bằng AWS CLI
