# HỆ THỐNG HỖ TRỢ RA QUYẾT ĐỊNH CHỌN PHIM SỬ DỤNG AWS VÀ MACHINE LEARNING

## 1. Giới thiệu dự án

Dự án xây dựng một website hỗ trợ người dùng lựa chọn phim phù hợp dựa trên các tiêu chí cá nhân như thể loại, quốc gia, năm phát hành, thời lượng, loại nội dung và từ khóa mô tả. Hệ thống sử dụng dữ liệu từ file `netflix_full.csv` và áp dụng Machine Learning để đưa ra danh sách phim đề xuất theo mức độ phù hợp.

Mục tiêu của dự án là xây dựng một hệ thống đơn giản, dễ triển khai, tối ưu chi phí nhưng vẫn thể hiện được các đặc trưng của Công nghệ 4.0 như điện toán đám mây, serverless, dữ liệu lớn ở mức cơ bản và ứng dụng Machine Learning trong hỗ trợ ra quyết định.

---

## 2. Mục tiêu của hệ thống

Hệ thống được xây dựng nhằm đáp ứng các mục tiêu chính sau:

- Hỗ trợ người dùng chọn phim nhanh hơn dựa trên sở thích cá nhân.
- Ứng dụng Machine Learning vào bài toán gợi ý phim.
- Triển khai hệ thống trên nền tảng AWS theo hướng serverless để giảm chi phí vận hành.
- Sử dụng dataset `netflix_full.csv` làm nguồn dữ liệu chính.
- Xây dựng website có giao diện đơn giản, dễ sử dụng, phù hợp với đồ án Công nghệ 4.0.
- Có thể mở rộng trong tương lai sang các mô hình gợi ý nâng cao hơn.

---

## 3. Kiến trúc tổng thể của dự án

### 3.1. Định hướng kiến trúc

Do mục tiêu của đồ án là xây dựng một hệ thống có chi phí thấp nhưng vẫn đảm bảo khả năng trình bày đầy đủ về công nghệ, hệ thống nên sử dụng kiến trúc serverless trên AWS.

Các thành phần chính gồm:

- Amazon S3 để lưu website tĩnh, dataset và file mô hình Machine Learning.
- Amazon CloudFront để phân phối website nhanh hơn tới người dùng.
- Amazon API Gateway để tạo API cho frontend gọi đến backend.
- AWS Lambda để xử lý logic nghiệp vụ và thực hiện gợi ý phim bằng Machine Learning.
- File `netflix_full.csv` làm nguồn dữ liệu phim.
- File mô hình đã xử lý trước, ví dụ `vectorizer.pkl`, `movie_vectors.pkl`, `movies_clean.json`.

Kiến trúc này không yêu cầu thuê máy chủ EC2 chạy liên tục, nhờ đó giúp giảm chi phí rất nhiều. Hệ thống chỉ phát sinh chi phí khi có người dùng truy cập hoặc gọi API.

---

## 4. Sơ đồ kiến trúc hệ thống

```text
+----------------------+
|      Người dùng      |
| Web Browser / Mobile |
+----------+-----------+
           |
           v
+----------------------+
|   Amazon CloudFront  |
| CDN phân phối nội dung|
+----------+-----------+
           |
           v
+----------------------+
|      Amazon S3       |
| Static Website       |
| HTML / CSS / JS      |
+----------+-----------+
           |
           v
+----------------------+
|   Amazon API Gateway |
| Nhận request từ web  |
+----------+-----------+
           |
           v
+----------------------+
|      AWS Lambda      |
| Python Backend       |
| ML + DSS Logic       |
+----------+-----------+
           |
           v
+--------------------------------+
|           Amazon S3            |
| netflix_full.csv               |
| vectorizer.pkl                 |
| movie_vectors.pkl              |
| movies_clean.json              |
+--------------------------------+
```

---

## 5. Mô tả các thành phần trong kiến trúc

### 5.1. Người dùng

Người dùng truy cập website bằng trình duyệt trên máy tính hoặc điện thoại. Người dùng nhập các tiêu chí chọn phim như thể loại, quốc gia, năm phát hành, thời lượng và từ khóa yêu thích.

Ví dụ người dùng nhập:

```json
{
  "type": "Movie",
  "genre": "Action",
  "country": "United States",
  "release_year": 2018,
  "duration": "Medium",
  "keyword": "hero adventure"
}
```

Sau đó hệ thống sẽ xử lý và trả về danh sách phim phù hợp nhất.

---

### 5.2. Amazon CloudFront

Amazon CloudFront đóng vai trò CDN giúp phân phối nội dung website tới người dùng nhanh hơn. Khi người dùng truy cập website, CloudFront sẽ lấy nội dung tĩnh từ Amazon S3 và cache tại các edge location.

Vai trò chính:

- Tăng tốc độ tải website.
- Giảm tải trực tiếp cho S3.
- Hỗ trợ HTTPS.
- Giúp kiến trúc website chuyên nghiệp hơn khi trình bày đồ án.

Trong trường hợp muốn tối ưu chi phí tối đa, CloudFront có thể được sử dụng ở mức cơ bản. Nếu đồ án chỉ chạy thử nghiệm nội bộ, có thể truy cập trực tiếp vào S3 Static Website. Tuy nhiên, để kiến trúc đẹp và đúng mô hình AWS hơn, nên đưa CloudFront vào sơ đồ.

---

### 5.3. Amazon S3 Static Website

Amazon S3 được dùng để lưu trữ frontend của website, bao gồm:

```text
index.html
style.css
app.js
assets/
```

Website này là website tĩnh, không cần server riêng. Toàn bộ phần giao diện người dùng sẽ được đặt trên S3.

Chức năng:

- Hiển thị giao diện chọn phim.
- Thu thập tiêu chí người dùng nhập.
- Gửi request đến API Gateway.
- Nhận kết quả trả về từ Lambda.
- Hiển thị danh sách phim được gợi ý.

---

### 5.4. Amazon API Gateway

API Gateway là lớp trung gian giữa frontend và backend. Khi người dùng bấm nút tìm phim, JavaScript ở frontend sẽ gửi request đến API Gateway.

Ví dụ endpoint:

```text
POST /recommend
```

Request gửi lên:

```json
{
  "type": "Movie",
  "genre": "Comedy",
  "country": "India",
  "release_year": 2020,
  "duration": "Short",
  "keyword": "family love"
}
```

API Gateway sẽ chuyển request này tới AWS Lambda để xử lý.

Vai trò chính:

- Tạo REST API hoặc HTTP API.
- Nhận dữ liệu từ frontend.
- Gọi Lambda backend.
- Trả kết quả JSON về website.
- Hỗ trợ CORS để frontend gọi API.

---

### 5.5. AWS Lambda

AWS Lambda là thành phần xử lý backend chính của hệ thống. Lambda sẽ được viết bằng Python.

Nhiệm vụ của Lambda:

- Nhận request từ API Gateway.
- Đọc dữ liệu đã xử lý hoặc model từ S3.
- Chuyển tiêu chí người dùng thành vector đặc trưng.
- Tính độ tương đồng giữa nhu cầu người dùng và các phim trong dataset.
- Sắp xếp kết quả theo điểm phù hợp.
- Trả về top 5 hoặc top 10 phim phù hợp nhất.

Lambda rất phù hợp với đồ án vì:

- Không cần quản lý server.
- Chỉ tính phí khi có request.
- Dễ kết nối với API Gateway và S3.
- Có thể chạy Python và các thư viện Machine Learning cơ bản.

---

### 5.6. Amazon S3 Data Storage

Ngoài việc host website, S3 còn được dùng để lưu dữ liệu và mô hình.

Các file nên lưu trong S3:

```text
netflix_full.csv
movies_clean.json
vectorizer.pkl
movie_vectors.pkl
```

Trong đó:

- `netflix_full.csv`: dataset gốc.
- `movies_clean.json`: dữ liệu phim đã làm sạch để Lambda trả kết quả nhanh.
- `vectorizer.pkl`: mô hình TF-IDF đã huấn luyện.
- `movie_vectors.pkl`: vector đặc trưng của toàn bộ phim.

Không nên để Lambda đọc và xử lý trực tiếp file CSV thô ở mỗi request vì sẽ làm hệ thống chậm. Cách tốt hơn là xử lý trước trên máy cá nhân, sau đó upload file đã xử lý lên S3.

---

## 6. Luồng hoạt động của hệ thống

### 6.1. Luồng truy cập website

```text
Bước 1: Người dùng mở trình duyệt và truy cập website.

Bước 2: Request được gửi tới CloudFront.

Bước 3: CloudFront lấy nội dung website từ S3 hoặc trả bản cache nếu đã có.

Bước 4: Website được hiển thị trên trình duyệt người dùng.

Bước 5: Người dùng bắt đầu nhập tiêu chí chọn phim.
```

---

### 6.2. Luồng gửi yêu cầu gợi ý phim

```text
Bước 1: Người dùng chọn các tiêu chí trên giao diện website.

Bước 2: Người dùng bấm nút "Gợi ý phim".

Bước 3: Frontend tạo request JSON chứa các tiêu chí người dùng nhập.

Bước 4: Frontend gửi request đến API Gateway.

Bước 5: API Gateway chuyển request đến AWS Lambda.

Bước 6: Lambda xử lý yêu cầu bằng mô hình Machine Learning.

Bước 7: Lambda trả về danh sách phim phù hợp.

Bước 8: API Gateway trả response về frontend.

Bước 9: Website hiển thị kết quả cho người dùng.
```

---

### 6.3. Luồng xử lý Machine Learning trong Lambda

```text
Bước 1: Lambda nhận tiêu chí người dùng từ API Gateway.

Bước 2: Lambda kiểm tra dữ liệu đầu vào.

Bước 3: Lambda tải vectorizer và movie vectors từ S3 nếu chưa được load.

Bước 4: Lambda ghép các tiêu chí người dùng thành một chuỗi nội dung.

Bước 5: Lambda dùng TF-IDF Vectorizer để chuyển chuỗi tiêu chí thành vector.

Bước 6: Lambda tính Cosine Similarity giữa vector người dùng và vector của từng phim.

Bước 7: Lambda lọc thêm theo điều kiện như loại phim, năm phát hành, quốc gia nếu có.

Bước 8: Lambda sắp xếp phim theo điểm phù hợp giảm dần.

Bước 9: Lambda trả về top 5 hoặc top 10 phim phù hợp nhất.
```

---

### 6.4. Luồng xử lý dữ liệu trước khi triển khai

```text
Bước 1: Đọc file netflix_full.csv trên máy cá nhân.

Bước 2: Làm sạch dữ liệu:
        - Xử lý giá trị null.
        - Chuẩn hóa tên cột.
        - Chuẩn hóa thể loại, quốc gia, thời lượng.
        - Chuyển duration sang dạng số nếu cần.

Bước 3: Ghép các cột quan trọng thành một cột đặc trưng nội dung.

Bước 4: Huấn luyện TF-IDF Vectorizer trên cột đặc trưng.

Bước 5: Tạo vector biểu diễn cho từng phim.

Bước 6: Lưu các file:
        - vectorizer.pkl
        - movie_vectors.pkl
        - movies_clean.json

Bước 7: Upload các file đã xử lý lên Amazon S3.

Bước 8: Lambda sử dụng các file này để inference khi người dùng gửi yêu cầu.
```

---

## 7. Mô hình Machine Learning sử dụng trong hệ thống

### 7.1. Phương pháp gợi ý phim

Hệ thống sử dụng phương pháp Content-Based Filtering. Đây là phương pháp gợi ý dựa trên nội dung của từng bộ phim.

Mỗi phim được biểu diễn bằng các đặc trưng như:

- Tên phim.
- Loại nội dung.
- Đạo diễn.
- Diễn viên.
- Quốc gia.
- Năm phát hành.
- Độ tuổi phân loại.
- Thời lượng.
- Thể loại.
- Mô tả nội dung phim.

Khi người dùng nhập nhu cầu, hệ thống cũng chuyển nhu cầu đó thành dạng biểu diễn tương tự. Sau đó, hệ thống tính độ tương đồng giữa nhu cầu người dùng với từng phim trong dataset.

---

### 7.2. Thuật toán TF-IDF

TF-IDF là kỹ thuật dùng để biểu diễn văn bản dưới dạng vector số.

TF-IDF giúp xác định từ nào quan trọng trong mô tả phim. Những từ xuất hiện nhiều trong một phim nhưng không xuất hiện quá phổ biến trong toàn bộ dataset sẽ có trọng số cao hơn.

Ví dụ:

Nếu người dùng nhập từ khóa:

```text
romantic comedy family
```

Hệ thống sẽ ưu tiên các phim có mô tả, thể loại hoặc nội dung liên quan đến tình cảm, hài hước và gia đình.

---

### 7.3. Thuật toán Cosine Similarity

Cosine Similarity được dùng để tính mức độ giống nhau giữa hai vector.

Trong hệ thống này:

- Vector thứ nhất là vector tiêu chí người dùng.
- Vector thứ hai là vector của từng phim.

Công thức ý tưởng:

```text
Similarity = cosine(user_vector, movie_vector)
```

Nếu điểm similarity càng cao thì phim càng phù hợp với nhu cầu người dùng.

Ví dụ:

```text
Phim A: similarity = 0.92
Phim B: similarity = 0.75
Phim C: similarity = 0.41
```

Hệ thống sẽ ưu tiên gợi ý phim A trước.

---

### 7.4. Lý do chọn Content-Based Filtering

Phương pháp này phù hợp với dự án vì:

- Không yêu cầu dữ liệu lịch sử đánh giá người dùng.
- Phù hợp với dataset Netflix có nhiều thông tin nội dung phim.
- Dễ triển khai bằng Python.
- Dễ giải thích trong báo cáo đồ án.
- Không cần hệ thống database phức tạp.
- Chi phí triển khai trên AWS thấp.

---

## 8. Logic hỗ trợ ra quyết định DSS

Hệ thống không chỉ lọc phim đơn giản mà còn hỗ trợ ra quyết định bằng cách tính điểm phù hợp tổng hợp.

Điểm phù hợp có thể gồm:

```text
Điểm phù hợp tổng = 
  70% điểm tương đồng nội dung
+ 10% điểm phù hợp năm phát hành
+ 10% điểm phù hợp thời lượng
+ 10% điểm phù hợp quốc gia hoặc loại phim
```

Ví dụ:

| Tiêu chí | Trọng số |
|---|---:|
| Mức độ tương đồng nội dung | 70% |
| Năm phát hành | 10% |
| Thời lượng | 10% |
| Quốc gia / loại phim | 10% |

Công thức minh họa:

```text
Final Score = 0.7 * SimilarityScore 
            + 0.1 * YearScore 
            + 0.1 * DurationScore 
            + 0.1 * MetadataScore
```

Cách làm này giúp hệ thống vừa có Machine Learning, vừa có tính chất của hệ hỗ trợ ra quyết định.

---

## 9. Công nghệ sử dụng

### 9.1. Frontend

| Công nghệ | Chức năng |
|---|---|
| HTML | Xây dựng cấu trúc giao diện |
| CSS | Thiết kế giao diện, màu sắc, bố cục |
| JavaScript | Xử lý tương tác, gọi API, hiển thị kết quả |
| Fetch API | Gửi request từ web tới API Gateway |

Frontend nên được thiết kế gồm các phần:

- Trang chủ giới thiệu hệ thống.
- Form chọn tiêu chí phim.
- Khu vực hiển thị kết quả gợi ý.
- Modal hoặc trang chi tiết phim.
- Thông báo lỗi nếu API không phản hồi.

---

### 9.2. Backend

| Công nghệ | Chức năng |
|---|---|
| Python | Ngôn ngữ xử lý chính |
| AWS Lambda | Chạy backend serverless |
| API Gateway | Tạo API cho frontend |
| boto3 | Kết nối Lambda với S3 |
| joblib | Load file model `.pkl` |
| scikit-learn | Xử lý TF-IDF và Cosine Similarity |
| numpy | Tính toán vector |
| pandas | Xử lý dữ liệu khi training offline |

---

### 9.3. Cloud và lưu trữ

| Dịch vụ | Chức năng |
|---|---|
| Amazon S3 | Lưu frontend, dataset, model |
| Amazon CloudFront | CDN tăng tốc website |
| AWS Lambda | Xử lý logic và Machine Learning |
| Amazon API Gateway | Kết nối frontend với Lambda |
| AWS IAM | Phân quyền Lambda truy cập S3 |
| Amazon CloudWatch | Theo dõi log và lỗi Lambda |

---

## 10. Cấu trúc thư mục dự án đề xuất

```text
movie-dss-aws/
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── assets/
│
├── backend/
│   ├── lambda_function.py
│   ├── requirements.txt
│   └── package/
│
├── data/
│   └── netflix_full.csv
│
├── model/
│   ├── train_model.py
│   ├── vectorizer.pkl
│   ├── movie_vectors.pkl
│   └── movies_clean.json
│
├── docs/
│   ├── architecture.md
│   └── deployment.md
│
└── README.md
```

---

## 11. Thiết kế giao diện website

### 11.1. Trang chủ

Trang chủ giới thiệu tên hệ thống và chức năng chính.

Nội dung gợi ý:

```text
Movie DSS - Hệ thống hỗ trợ ra quyết định chọn phim

Ứng dụng Machine Learning và điện toán đám mây AWS để đề xuất phim phù hợp với sở thích người dùng.
```

Các thành phần nên có:

- Banner giới thiệu.
- Nút bắt đầu chọn phim.
- Mô tả ngắn về Machine Learning.
- Mô tả các tiêu chí hệ thống sử dụng.

---

### 11.2. Form chọn phim

Các trường người dùng có thể nhập:

| Trường | Kiểu dữ liệu |
|---|---|
| Loại nội dung | Select: Movie / TV Show |
| Thể loại | Select hoặc checkbox |
| Quốc gia | Select |
| Năm phát hành | Number |
| Thời lượng | Short / Medium / Long |
| Từ khóa mô tả | Text input |
| Số lượng kết quả | Top 5 / Top 10 |

Ví dụ giao diện:

```text
[Loại phim]       Movie
[Thể loại]        Action
[Quốc gia]        United States
[Năm phát hành]   2018
[Thời lượng]      Medium
[Từ khóa]         hero adventure
[Nút]             Gợi ý phim
```

---

### 11.3. Kết quả gợi ý

Mỗi kết quả nên hiển thị:

- Tên phim.
- Loại phim.
- Quốc gia.
- Năm phát hành.
- Thời lượng.
- Thể loại.
- Mô tả.
- Điểm phù hợp.

Ví dụ:

```text
1. Inception
Loại: Movie
Năm: 2010
Thể loại: Action, Sci-Fi, Thriller
Quốc gia: United States
Điểm phù hợp: 94%
Mô tả: Một bộ phim khoa học viễn tưởng về giấc mơ và tiềm thức.
```

---

## 12. Tối ưu hiệu suất hệ thống

### 12.1. Không xử lý CSV thô trong mỗi request

Nếu Lambda đọc và xử lý trực tiếp `netflix_full.csv` mỗi lần người dùng tìm phim, thời gian phản hồi sẽ chậm.

Giải pháp:

- Xử lý dataset trước trên máy cá nhân.
- Tạo file `movies_clean.json`.
- Tạo file `vectorizer.pkl`.
- Tạo file `movie_vectors.pkl`.
- Upload các file này lên S3.
- Lambda chỉ load file đã xử lý để tính toán nhanh.

---

### 12.2. Sử dụng biến global trong Lambda

Trong Lambda có thể dùng biến global để cache model khi container Lambda còn warm.

Ví dụ:

```python
vectorizer = None
movie_vectors = None
movies = None
```

Khi request đầu tiên đến, Lambda tải model từ S3. Nếu request tiếp theo được xử lý bởi cùng một Lambda container, hệ thống có thể tái sử dụng model mà không cần tải lại.

---

### 12.3. Giới hạn số lượng kết quả trả về

Chỉ nên trả về top 5 hoặc top 10 phim phù hợp nhất.

Lợi ích:

- Giảm dung lượng response JSON.
- Tăng tốc hiển thị frontend.
- Người dùng dễ lựa chọn hơn.
- Giảm chi phí truyền dữ liệu.

---

### 12.4. Dùng CloudFront để tăng tốc website

CloudFront cache các file tĩnh như:

```text
index.html
style.css
app.js
image
icon
```

Nhờ đó website tải nhanh hơn và giảm số lần truy cập trực tiếp vào S3.

---

### 12.5. Theo dõi lỗi bằng CloudWatch

AWS CloudWatch giúp theo dõi log của Lambda.

Các thông tin cần theo dõi:

- Request thành công.
- Request lỗi.
- Thời gian chạy Lambda.
- Lỗi đọc file từ S3.
- Lỗi xử lý model.
- Lỗi dữ liệu đầu vào.

---

## 13. Tối ưu chi phí AWS

Hệ thống được thiết kế để tối ưu chi phí bằng cách sử dụng các dịch vụ serverless.

### 13.1. Các dịch vụ nên dùng

| Dịch vụ | Lý do |
|---|---|
| S3 | Rẻ, dễ lưu website và dataset |
| Lambda | Chỉ trả tiền khi có request |
| API Gateway | Tạo API nhanh, không cần server |
| CloudFront | Tăng tốc website, có free tier |
| CloudWatch | Theo dõi log cơ bản |

---

### 13.2. Các dịch vụ không nên dùng ở giai đoạn đồ án

| Dịch vụ | Lý do không nên dùng |
|---|---|
| EC2 | Phải chạy server liên tục, tốn chi phí |
| RDS / Aurora | Không cần database quan hệ cho dataset nhỏ |
| ElastiCache Redis | Chưa cần nếu lượng người dùng ít |
| SageMaker Endpoint | Có thể phát sinh chi phí nếu endpoint chạy liên tục |
| OpenSearch | Quá phức tạp cho đồ án nhỏ |

---

### 13.3. Cách đưa SageMaker vào báo cáo mà không tốn chi phí

Trong báo cáo có thể trình bày:

```text
Ở phiên bản hiện tại, mô hình Machine Learning được huấn luyện offline bằng Python và triển khai inference trên AWS Lambda để tối ưu chi phí. Trong hướng phát triển, hệ thống có thể mở rộng sang Amazon SageMaker để tự động hóa quá trình huấn luyện, triển khai endpoint inference và quản lý vòng đời mô hình ở quy mô lớn.
```

Cách viết này giúp bài có định hướng Công nghệ 4.0 rõ ràng nhưng vẫn không cần triển khai SageMaker thật nếu chưa cần.

---

## 14. Quy trình triển khai trên AWS

### 14.1. Bước 1: Chuẩn bị dataset

Đặt file dataset vào thư mục:

```text
data/netflix_full.csv
```

Kiểm tra các cột quan trọng như:

```text
show_id
type
title
director
cast
country
date_added
release_year
rating
duration
listed_in
description
```

---

### 14.2. Bước 2: Huấn luyện mô hình offline

Chạy file:

```text
model/train_model.py
```

File này thực hiện:

- Đọc `netflix_full.csv`.
- Làm sạch dữ liệu.
- Ghép nội dung phim thành cột đặc trưng.
- Huấn luyện TF-IDF Vectorizer.
- Tạo vector cho từng phim.
- Lưu file model và dữ liệu đã xử lý.

Kết quả tạo ra:

```text
vectorizer.pkl
movie_vectors.pkl
movies_clean.json
```

---

### 14.3. Bước 3: Upload dữ liệu lên S3

Tạo bucket S3, ví dụ:

```text
movie-dss-bucket
```

Upload các file:

```text
data/netflix_full.csv
model/vectorizer.pkl
model/movie_vectors.pkl
model/movies_clean.json
frontend/index.html
frontend/style.css
frontend/app.js
```

---

### 14.4. Bước 4: Tạo Lambda Function

Tạo Lambda với runtime:

```text
Python 3.10 hoặc Python 3.11
```

Cấu hình quyền IAM cho Lambda đọc file từ S3.

Lambda cần quyền:

```text
s3:GetObject
```

Tài nguyên cần truy cập:

```text
arn:aws:s3:::movie-dss-bucket/*
```

---

### 14.5. Bước 5: Tạo API Gateway

Tạo HTTP API hoặc REST API.

Endpoint đề xuất:

```text
POST /recommend
```

Kết nối endpoint này tới Lambda.

Bật CORS để frontend có thể gọi API.

---

### 14.6. Bước 6: Host frontend trên S3

Bật Static Website Hosting cho bucket chứa frontend.

Cấu hình:

```text
Index document: index.html
Error document: index.html
```

Sau đó có thể truy cập website bằng S3 website endpoint hoặc thông qua CloudFront.

---

### 14.7. Bước 7: Tạo CloudFront Distribution

Tạo CloudFront Distribution trỏ tới S3 bucket chứa website.

Lợi ích:

- Tăng tốc website.
- Hỗ trợ HTTPS.
- Có URL truy cập chuyên nghiệp hơn.

---

### 14.8. Bước 8: Kiểm thử hệ thống

Kiểm thử các trường hợp:

- Người dùng chọn thể loại Action.
- Người dùng chọn quốc gia United States.
- Người dùng nhập từ khóa romantic comedy.
- Người dùng không nhập tiêu chí.
- API lỗi hoặc Lambda timeout.
- Dataset thiếu giá trị.
- Kết quả trả về rỗng.

---

## 15. Mẫu API Request và Response

### 15.1. Request

```json
{
  "type": "Movie",
  "genre": "Action",
  "country": "United States",
  "release_year": 2018,
  "duration": "Medium",
  "keyword": "hero adventure",
  "top_k": 10
}
```

---

### 15.2. Response

```json
{
  "status": "success",
  "results": [
    {
      "title": "Example Movie",
      "type": "Movie",
      "country": "United States",
      "release_year": 2019,
      "duration": "110 min",
      "listed_in": "Action, Adventure",
      "description": "A hero begins an adventure to save the world.",
      "score": 0.93
    },
    {
      "title": "Another Movie",
      "type": "Movie",
      "country": "United States",
      "release_year": 2020,
      "duration": "98 min",
      "listed_in": "Action, Sci-Fi",
      "description": "A science fiction story with action and adventure.",
      "score": 0.89
    }
  ]
}
```

---

## 16. Ưu điểm của kiến trúc đề xuất

Kiến trúc này có nhiều ưu điểm đối với một đồ án Công nghệ 4.0:

- Đơn giản, dễ hiểu, dễ trình bày.
- Chi phí thấp do sử dụng serverless.
- Không cần duy trì server riêng.
- Có ứng dụng Machine Learning rõ ràng.
- Có sử dụng cloud computing.
- Có khả năng mở rộng khi lượng người dùng tăng.
- Phù hợp với dataset Netflix dạng CSV.
- Dễ triển khai demo thực tế.

---

## 17. Hạn chế của hệ thống

Bên cạnh các ưu điểm, hệ thống vẫn có một số hạn chế:

- Chưa có dữ liệu hành vi người dùng thực tế.
- Chưa có collaborative filtering dựa trên đánh giá của nhiều người dùng.
- Chưa có database lưu lịch sử tìm kiếm.
- Nếu dataset quá lớn, Lambda có thể bị giới hạn dung lượng và thời gian xử lý.
- Mô hình Content-Based Filtering phụ thuộc nhiều vào chất lượng mô tả phim.
- Chưa có cơ chế cập nhật dữ liệu tự động.

---

## 18. Hướng phát triển trong tương lai

Trong tương lai, hệ thống có thể được mở rộng theo các hướng sau:

- Thêm chức năng đăng nhập người dùng bằng Amazon Cognito.
- Lưu lịch sử xem và đánh giá phim bằng DynamoDB.
- Áp dụng Collaborative Filtering khi có nhiều dữ liệu đánh giá.
- Kết hợp Content-Based Filtering và Collaborative Filtering thành Hybrid Recommendation System.
- Sử dụng Amazon SageMaker để huấn luyện và triển khai mô hình ở quy mô lớn.
- Thêm dashboard phân tích xu hướng phim bằng Amazon QuickSight.
- Tự động cập nhật dataset theo lịch bằng AWS EventBridge và Lambda.
- Thêm chức năng chatbot tư vấn phim.
- Tích hợp poster phim từ API bên ngoài.
- Thêm chức năng lọc nâng cao theo độ tuổi, diễn viên, đạo diễn, quốc gia.

---

## 19. Kết luận

Dự án hệ thống hỗ trợ ra quyết định chọn phim sử dụng AWS và Machine Learning là một mô hình phù hợp với môn đồ án Công nghệ 4.0. Hệ thống kết hợp giữa website, điện toán đám mây, serverless architecture và Machine Learning để giải quyết bài toán lựa chọn phim theo nhu cầu cá nhân.

Kiến trúc đề xuất sử dụng Amazon S3, CloudFront, API Gateway và AWS Lambda giúp hệ thống dễ triển khai, tối ưu chi phí và phù hợp với quy mô đồ án. Mô hình Machine Learning Content-Based Filtering sử dụng TF-IDF và Cosine Similarity giúp hệ thống đưa ra gợi ý phim dựa trên nội dung, thể loại, mô tả và các thông tin liên quan đến phim.

Với cách triển khai này, dự án vừa có tính thực tiễn, vừa thể hiện được các công nghệ tiêu biểu của thời đại Công nghệ 4.0.
