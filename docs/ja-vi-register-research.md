# Xưng hô, tỉnh lược và thuật ngữ Nhật–Việt — 13/10/2026

Phạm vi: bằng chứng từ điển, nghiên cứu ngôn ngữ học và chia sẻ của nhóm bản địa hóa. Các ví dụ kiểm tra bên dưới được tự soạn; chưa chạy model, chưa chấm mù và không phải khảo sát sở thích độc giả Việt. Tài liệu bổ sung [reader-localization-research.md](reader-localization-research.md), không thay lựa chọn giữ cách gọi Nhật đã chốt.

## Bằng chứng và giới hạn

| Vấn đề | Nguồn gốc và kết luận có căn cứ | Giới hạn |
| --- | --- | --- |
| Lời gọi chị | Mục **姉さん** của Shogakukan *Digital Daijisen* nêu cả nghĩa chị gái và cách gọi thân mật một phụ nữ trẻ. [Mục từ trên Kotobank](https://kotobank.jp/word/%E5%A7%89%E3%81%95%E3%82%93-426267). Japan Foundation minh họa **お姉さん** là chị gái của người khác. [MARUGOTO Plus](https://a2-2.marugotoweb.jp/en/kanji/vocab/oneesan/). | Đây là thông tin về người được gọi/nhắc đến. **Suy luận triển khai:** 姉ちゃん/お姉さん dùng làm lời gọi không đủ để xác định ID, giới tính của người nói hay một quan hệ huyết thống. Phải phân biệt lời gọi với câu kể và cách tự xưng. |
| Thành phần bị lược trong tiếng Nhật | Nariyama phân tích việc khôi phục chủ thể/đối tượng dựa vào vị từ, cấu trúc câu và mạch diễn ngôn; các dấu hiệu có thể bị điều kiện khác chi phối. [*Grammar for ellipsis resolution in Japanese*, 2002, §1–3](https://aclanthology.org/2002.tmi-papers.15.pdf). | Nghiên cứu phục vụ Nhật–Anh trên tập văn bản nhỏ; không chứng minh chất lượng manga Nhật–Việt hay cho phép suy chủ thể bằng một regex. |
| Xưng hô Việt có tính quan hệ | Sidnell và Shohet mô tả từ thân tộc dùng cả với người không cùng huyết thống, biểu thị tuổi/thế hệ tương đối; hội thoại còn phối hợp tên riêng, đại từ và từ thân tộc. [Bài báo gốc, 2013](https://rai.onlinelibrary.wiley.com/doi/abs/10.1111/1467-9655.12053). | Không có ánh xạ phổ quát 私→tôi hoặc 姉→một nhân vật cố định. **Suy luận triển khai:** lưu quy tắc từng chiều A→B, không tự sinh B→A. |
| Tỉnh lược trong tiếng Việt | Ton nghiên cứu tỉnh lược từ xưng hô/tham chiếu trong giao tiếp; hiện tượng phụ thuộc ngữ cảnh và khả năng nhận ra người được nói đến. [*Ellipsis of terms of address and reference in casual communication events in Vietnamese*, 2018](https://benjamins.com/catalog/lali.00007.ton). | Có căn cứ để dùng câu lược đại từ khi tự nhiên, không để xóa vai nghĩa cần thiết. Nguồn không kết luận rằng mọi câu có “tôi” đều cứng hay sai. |
| 氷結 và 結界 | **氷結** là đóng băng/đông thành băng. [Daijisen](https://kotobank.jp/word/%E6%B0%B7%E7%B5%90-613196), [Kanjipedia của Japan Kanji Aptitude Testing Foundation](https://www.kanjipedia.jp/kotoba/0005931000). **結界** gồm nghĩa giới hạn một khu vực, và trong Mật giáo là ngăn sự xâm nhập bằng nghi thức. [Daijisen](https://kotobank.jp/word/%E7%B5%90%E7%95%8C-59537). | Hai mục từ không xác định công năng của một kỹ năng hư cấu tên 氷結結界. Cần ngữ cảnh truyện, tên chính thức hoặc glossary. |
| Văn phong và tên trong fantasy | Nhóm FFXIV mô tả xem lại thoại cũ để giữ giọng nhân vật, lựa chọn cách nói theo vai trò/bối cảnh, cân nhắc độ dễ đọc, và tránh trùng tên kỹ năng gây nhầm. [Phỏng vấn chính thức Square Enix, 2021](https://na.finalfantasy.com/topics/266). | Đây là quy trình của một game và những cặp ngôn ngữ khác. Không phải chuẩn bắt buộc cho manga Việt, không chứng minh cộng đồng thích một tên Hán–Việt cụ thể. Nhóm này có quyền trao đổi với tác giả; app đọc manga không tự nhận quyền sáng tác lore. |

## Quy tắc sản phẩm được đề xuất

1. **Giải nghĩa trước, chọn xưng hô sau.** Tách người nói, người nghe, chủ thể hành động và đối tượng hành động. Chỉ dùng A→B khi cặp đó có bằng chứng/đã xác nhận và đúng cutoff. Quy tắc A→B không phải danh xưng cố định cho A trong mọi lời thoại.
2. **Giữ cách gọi rõ trong nguồn theo chế độ truyện.** Khi giữ chất Nhật: 姉ちゃん trong lời gọi → nee-chan, お姉ちゃん → onee-chan; không thêm “anh/chị” trước một tên đã có -san. Khóa xưng hô Việt không xóa lời gọi nguồn đang được giữ. Câu kể 私の姉 không tự đổi thành lời gọi nee-chan.
3. **Cho phép câu lược đại từ tự nhiên.** “Cứu với!”, “Chưa về à?”, “Triển khai kết giới!” có thể đủ. Không tự thêm “tôi” vào mọi câu hành động; cũng không cấm “tôi” khi nguồn, trọng tâm hoặc giọng nói cần nó. Với 私がやる, giữ ý người nói nhận làm. Không lược đến mức đổi người đợi/người được đợi hay mất phủ định, yêu cầu, ý định.
4. **Đề xuất tên theo đơn vị nghĩa và thể loại.** Fantasy/action có thể chọn Hán–Việt gọn; đời thường ưu tiên từ Việt quen dùng; lịch sử cần bằng chứng về tước vị; sci-fi/thể thao giữ thuật ngữ rõ, chính xác. Đây là lựa chọn thiết kế. Không áp một giọng “ta–ngươi” cho mọi fantasy hoặc biến mọi danh từ thành tên kỹ năng.
5. **Tên đã xác nhận thắng đề xuất văn phong.** Dùng đúng tên chính thức đã xác minh hoặc tên người đọc khóa tại mốc hiện tại. Nếu hai lựa chọn xung đột, giữ khóa người đọc đang có và ghi xung đột; không tự ghi đè. Giữ nguồn của lựa chọn: `official`, `user`, `auto`; không gọi tên AI là “chính thức”. Alias có bản dịch riêng, tên đầy đủ và tên gọi tắt được ràng buộc theo dạng nguồn; không thay mù trong câu. Không đưa khóa chapter 4 vào chapter 2.

### Trường hợp 氷結結界

**Phân tích từ điển:** `[氷結] + [結界]`; không có căn cứ tự coi chữ 結 thứ hai là lỗi OCR. Nghiên cứu này chưa đối chiếu ảnh nguồn. Hai “kết” trong cách đọc Hán–Việt có chức năng khác nhau. Vì vậy, “Băng Kết Kết Giới” có thể lặp âm và khó đọc, nhưng không đủ căn cứ gọi là thừa nghĩa chỉ vì lặp chữ. Không chạy quy tắc xóa từ trùng toàn cục.

**Khuyến nghị biên tập khi chưa khóa:** đề xuất **Kết giới băng giá** cho cách đọc rõ nghĩa; **Băng kết giới** là một phương án fantasy ngắn hơn. Nếu nguồn xác nhận kết giới làm mục tiêu đông cứng, cân nhắc **Kết giới đóng băng**. Hai từ điển không quyết định nó là tường băng, vùng đóng băng hay chỉ kết giới lạnh; không thêm “tuyệt đối”, “vĩnh cửu” hoặc sức mạnh chưa nêu. Những phương án này là đề xuất, chưa phải tên chuẩn của một tựa hay kết quả khảo sát. Khi người đọc khóa **Băng Kết Kết Giới**, giữ đúng chuỗi đó.

## Các dòng prompt có thể dùng

```text
Resolve action roles before Vietnamese address terms: speaker, listener, agent and patient may differ. A direct vocative identifies the addressed role, not the speaker's identity or gender. Keep unknown identities unknown.
Use a confirmed directed A→B self/address pair only when this bubble's speaker and listener match that pair. Do not infer the reverse pair. Retain source-present vocatives under the selected story style.
Use natural Vietnamese subject/address ellipsis where roles remain clear. Do not insert tôi into every action line or remove an explicit/emphatic self-reference. Preserve who waits for whom, negation, requests and intentions.
For new terms, translate meaningful compounds in a concise genre-appropriate register. Repeated characters or syllables are not automatically redundant. Add no unexpressed effects or lore.
At the current chapter/page cutoff, exact verified official or reader-locked terms and source-specific alias translations override new style proposals. Never expand every nickname to the canonical full name by blind string replacement.
```

Đây là adapter của app, không phải template chính thức của Hy-MT2. Đánh giá tác động bằng các trường hợp tự soạn trước khi tuyên bố cải thiện chất lượng.

## Trường hợp kiểm tra đề xuất

Các câu Việt minh họa điều kiện chấp nhận, không phải đáp án duy nhất. Chấm riêng ý nghĩa, xưng hô, tên và metadata; schema JSON hợp lệ không đủ.

| Nguồn và ngữ cảnh | Điều kiện cần đạt | Lỗi cần phát hiện |
| --- | --- | --- |
| 姉ちゃん、まだ帰らないの？; chưa biết người nói; giữ cách gọi Nhật | “Nee-chan, chưa về à?”; câu hỏi; speaker vẫn `unknown` | Gán người nói là chị, em trai hoặc một ID chỉ từ 姉ちゃん; biến thành “Tôi chưa về.” |
| お姉さん、これ落としましたよ。; chưa biết quan hệ; chế độ Việt tự nhiên | “Chị ơi, chị đánh rơi cái này.” hoặc câu tương đương; không ghi huyết thống | Ghi vào memory “người nói là em ruột”. |
| 私の姉は医者です。; câu kể | “Chị gái tôi là bác sĩ.” hoặc cách xưng hô có căn cứ | Biến câu kể thành lời gọi “Nee-chan!”. |
| 助けて！; không biết ID người nói/người nghe | “Cứu với!”; giữ lời cầu cứu | Ép chèn một cặp anh–em/ta–ngươi chưa xác nhận. |
| 私がやる。; chưa có khóa xưng hô | “Để tôi làm.” hoặc câu tương đương giữ ý nhận làm | Cấm từ “tôi” toàn cục; mất trọng tâm tự nhận việc. |
| 私を待ってください。; speaker=A, listener=B, A→B đã khóa chị–em | “Em chờ chị nhé.”; B đợi A; giữ yêu cầu | “Chị chờ em nhé.”; đổi thành sự kiện đã hoàn tất. |
| 待ってる。; B nói với A nhưng chỉ có khóa A→B | Lược tự nhiên hoặc xưng hô có bằng chứng khác; không tự áp chiều đảo | Tự tạo B→A chỉ bằng cách đảo hai đại từ trong khóa. |
| 氷結結界を展開する！; chưa khóa; fantasy | Tên đề xuất gọn và chỉ gồm nghĩa được nguồn hỗ trợ; có thể “Triển khai Kết giới băng giá!” | Thêm công năng; tự nhận tên đề xuất là tên chính thức. |
| Cùng nguồn; người đọc khóa 氷結結界→Băng Kết Kết Giới | “Triển khai Băng Kết Kết Giới!” | Xóa một “Kết”, đổi tên vì quy tắc chống lặp hoặc đổi thể loại. |
| Alias đã khóa 氷の壁→Bức Tường Băng; canonical 氷結結界→Băng Kết Kết Giới; nguồn dùng 氷の壁 | Giữ “Bức Tường Băng” trong lần dùng alias | Ép mọi alias thành tên đầy đủ. |
| Tên mới khóa ở chapter 4; dịch lại chapter 2 | Dùng phiên bản tại chapter 2 | Đưa lựa chọn mới/lore tương lai về quá khứ. |

## Khoảng trống còn lại

Chưa xác minh một bản dịch phát hành chính thức của cụm 氷結結界 trong một tựa cụ thể. Chưa có bằng chứng đại diện về sở thích độc giả Việt hay đo chất lượng Hy-MT2 từ nghiên cứu này. Microsoft có danh mục style guide tiếng Việt nhưng liên kết PDF không tải được trong phiên kiểm tra; không dùng nó để gán quy tắc xưng hô cho manga.
