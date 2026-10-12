# DD — Home Assistant Apps

Kho ứng dụng Home Assistant để kết nối thiết bị với DD qua VPS.

## DD Connector 0.3.0-beta.1

Bản thử nghiệm có giao diện chọn thiết bị, ghép mã và nhật ký lệnh. Đã kiểm thử tự động; chưa nghiệm thu phiên bản này trên HA OS thật. Dùng bản sao lưu trước khi thử.

## Cài mới

1. Trong Home Assistant mở **Cài đặt → Ứng dụng → Cài đặt ứng dụng → Kho lưu trữ** (các bản HA cũ gọi là Add-ons).
2. Thêm `https://github.com/vinhduong6868/DD`.
3. Chọn **DD Connector**, cài đặt và cấu hình `relay_url` theo máy chủ DD được cấp. Đường truyền phải là `wss://`.
4. Khởi động, mở giao diện Connector, chọn các thiết bị cần chia sẻ và lưu.
5. Tạo mã kết nối. Trong DD Core vào **Kết nối → DD Cloud**, đăng nhập và nhập mã. Một mã ghép cả nguồn HA; chỉ các thiết bị được chọn mới được chia sẻ.
6. Sau khi thử thành công, bật tự khởi động và giám sát trong HA nếu muốn ứng dụng tự chạy lại.

Không cần đăng nhập GitHub để tải kho công khai. Quản trị Connector cần tài khoản quản trị HA; ghép vào Core cần quyền tương ứng của nhà trong DD. Kho này không cung cấp tài khoản hoặc quyền truy cập máy chủ DD.

## Đã dùng bản Local?

**Đừng gỡ bản Local đang chạy.** HA coi bản cài từ kho mới và ứng dụng Local là hai ứng dụng khác nhau; dữ liệu ghép và danh sách chia sẻ không tự chuyển. Sao lưu ứng dụng cũ trước, giữ bản cũ để khôi phục, rồi lập kế hoạch chuyển liên kết. Chưa có công cụ di chuyển tự động trong phiên bản này. Không chạy hai Connector dùng cùng thông tin liên kết đồng thời.

## Nhật ký lệnh

Mở **Nhật ký lệnh → Làm mới nhật ký**. Hiện mã lệnh do VPS tạo, thực thể đích, hành động, thời gian, thời lượng, giai đoạn và mã lỗi HTTP nếu có.

- **HA đã chấp nhận**: API HA nhận lời gọi, chưa chứng minh thiết bị thực hiện.
- **Trạng thái HA đã khớp**: đọc lại HA thấy trạng thái mong đợi; vẫn không phải đo đạc vật lý độc lập.
- **Chưa xác nhận trạng thái**: đọc lại chưa khớp, bị lỗi, hoặc hàng chờ đang đầy.
- **Lệnh thất bại**: kiểm tra chia sẻ hoặc gọi HA không thành công.

Tối đa 200 sự kiện/24 giờ, lưu RAM và mất khi Connector khởi động lại. Không ghi tham số lệnh, URL media, token hay lời nói. Chỉ quản trị HA được xem. Mã lệnh hiện nối VPS ↔ Connector; chưa đồng nhất với mã kiểm toán Core.

## Giới hạn

Không phải mọi thiết bị đều báo trạng thái tức thì. Chỉ đọc lại các hành động có trạng thái quan sát được; không tự gửi lại lệnh. HA entity lỗi không được coi là lệnh thành công. Gói không kèm Music Assistant hoặc chức năng tải nhạc/video.

## Báo lỗi

Gửi phiên bản, mã lệnh, thời gian và mã lỗi trong nhật ký. Không gửi token, mã ghép còn hiệu lực, file options/credentials hoặc dữ liệu riêng của nhà.

## Kết nối với Core trong mạng nội bộ (0.4.0-beta.1)

Yêu cầu Core vật lý đã có runtime DD Connector local và Home Assistant cùng mạng nội bộ. DD Cloud vẫn dùng cấu hình và thông tin ghép hiện tại.

1. Trên Core: Thiết bị → Home Assistant → Thêm Home Assistant → Local · DD Connector. Copy địa chỉ Core và mã xác minh chứng chỉ từ Core đã đăng nhập.
2. Trong DD Connector: Kết nối với DD trong mạng nội bộ. Dán địa chỉ và mã xác minh, rồi bật kết nối nội bộ.
3. Nhập mã kết nối do Connector hiển thị vào Core. Quyền ghép được kiểm tra bằng quyền quản lý nhà hiện có.
4. Chọn các entity muốn chia sẻ trong Connector rồi Đồng bộ trên Core. Chọn “Đồng bộ tất cả” sẽ chia sẻ toàn bộ danh sách theo chính sách hiện có.

Chỉ một transport hoạt động tại một thời điểm. Ghép local và Cloud lưu thông tin riêng; không tự chuyển sang Cloud khi LAN lỗi. Cấu hình local giữ qua restart. Không cung cấp HA token cho Core. Core kiểm tra nguồn canonical trước khi đọc hoặc gửi lệnh.

Local dùng TLS và đối chiếu SHA-256 chứng chỉ Core; địa chỉ phải phân giải về mạng riêng. Khi chứng chỉ Core thay đổi, cần cập nhật mã xác minh từ Core. Kết nối API key trên Core vẫn được giữ; bản này không tự chuyển hoặc gộp các nguồn. Khi dùng nhiều nguồn cho cùng Home Assistant, kiểm tra nguồn của từng thiết bị trước khi điều khiển.

Bản beta đã kiểm thử bằng dữ liệu giả; nghiệm thu LAN và thiết bị thực tế còn cần hoàn tất trên cặp Core/Home Assistant. Phản hồi “accepted_unverified” chỉ cho biết HA nhận yêu cầu, không khẳng định thiết bị vật lý đã đổi trạng thái.
