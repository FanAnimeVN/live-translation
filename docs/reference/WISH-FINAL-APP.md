# Live translation — Wish Final App

Tổng hợp ngày 18/10/2026 từ yêu cầu, phản hồi, ví dụ và các kế hoạch đã bàn trong cuộc trò chuyện.

Đây là bản mô tả **sản phẩm người dùng mong muốn**, không phải báo cáo đã hoàn thành, cam kết ngày phát hành hay lệnh tiếp tục triển khai. Goal phát triển đã được tạm dừng theo yêu cầu. Tài liệu này không thay đổi mã nguồn, cấu hình, mặc định hay ngân sách.

## 1. Ước muốn trung tâm

> Mở một trang manga raw tiếng Nhật trên web, bật dịch và đọc tiếng Việt như đang đọc một bản manga được dịch, biên tập và dàn chữ chỉn chu: đúng nghĩa, đúng quan hệ nhân vật, đúng chất Nhật và đúng vibe của bộ truyện. Chữ hòa vào tranh đến mức gần như quên rằng mình đang bật dịch. Truyện nhớ những gì mình đã đọc, tên gọi giữ nhất quán, lướt đọc liên tục, quay lại không phải chờ hay trả tiền dịch lại vô ích.

Đây không chỉ là OCR cộng một lớp chữ Việt. Sản phẩm phải giải quyết **toàn bộ trải nghiệm đọc**.

Thứ tự ưu tiên đã xác lập:

1. Đúng nghĩa, ngữ cảnh và cảm xúc.
2. Chữ dịch hòa vào manga, không hỏng tranh.
3. Đọc liên tục, nhanh và ổn định.
4. Chi phí/tài nguyên hợp lý và các tính năng mở rộng.

Chất lượng phải được hoàn thiện trước khi tối ưu tốc độ/chi phí bằng những đánh đổi làm mất nội dung. Điều đó không bỏ mục tiêu phản hồi gần thời gian thực của sản phẩm cuối.

## 2. Trải nghiệm từ lúc mở truyện đến lúc đọc tiếp

- Cài đặt đơn giản; dùng trên trình duyệt thật, không cần người đọc biết repo, Python, môi trường phát triển hay lệnh khởi động server.
- Nếu cần companion Windows thì nó phải được đóng gói, kết nối và chẩn đoán rõ ràng; không để người đọc liên tục mắc kẹt ở lỗi không tìm thấy host.
- Chọn hoặc xác nhận đúng truyện/chapter; hệ thống không âm thầm trộn hai bộ hay hai phiên bản.
- Bấm dịch là hệ thống tự nhận diện phần chữ phù hợp và chuẩn bị bản dịch, không bắt khoanh từng bóng thoại.
- Nội dung của trang/ảnh đã tải được chuẩn bị trước; không phải cứ lướt đến đúng ảnh rồi mới bắt đầu dịch từ đầu.
- Có thể đợi một khoảng tải ban đầu ngắn nếu đổi lại đọc mượt; trạng thái phải rõ, không để chờ vô định.
- Chuẩn bị có giới hạn các ảnh tiếp theo để khi lướt tới đã có bản dịch; ưu tiên phần đang đọc, không âm thầm dịch cả website hoặc phát sinh phí ngoài ý muốn.
- Cuộn, zoom, resize, ảnh tải muộn và chuyển chapter không làm chữ lệch, giật, dính nhầm ảnh hay xuất hiện kết quả của trang cũ.
- Xem gốc tức thì, khôi phục cả chữ và tranh nguyên bản; có thể bật lại bản dịch.
- Khi một chỗ sai, người đọc sửa hoặc thử lại đúng chỗ đó; không phải dịch lại cả trang.
- Đóng rồi mở lại vẫn giữ tiến độ, bộ nhớ truyện, các xác nhận và bản dịch hợp lệ đã lưu.

## 3. Dịch Nhật–Việt đúng, tự nhiên và giữ chất manga

### Nghĩa và văn phong

- Không chỉ thay từng từ: phải hiểu đủ câu, các cột thuộc cùng một lượt thoại, lượt đối đáp và ngữ cảnh liên quan.
- Không mất phủ định, chủ thể, đối tượng, quan hệ cho–nhận, sắc thái nghi vấn, điều kiện hoặc ý chưa chắc chắn.
- Không gom hai người nói thành một, hoặc cắt một câu thành nhiều mảnh tiếng Việt khó đọc.
- Tiếng Việt phải tự nhiên, có nhịp và hợp nhân vật; không thô, cứng, đơ, lặp từ, quá Hán hóa hay tự thêm ý.
- Các ví dụ như xưng hô “chị/tôi”, thuật ngữ kiểu “băng kết giới”, từ lặp và ký tự dư phải được xét bằng nguồn/ngữ cảnh, không chữa theo cảm giác hoặc thay từ hàng loạt.
- Không coi mọi cặp “chị/tôi” là sai: phải hiểu ai nói với ai, thái độ và quan hệ tại thời điểm đó.
- Mỗi truyện/thể loại có giọng phù hợp: học đường, đời thường, fantasy, chiến đấu, lịch sử, hài, kinh dị, sci-fi… Không dùng một lớp văn phong chung cho tất cả.

### Văn hóa Nhật và danh xưng

- Mặc định giữ những hậu tố/cách gọi Nhật có ý nghĩa trong bản gốc: senpai, sama, san, kun, chan, onii-chan, nee-chan…
- Giữ cấu trúc cách gọi như Kirito-kun, Asura-san khi phù hợp với nguồn; không tự thêm hậu tố chỉ để tạo cảm giác anime.
- Phân biệt họ, tên, biệt danh và danh xưng. Chuyển từ gọi họ sang tên, bỏ hậu tố hoặc đổi cách gọi có thể là diễn biến quan hệ, không được làm mất dấu hiệu ấy.
- Không áp một quy tắc tuyệt đối rằng chỉ người thân mới gọi tên; tôn trọng ngữ cảnh cụ thể trong nguồn.
- Xưng hô được nhớ theo hướng người nói → người nghe; A gọi B thế nào không tự quyết định B gọi A thế nào.
- Không bịa giới tính, tuổi, vai vế, quan hệ hay người nói khi chưa có bằng chứng; unknown vẫn là unknown.
- **Không “chị nee-chan”, “chị gái nee-chan”, “anh onii-chan”, “anh trai onii-chan”.** Lời gọi đã giữ nee-chan/onii-chan không chồng thêm danh xưng Việt cùng nghĩa.
- Quy tắc trên không xóa đại từ Việt hợp lệ ở phần còn lại của câu, không biến mọi câu kể về anh/chị thành tiếng Nhật và không ghi đè ngoại lệ người đọc đã khóa.

### Cảm xúc phải nằm cả trong cách trình bày

- Giữ nói lắp, ngập ngừng, kéo âm, nhấn mạnh, câu đứt quãng, dấu ba chấm và ngắt đoạn có dụng ý.
- Nhận diện kiểu Wa-ta-shi, lời nói từng âm/từng chữ, hoặc I L O V E Y O U; bản dịch phải thể hiện nhịp chậm và hàm ý ấy, không làm phẳng thành một câu bình thường.
- Giữ tác dụng của chữ IN HOA, kích cỡ/nhấn chữ và khoảng cách biểu cảm khi có thể.
- Không để output sinh thêm cặp dấu nháy rỗng, ký tự rác, phần giải thích hay lặp câu.
- Đồng thời không xóa dấu Nhật, ngoặc thoại, dấu ba chấm hoặc khoảng cách có nghĩa chỉ để làm OCR trông sạch. Ngoặc thoại có thể kéo qua nhiều bóng.

### Thị hiếu độc giả

- Nghiên cứu đủ nghiêm túc cộng đồng đọc manga/anime, đặc biệt người đọc Việt: họ thích giữ chất Nhật đến đâu, điều gì làm bản dịch khó đọc, loại xưng hô/văn phong nào hợp từng thể loại.
- Dùng nghiên cứu và chấm đọc thật để hoàn thiện trải nghiệm; không coi vài bình luận là ý kiến đại diện toàn cộng đồng.
- Hướng mặc định là giữ chất Nhật nhưng câu Việt mượt; lựa chọn phong cách theo truyện có thể bổ sung nếu có ích, không làm loãng các quy tắc nghĩa và nhất quán.

## 4. Tên và thuật ngữ nhất quán từ đầu đến cuối

- Có bộ thuật ngữ riêng cho từng truyện: nhân vật, biệt danh, bang hội, tổ chức, clan, hội mạo hiểm giả, vũ khí, kỹ năng, địa danh và các khái niệm lặp lại.
- Khi đã có tên chính thức hoặc reader xác nhận, giữ nhất quán; không mỗi trang một cách dịch.
- Khi chưa có, chọn một phương án hợp lý, đẹp và sát nghĩa nhất có thể, dùng ổn định nhưng ghi rõ chưa được người đọc kiểm chứng.
- Chính tả/cách đọc/tên ưu tiên không được đổi ngẫu nhiên giữa các model hay các lần đọc.
- Phân biệt tên chuẩn với bí danh, biệt danh, cách gọi thân mật, tên được tiết lộ sau hoặc tên khác thật sự có trong nguyên tác. Không thay mọi cách gọi bằng tên đầy đủ.
- Có quy tắc theo thể loại; không dịch tên fantasy, tên học đường và tước vị lịch sử bằng một công thức máy móc.

### Người đọc tham gia, nhưng không phải làm biên tập viên toàn thời gian

- Khi thực sự chưa chắc, hỏi gọn: “Cách gọi này đúng ý bạn chưa?” với **Đúng / Đổi / Để sau**.
- Có nút xác nhận và chỉnh sửa về sau; lỡ xác nhận sai vẫn sửa được.
- Nhớ lựa chọn cho các lần tiếp theo; không hỏi lại cùng vấn đề liên tục.
- Không chặn việc đọc bằng một chuỗi popup cho từng tên/từng chữ.
- Khóa của reader có ưu tiên hơn dự đoán AI; khi sửa phải giữ lịch sử và mốc áp dụng, tránh đưa tên được tiết lộ sau về chapter trước.

## 5. Chữ phải trông như được in sẵn vào truyện

Mục tiêu thị giác là **readable and looks integrated into the manga**: gần với một bản scanlation được typeset tốt, không phải thẻ dịch nổi trên ảnh.

### Trong bóng thoại

- Xóa sạch chữ gốc trong phạm vi có thể xử lý an toàn, bao gồm viền/halo cần thiết; không để ký tự lồi ra ngoài chữ Việt.
- Giữ màu và kết cấu của bóng gốc; không phủ một hình chữ nhật trắng khác màu lên bóng.
- Dàn chữ Việt trên nền trong suốt sau cleanup khi phù hợp; không cần tạo một lớp nền mới dễ nhận ra.
- Tự cân dòng, lề, căn giữa, line-height và cỡ chữ để fit hình dạng/vùng trống của bóng.
- Ưu tiên phong cách và cỡ chữ gần bản gốc, chọn font tương tự hoặc font dễ đọc tối ưu; dấu Việt phải đẹp và đủ.
- Không cố giữ cùng cỡ chữ nếu câu Việt dài hơn làm tràn; cũng không thu nhỏ đến mức không đọc được hay cắt nghĩa để vừa.
- Không chồng hai bản dịch lên nhau, đè viền/tail bóng hoặc che nội dung tranh.

### Chữ không có bóng và chữ trên cảnh

- Không mặc định đưa một tấm nền đặc sau chữ dịch làm mất tranh.
- Hướng trải nghiệm mong muốn: xóa chữ cũ, phục hồi phần nền bị che rồi đặt chữ Việt vào, giữ cảm giác tranh liên tục.
- Bao gồm các ví dụ nền mưa, đường mưa, texture và khung cảnh mà người dùng đã gửi: zoom gần vẫn không dễ thấy một miếng vá hay chữ gốc sót lại.
- Nhận thức rằng phần tranh dưới chữ không có sẵn có thể chỉ được tái dựng, không được gọi kết quả suy đoán là nguyên tác thật.
- Không phục hồi bằng cách làm hỏng khuôn mặt, vật thể, nét tranh hoặc chi tiết có nghĩa. Khi không chắc phải giữ tranh gốc và cho một phương án đọc/annotation có thể đảo ngược.
- Fallback hữu ích nhưng không được báo thành “đã integrated hoàn hảo”.

### Tùy chọn chất lượng đúng triết lý của người dùng

- Cải thiện tốt, an toàn, rẻ và không làm chậm đáng kể: **bật mặc định**, không giấu sau quá nhiều tùy chọn.
- Cleanup local không gửi ảnh/không tốn credit, có giới hạn và đảo ngược được là ví dụ phù hợp, nếu có bằng chứng chất lượng.
- Tôn trọng người đã chủ động tắt một tính năng.
- Chỉ khi có đánh đổi đáng kể về API/credit, thời gian, RAM/pin hoặc nguy cơ sửa tranh mới để tùy chọn riêng.
- Tính năng immersion/redraw cao cấp phải dễ tìm, giải thích được lợi ích, chi phí, thời gian và rủi ro; hỏi xác nhận trước lần sử dụng bị ảnh hưởng.
- Không dùng model tạo ảnh cho một bóng nền phẳng chỉ vì đã bật chế độ đẹp.
- Lưu cài đặt không tự chạy dịch, gửi ảnh hoặc tính phí.

## 6. Hiểu loại chữ, không dịch mọi thứ vô tội vạ

- Hỗ trợ chữ Nhật dọc/ngang và bố cục nhiều cột; giải quyết furigana, chữ nhỏ, chữ stylize và SFX thay vì chỉ tối ưu bóng thoại sạch.
- Phân biệt thoại, suy nghĩ, lời dẫn, thư/biển/bảng có ý nghĩa, SFX và chữ trang trí/phụ.
- Ví dụ bảng nền dày đặc: không dịch hàng loạt tất cả chữ chỉ vì detector thấy chữ.
- Đồng thời không bỏ một manh mối, thư hoặc lời dẫn chỉ vì nhỏ, dày hay không có bóng.
- Chỉ tự bỏ qua khi có bằng chứng không liên quan hoặc reader yêu cầu; trường hợp chưa rõ giữ nguyên và cho người đọc dịch vùng đó nếu muốn.
- Có cách chọn dịch thêm, bỏ qua hoặc sửa phân loại từng vùng, không hỏi liên tục trong lúc đọc.
- Chữ bị để sau không biến thành sự kiện cốt truyện trong bộ nhớ.
- SFX cần cách xử lý riêng, giữ tác dụng thị giác/cảm xúc; không mặc định xóa chữ trang trí lớn rồi vẽ hỏng tranh.

## 7. Truyện có trí nhớ, nhưng không biết trước phần người đọc chưa đọc

### Bộ nhớ riêng cho từng bộ

- Nhớ nhân vật, tên gọi, thuật ngữ, quan hệ đã có bằng chứng, sự kiện quan trọng và tiến độ.
- Đọc tới đâu, tích lũy tới đó; dùng ngữ cảnh gần và sự kiện liên quan để dịch trang sau tốt hơn.
- Chủ yếu lưu sự kiện/tóm tắt cô đọng, không nhồi toàn bộ thoại từ đầu truyện vào mỗi request hay biến lorebook thành transcript ngày càng dài.
- Có thể cần lưu nguồn ngắn của sự kiện và cache thoại tạm thời để kiểm tra; mục tiêu không lưu tràn lan không có nghĩa xóa hết chứng cứ.
- Mỗi điều nhớ có nguồn, chapter/page và mốc được biết. Tách sự kiện, suy đoán, lời đồn, câu hỏi và điều reader xác nhận.
- Không để một bản tóm tắt sai trở thành “sự thật” rồi làm sai các trang sau.
- Không trộn ký ức giữa truyện; không kéo dữ kiện của chapter sau về trước khi đọc lại/nhảy chapter.
- Prefetch hoặc dịch xong một trang không có nghĩa người đọc đã đọc trang ấy.

### Tóm tắt bằng model phù hợp

- Có thể dùng model dịch nhanh/chất lượng và model tóm tắt rẻ riêng nếu thực sự tốt hơn.
- Tóm tắt chạy nền theo các mốc đọc phù hợp; không tranh tài nguyên hay chặn phản hồi dịch đang đọc.
- Không bắt buộc công thức cứng “cứ 10–15 trang” hoặc dùng nhiều model chỉ vì có thể; mục tiêu là context hữu ích, ít phí, ít sai và không spoil.
- Công việc cloud nền cũng phải minh bạch và được cho phép; không lén xử lý backlog rồi phát sinh hóa đơn.

### Tra thông tin nền và cold start

- Ý tưởng đã nêu: nhận diện truyện và tìm thông tin nền/alias/nhân vật từ nguồn như wiki trước hoặc khi bắt đầu dịch.
- Điều kiện không được phá: đúng bộ, có nguồn và **không lấy kiến thức tương lai để tiết lộ thân phận, quan hệ, twist hay cốt truyện chưa đọc**.
- Vì vậy tra hồ sơ nhân vật/plot tự do không mặc nhiên là mặc định an toàn; đây là hướng cần thiết kế kỹ, không phải giấy phép tự crawl mọi wiki.
- Không tìm thấy, truyện mới, ngách hoặc doujinshi vẫn đọc/dịch được: bắt đầu bằng bộ nhớ trống và xây từ các trang đã đọc.
- Không ép reader chờ có wiki, không bịa thông tin nền, không đoán quan hệ rồi khóa như sự thật.

### Reader sở hữu bộ nhớ

- Có nơi xem/sửa/xác nhận tên, thuật ngữ, xưng hô, ghi nhớ và tiến độ theo truyện.
- Có backup/import/export để không mất lựa chọn khi chuyển hoặc cài lại; không kèm key hay ảnh riêng trong gói chia sẻ.
- Định dạng SQLite/Markdown/JSON là lựa chọn kỹ thuật đã bàn, không phải trải nghiệm người đọc phải hiểu hay tự quản lý.

## 8. Chat ngay trong lúc đọc — ước muốn đã ghi nhận, để sau MVP

- Hỏi “nhân vật này là ai?”, “nguồn gốc thế nào?”, “vì sao có cảnh này?”, “sự kiện vừa rồi nghĩa là gì?” mà không rời trang đọc.
- Nhắc lại những gì đã đọc khi quên context hoặc quay lại sau lâu ngày.
- Giải thích rõ, hấp dẫn, có thể nêu suy đoán theo cách gợi hứng thú, nhưng phân biệt suy đoán với sự kiện.
- **Tuyệt đối không spoil**, kể cả model vốn biết toàn bộ cốt truyện hoặc tìm được wiki.
- Không spoil bằng ám chỉ, xác nhận/phủ nhận một twist hay kiểu “sau này bạn sẽ hiểu”.
- Chỉ dùng manh mối người đọc đã tiếp cận; có thể chỉ lại mốc để reader tự suy luận.
- Nếu reader yêu cầu spoil: cảnh báo, nêu phạm vi và xin xác nhận rõ trước khi tiết lộ.
- Đây là tính năng tương lai cần lưu lại, không chen vào thay việc hoàn thiện dịch/lettering hiện tại.

## 9. Nhanh, tiết kiệm và nhẹ máy

- Cảm giác mong muốn: bấm dịch phản hồi gần ngay, chuẩn bị nhanh, sau đó đọc không bị đứt quãng.
- Không chờ quá lâu với vài chữ/bốn bóng thoại; không báo “bản dịch quá dài” rồi ngưng toàn bộ khi request thực sự nhỏ.
- Chỉ sửa/retry phần lỗi, giữ phần đúng; giới hạn retry để không đốt credit.
- Cache kết quả hợp lệ để đọc lại không phải OCR/dịch/tính tiền từ đầu.
- Đổi giao diện, cuộn hay scheduler không được vô cớ làm hết cache; đổi OCR/thuật ngữ/context liên quan thì phải tránh trả lại bản sai cũ.
- Prefetch có giới hạn, ưu tiên trang hiện tại và minh bạch chi phí; không tải vô hạn cả chapter trong nền.
- Không giữ toàn bộ ảnh và model không cần thiết trong RAM. Mục tiêu máy 16 GB không GPU rời vẫn dùng hợp lý.
- Phân biệt lần đầu lạnh, đã warm và cache; không dùng tốc độ cache để hứa tốc độ API mới.
- Các mục tiêu từng thống nhất để đo: bóng đầu đã warm p95 <5 giây; trang cloud tối đa 12 bóng p95 <8 giây; hiển thị cache đã định vị p95 <200 ms. Đây là mục tiêu, không phải kết quả đã đạt hay lời hứa tức thì mọi trang.

## 10. Cloud trước, local sau; có miễn phí lẫn trả phí

- Trước mắt tối ưu tuyến cloud để đạt chất lượng và demo desktop thực dụng; không tiếp tục dồn trọng tâm sang local chậm/yếu.
- Tìm model/route có điểm cân bằng tốt nhất giữa nghĩa Việt, văn phong, tốc độ, giá và độ ổn định.
- Có model mặc định phù hợp và một số lựa chọn khác đã thử nghiệm, không yêu cầu reader tự nghiên cứu hàng chục model.
- Các tên Haiku/DeepSeek/GLM… và số liệu quảng cáo từng xuất hiện là ứng viên/đề xuất cần kiểm chứng, không là yêu cầu phải dùng bằng mọi giá.
- Không chọn mặc định chỉ từ lời quảng cáo, bảng xếp hạng hoặc vài câu demo.
- Có hướng **BYOK** cho người mang key và hướng **subscription/credit** cho người muốn dùng sẵn; tự cấu hình được những gì có thể, vẫn rõ provider/model/chi phí.
- Có hướng local/offline miễn phí, hướng dẫn tải model và setup dễ làm, nhưng tối ưu sau khi cloud desktop hoàn thiện.
- Offline thật sự không gọi cloud, không tra metadata/wiki trong nền.
- Gói cloud 30 ngày/credit đã nằm trong hướng mở rộng sau beta; giá, quota và cam kết thương mại cụ thể chưa chốt.
- Không dùng key phát triển chung làm key trong bundle cho cả nhóm. Ngân sách thử đã cho không phải ngân sách vô hạn hay một phần giá sản phẩm.

## 11. UX chuyên nghiệp và lỗi phải có đường thoát

- Giao diện sạch, gọn, ít gây chú ý; phần đọc truyện là trung tâm.
- Không popup dày đặc, không viền debug/tooltip/card trắng thường trực trên manga.
- Có trạng thái đủ rõ: đang chuẩn bị, OCR/dịch, sẵn sàng, phần cần xem lại; không đổ chi tiết kỹ thuật lên reader nếu không cần.
- Kết nối companion bền vững, tự nối lại hợp lý và hướng dẫn khắc phục đúng nguyên nhân.
- Phân biệt mất kết nối, chưa cài host, key sai, hết quota, timeout, OCR và output sai; không báo mọi vấn đề thành “dịch quá dài”.
- Mất kết nối không có nghĩa thư viện trống; không bắt nhập lại key hay xóa memory vô cớ.
- Dữ liệu và bản dịch đúng không biến mất vì một vùng lỗi; thao tác hủy/dịch lại/sửa không làm kết quả cũ quay lại đè lên.
- Thay đổi trong mã nguồn phải được đưa vào đúng runtime/bundle trước khi nói người dùng đang có bản mới.
- Nhóm test có bộ cài/hướng dẫn để tự chạy trên Windows sạch, không cần nhờ agent sửa registry lặp đi lặp lại.
- Không yêu cầu reader tắt phần mềm bảo mật để sử dụng; không đóng ứng dụng hay khởi động lại trình duyệt ngoài sự đồng ý.

## 12. Phạm vi nền tảng và mở rộng

- Cốt lõi trước mắt: manga raw Nhật → Việt trực tiếp trên web, Windows desktop, Edge/Chrome.
- Điện thoại là mong muốn về sau: phải nhẹ và có hướng kiến trúc phù hợp, nhưng **đã quyết định tạm bỏ khỏi MVP**.
- Safari và các dịch vụ/extension có tính năng dịch là nguồn học hỏi; không suy ra rằng Safari/iOS phải được làm ngay cùng desktop.
- Korean manhwa, Chinese manhua và nhiều ngôn ngữ có thể là hướng mở rộng, nhưng không được đổi mục tiêu chất lượng Nhật–Việt lấy một nhãn “80+ languages”.
- Anime là tham chiếu về văn hóa/nhịp thoại/vibe trong các góp ý; chưa có yêu cầu chốt xây cả hệ thống dịch video/phụ đề trực tiếp trong MVP.
- File ZIP/PDF, kho context cộng đồng, đồng bộ cloud và các ý tưởng mở rộng không tự thành cam kết phải xây chỉ vì từng xuất hiện trong mô tả đối thủ/lộ trình.

## 13. Học từ sản phẩm tốt, không biến nghiên cứu thành mục tiêu cuối

- Tham khảo Scan Translator, Ichigo/Manga Translator, các tính năng dịch liên quan trên Safari và trải nghiệm scanlation thật.
- Đối chứng kỹ thuật ưu tiên **manga-image-translator**; Comic Translate thứ hai; Kites tham khảo phụ về UX, không là chuẩn chất lượng chính.
- Tìm trên GitHub/Hugging Face, đọc tài liệu kỹ thuật, tìm model/dataset/thuật toán phù hợp; tái sử dụng thành phần hợp pháp khi thực sự hiệu quả.
- Không suy chất lượng hoặc engine nội bộ của dịch vụ thương mại từ screenshot, stars hay quảng cáo; không sao chép mã/weight/font không đáp ứng giấy phép sản phẩm.
- Fine-tune/train bằng dữ liệu có quyền là một công cụ nếu chứng minh cần thiết, không phải mục tiêu riêng hay lý do trì hoãn sản phẩm vô hạn.
- Mục tiêu cuối là trải nghiệm tương đương hoặc vượt đối thủ trong phạm vi được kiểm tra, không phải số lượng tài liệu, model, thử nghiệm hay test pass.

## 14. Kiểm chứng phải bám vào trải nghiệm thật

- Sau test tự tạo phải chạy bộ manga riêng người dùng đã gửi tại `C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001`.
- Giữ nguyên nguồn, rà nhãn/quyền/trùng lặp; không thay nhãn, bỏ câu khó hay nới matcher để tạo điểm đẹp.
- Mong muốn là xử lý đầy đủ, đúng mọi câu trong bộ chuẩn đã xác minh, tiến tới 78/78 chứ không hài lòng với một demo sạch. Một điểm OCR không tự chứng minh dịch Việt hoặc phục hồi tranh đạt.
- Không được để cải tiến một ca làm mất câu, gom sai người, xóa nhầm tranh hoặc làm hỏng ca từng tốt.
- Khi báo tiến độ phải phân biệt cùng dữ liệu/cấu hình nào: production, candidate, crop chuẩn, toàn trang, replay hay inference mới. Không đưa 49/78 rồi chuyển sang 36/78 mà không giải thích.
- Kiểm tra trang thật khó: nền mưa, chữ không bóng, bảng dày, chữ nhỏ, cột dọc, dấu hỏi, ngoặc, typography biểu cảm và thoại dài.
- Thử cả cuộn/zoom/resize/lazy loading, sửa OCR, đổi tên/xưng hô, cache, đổi chapter, timeout/crash/quota và khôi phục bản gốc.
- Nhiều unit test xanh không có nghĩa người đọc đã có một sản phẩm tốt; cần chấm nghĩa Việt, thị giác và phiên đọc thực tế.
- Phải có test độc lập/reader phù hợp để tránh tự chấm quá lạc quan. Các mục tiêu số chi tiết đã bàn là tiêu chí kiểm chứng, không được báo thành kết quả đạt.
- Ưu tiên cuối cùng trước lúc tạm dừng: nâng chất lượng trong môi trường riêng trước, không liên tục yêu cầu người dùng mở/reload Edge; khi đủ tin cậy mới để người dùng test một lượt. Quyết định này thay cho yêu cầu test Edge liên tục ở giai đoạn trước.

## 15. Riêng tư, quyền kiểm soát và dữ liệu

- Ảnh/crop/patch riêng chỉ ở RAM; không âm thầm lưu dataset, ảnh truyện, key hoặc memory vào repo, log hay bundle chia sẻ.
- Khi reader chọn cloud OCR/dịch/redraw phải biết phần nào được gửi tới provider và có quyền cho phép sử dụng.
- Key lưu an toàn; không đưa vào bộ cài/test bundle hoặc xuất context.
- Không tính phí hoặc chuyển sang cloud/nhà cung cấp khác âm thầm khi offline, lỗi hoặc đổi cài đặt.
- Reader kiểm soát tên/xưng hô, chế độ đọc, những vùng bỏ qua và việc dùng tính năng tốn thêm.
- Không có lợi ích UX nào cho phép làm lộ spoiler, ghi đè lựa chọn đã khóa, hỏng tranh hoặc chi tiền ngoài đồng ý.

## 16. Đường ranh để không đi xa khỏi mong muốn ban đầu

### Lõi phải làm tốt

Một người bình thường mở manga trên desktop, bật dịch, đọc tiếng Việt đúng và đẹp, lướt liên tục, nhớ context/tên gọi, sửa được chỗ chưa chắc và quay lại vẫn đọc được.

### Thuộc bản hoàn chỉnh, nhưng không chen vào giải quyết lõi

Chat không spoil, local/offline miễn phí tối ưu, hướng mobile và thanh toán/subscription hoàn chỉnh. Safari và các mở rộng ngôn ngữ/định dạng cần xác nhận phạm vi riêng; không tự coi việc nhắc tới đối thủ là yêu cầu phải triển khai.

### Là phương tiện, không phải “wish” bắt buộc

Một model cụ thể, một detector, nhiều agent, một thuật toán inpainting, schema SQLite, số phiên bản prompt, số test, tên adapter hay một mốc OCR của thử nghiệm. Chọn chúng theo hiệu quả đối với trải nghiệm; không để chúng thay thế mục tiêu sản phẩm.

### Chưa được mặc nhiên quyết định

Giá bán cuối, quota cuối, tên model mặc định cuối, tự thu thập wiki/nhân vật không giới hạn, dịch mọi chữ/mọi trang/mọi ngôn ngữ, train bằng mọi dữ liệu tìm được, bật redraw trả phí mặc định hoặc hứa vượt đối thủ trên mọi manga.

## Một câu để kiểm tra mọi quyết định sau này

> Thay đổi này có giúp người đọc thấy mình đang đọc một bản manga Việt đúng, tự nhiên, đẹp như được làm sẵn — nhanh, nhất quán, không spoil, không phá tranh và không phát sinh chi phí bất ngờ — hay chỉ làm hệ thống kỹ thuật phức tạp thêm?

## Phụ lục — Những chỉ tiêu đã bàn, không được nhầm với kết quả

Các con số này được giữ lại để không làm mất nội dung kế hoạch đã duyệt. Chúng là cách kiểm chứng mong muốn sản phẩm, không phải các tính năng reader phải nhìn thấy và không có nghĩa đã đạt:

- Nghĩa Việt: lỗi nghiêm trọng quan sát ≤2% trên ít nhất 500 lượt thoại ordinary held-out, có reviewer độc lập và khoảng tin cậy.
- Detection/grouping: recall ordinary ≥98%; không mất nguyên bóng hoặc overmerge trên regression riêng.
- Lettering: ≥95% bóng ordinary được chấm đọc được, fit và không thấy nền thẻ; báo riêng SFX/chữ trên tranh/ca khó.
- Bảo vệ nguồn: vùng tranh bảo vệ không bị sửa, xem gốc khôi phục chính xác.
- Tốc độ: warm first bubble p95 <5 giây; trang ≤12 bóng p95 <8 giây cloud; mốc local từng bàn <15 giây nhưng không là ưu tiên tối ưu hiện tại; cache đã định vị p95 <200 ms.
- Tài nguyên: mục tiêu RAM tăng thêm ≤4 GiB, không thrashing trên máy 16 GB; không lấy một lần tránh crash làm chứng cứ đã đạt.
- Đo tốc độ: ít nhất 100 lượt warm và 200 lượt cache, tách cold/warm/cache cùng máy, mạng, provider, phiên bản và tỷ lệ lỗi.
- Chính sách cache/prefetch từng bàn: OCR 24 giờ; bản dịch đã chấp nhận 30 ngày, tối đa 100 MiB LRU, không lưu ảnh; chuẩn bị tối đa hai ảnh DOM tiếp theo đã tải/truy cập được sau xác nhận chi phí. Hết cache tạm không được xóa reader locks/lịch sử.
- Mở rộng kiểm chứng sau khi qua bộ riêng: tối thiểu 100 trang/1.000 crop có quyền, ít nhất 50 trang từ tựa chưa dùng tuning; không gọi bộ tám trang đã sửa lỗi nhiều lần là held-out.
- Beta: ít nhất năm reader đọc phiên dài, quay lại, nhảy chapter; thử cài mới/cập nhật/rollback/gỡ/phục hồi bộ nhớ trên máy sạch.
- Chỉ tuyên bố vượt đối thủ trong phạm vi kiểm tra khi so mù đạt tỷ lệ ưu tiên ≥60%, khoảng tin cậy 95% loại trừ 50%, không đổi nghĩa hoặc tranh lấy điểm đẹp.
- Không stale result, future context, lộ key/text, gọi mạng khi offline, ghi đè reader lock, âm thầm tính phí hay migration mất dữ liệu.

Đây không phải một lộ trình triển khai mới. Mọi thay đổi phạm vi hoặc chỉ tiêu sau này cần được nói rõ, không tự hạ chuẩn để báo hoàn thành.
