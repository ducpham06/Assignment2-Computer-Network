# HƯỚNG DẪN TOÀN DIỆN TỪ A–Z: ĐÁNH GIÁ THIẾT KẾ, DỰNG LAB EVE-NG, CẤU HÌNH, AUTOMATION & DEMO (TVI ENTERPRISE NETWORK)

> **Phiên bản 2 (12/11/2026):** cập nhật theo bản thiết kế mới chỉ dùng họ image **Cisco vIOS** (đã bỏ Arista vEOS). Cụm Data Center giờ là 4 router vIOS chạy **MPLS L3VPN** và chạy **chung một lab** với phần Campus/WAN. Các mục đã sửa: 1.1, 1.2, 3.2, 4.3, 5, 6.6–6.7, 7.4–7.5, 8 và toàn bộ Phần 9.

Tài liệu này được biên soạn dành riêng cho cấu hình máy ảo của bạn (**17.5 GB RAM, 8 vCPU**, đã tải sẵn 2 image `vios-adventerprisek9-m.SPA.159-3.M6.tgz` và `viosl2-adventerprisek9-m.ssa.high_iron_20200929.tgz`, sử dụng **Python + PyYAML + Netmiko**). Mọi bước từ giải thích kiến trúc, bung file image, tạo thiết bị, cắm từng sợi cáp, cấu hình copy-paste cho từng máy, chạy script tự động hóa cho đến kịch bản thử nghiệm đều được trình bày chi tiết từng bước.

## PHẦN 1: ĐÁNH GIÁ CHI TIẾT BÀI LÀM HIỆN TẠI (DESIGN & CODE AUDIT)

Qua kiểm tra toàn bộ mã nguồn, cấu hình, báo cáo LaTeX (`report/main.pdf`) và chạy bộ kiểm thử tự động `tools/validate.py` trên repo `assignment2-computer-network` bạn gửi, dưới đây là kết quả đánh giá chi tiết:

### 1.1. Kết quả kiểm tra tự động (`validate.py`) — Đạt 18/18 tiêu chí kỹ thuật

Bài làm trong repo được thiết kế bằng phương pháp **Source-of-Truth (`tools/sot.py`)** cực kỳ bài bản. Toàn bộ 18 bài kiểm tra tính nhất quán đều đạt **PASS 100%**:

* **Quy hoạch IP (IPv4 VLSM & IPv6 Dual-Stack):** Phân bổ rõ ràng theo từng khu vực:

  * **TP.HCM (HQ):** `10.10.0.0/16` và `2001:db8:a010::/48`

  * **Hà Nội (R&D):** `10.20.0.0/16` và `2001:db8:a020::/48`

  * **Đà Nẵng (Logistics):** `10.30.0.0/16` và `2001:db8:a030::/48`

  * Không có bất kỳ dải mạng hay địa chỉ IP nào bị trùng lặp; đáp ứng dư sức quy mô mở rộng đến năm 2030.

* **Hạ tầng Layer 2 & Dự phòng Gateway (STP + LACP + HSRPv2):**

  * Giao thức **Rapid-PVST+** được bật trên toàn bộ Switch, có chia tải Root Bridge hợp lý: `HCM-CORE1` làm Root Primary (Priority `24576`) kiêm HSRP Active (Priority `110`) cho các VLAN `10, 12, 40, 80`; `HCM-CORE2` làm Root Primary kiêm HSRP Active cho các VLAN `60, 70, 99`.

  * Đường nối giữa 2 Core Switch tại TP.HCM gom 2 cổng `Gi0/1` và `Gi0/2` thành `Port-channel1` chạy **LACP (`mode active`)**.

  * Các cổng thừa được đưa vào **Blackhole VLAN 999 (`NATIVE_UNUSED`)** và `shutdown` đúng chuẩn bảo mật.

* **Định tuyến Nội vùng (Underlay - OSPFv2 & OSPFv3):**

  * Mỗi chi nhánh chạy một tiến trình OSPF riêng (HCM: `OSPF 10`, Hà Nội: `OSPF 20`, Đà Nẵng: `OSPF 30`), bật `passive-interface default` và chỉ mở OSPF trên các cổng nối điểm-điểm (Point-to-Point).

* **Định tuyến Liên vùng & WAN (Overlay - GRE over IPsec + BGP, không phải DMVPN):**

  * Thiết lập **6 đường hầm GRE bọc bảo mật IPsec IKEv2 (AES-256, SHA-256, DH Group 14)** nối trực tiếp giữa 3 chi nhánh qua 2 nhà mạng độc lập (`ISP-A` trên Plane A và `ISP-B` trên Plane B).

  * Chạy **25 phiên BGP ở phần Campus/WAN (cả IPv4 và IPv6)**, cộng thêm 4 phiên VPNv4 trong Data Center (tổng 29), có tổng hợp tuyến (Route Summarization `/16` và `/48`) tại biên và quảng bá Default Route cho phép các chi nhánh truy cập Internet trực tiếp (**Direct Cloud Access / Local Internet Breakout** qua NAT Overload) mà không cần vòng về HQ.

* **Bảo mật, QoS & Dịch vụ mạng:**

  * Đầy đủ **DHCP Server tập trung** tại `HCM-SRV1` (`10.10.43.10`) kèm `ip helper-address` trên mọi Gateway; **DHCP Snooping, Dynamic ARP Inspection (DAI), Port-Security** trên các cổng Access; **Zone-Based Firewall (ZBF)** tại biên WAN; **ACL** cô lập mạng Guest, IoT và bảo vệ VLAN Ban Giám Đốc (`VLAN 10`).

  * Chính sách **QoS LLQ (Low Latency Queuing)** đánh dấu gói tin thoại VoIP (`DSCP EF` - ưu tiên 30% băng thông) kèm bộ phát lưu lượng kiểm thử **IP SLA UDP-Jitter**.

* **Data Center (vIOS, MPLS L3VPN):** 2 Spine + 2 Leaf, underlay OSPF + LDP, overlay MP-BGP VPNv4 (2 Spine làm Route Reflector), 2 tenant `TENANT-PROD` và `TENANT-DEV` cách ly bằng VRF/route-target; mỗi Leaf nối xuống 1 Core HCM qua cổng biên `Gi0/5`.

* **Code Automation (`automation/tvi_auto.py`):**

  * Viết bằng **Python + PyYAML + Netmiko** đúng yêu cầu của bạn, tách biệt hoàn toàn danh sách thiết bị ra `inventory.yaml`, tuyệt đối không lưu mật khẩu cứng trong code (dùng biến môi trường hoặc `getpass`), có tự động sao lưu cấu hình vào `backups/`, ghi nhật ký vào `logs/automation.log`, so sánh khác biệt (`diff`) và kiểm tra tuân thủ (`verify`).

### 1.2. Ba điểm bạn CẦN LƯU Ý & XỬ LÝ để đạt điểm tối đa với cấu hình máy ảo 17.5 GB RAM

| Vấn đề phát hiện | Nguyên nhân | Cách giải quyết triệt để (đã tích hợp trong hướng dẫn này) | 
| ----- | ----- | ----- | 
| **1. RAM 17.5 GB và cụm Data Center** | Bản cũ dùng 4 node Arista vEOS (2 GB/node) nên phải tách thành Lab A và Lab B. Bản mới thay bằng 4 router **vIOS** (512 MB/node), nên toàn bộ 18 thiết bị Cisco chỉ tốn khoảng **11.5 GB RAM** (9 vIOS router × 512 MB + 5 vIOS-L2 × 1024 MB + 4 vIOS DC × 512 MB). | **Chạy toàn bộ trong MỘT lab:** với 17.5 GB RAM và 8 vCPU vẫn dư khoảng 4–5 GB cho EVE-NG. Không cần image Arista, không cần cờ `--lab A` khi chạy script Python. Vẫn phải khởi động theo đợt (Phần 5) vì 8 vCPU sẽ quá tải nếu bật cùng lúc. | 
| **2. Cách bung 2 file `.tgz` của bạn vào EVE-NG** | Hướng dẫn của môn ghi bản `.vmdk` cũ (`152-4.M3`), trong khi bạn đang có 2 bản nén `.tgz` mới hơn: `vios-adventerprisek9-m.SPA.159-3.M6.tgz` và `viosl2-adventerprisek9-m.ssa.high_iron_20200929.tgz`. | Các file `.tgz` này thực chất đã được đóng gói sẵn thư mục chuẩn cho EVE-NG! Bạn **không cần đổi tên thủ công từ vmdk**, chỉ cần dùng lệnh `tar -xzf` giải nén trực tiếp vào `/opt/unetlab/addons/qemu/` theo đúng các câu lệnh ở **Phần 3** bên dưới. | 
| **3. Các ô màu vàng `[Evidence]` trong file báo cáo `report/main.pdf`** | Trong file `report/main.pdf` (Mục 7.2 Evidence, 17 khung E1–E17), tác giả để sẵn các khung màu vàng ghi: *"\[Paste the real CLI output or a cropped screenshot captured in the EVE-NG lab here\]"*. Nếu nộp luôn file PDF hiện tại mà chưa dán ảnh/kết quả chạy lab thực tế vào thì sẽ bị trừ điểm phần kiểm thử (15%). | Sau khi dựng xong Lab A theo hướng dẫn dưới đây và gõ các lệnh ở **Phần 8**, bạn chỉ cần copy kết quả trên màn hình (hoặc chụp ảnh màn hình) dán vào `report/main.tex` rồi biên dịch lại PDF (hoặc chèn vào báo cáo). | 

## PHẦN 2: GIẢI THÍCH BỨC TRANH TỔNG THỂ (ĐỂ BẠN HIỂU RÕ MÌNH ĐANG LÀM GÌ)

Nếu đọc tài liệu tiếng Anh thấy quá nhiều thuật ngữ, bạn chỉ cần hình dung hệ thống mạng của công ty **TechViet Innovations (TVI)** giống như hệ thống giao thông của 3 tòa nhà tại 3 miền đất nước:

1. **Ba Chi Nhánh (3 Sites):**

   * **Trụ sở chính TP.HCM (`HCM`):** Tòa nhà lớn nhất nên có đầy đủ 3 tầng thiết bị:

     * **Tầng Access (`HCM-ACC1` - Switch L2):** Nơi cắm dây trực tiếp vào máy tính nhân viên (`PC-HCM-CORP`), máy Giám đốc (`PC-HCM-EXEC`), điện thoại bàn (`PC-HCM-PHONE`), khách (`PC-HCM-GUEST`) và máy chủ trung tâm (`HCM-SRV1`).

     * **Tầng Core (`HCM-CORE1` & `HCM-CORE2` - Switch L3):** Hai bộ não xử lý trung tâm của tòa nhà TP.HCM. Dùng 2 con chạy song song (**HSRP**) để nếu `CORE1` cháy/tắt nguồn, `CORE2` lập tức thay thế trong tích tắc mà nhân viên không bị rớt mạng.

     * **Tầng Biên WAN (`HCM-EDG1` & `HCM-EDG2` - Router):** Hai cổng gác bảo vệ nối tòa nhà TP.HCM ra ngoài Internet.

   * **Chi nhánh Hà Nội (`HAN`):** Quy mô vừa nên gộp tầng Core và Biên làm một (`HAN-EDG1` & `HAN-EDG2` vừa làm cổng ra Internet, vừa làm Gateway HSRP cho mạng nội bộ), phía dưới có 1 Switch cắm máy nhân viên (`HAN-ACC1`).

   * **Chi nhánh Đà Nẵng (`DAD`):** Tương tự Hà Nội, gồm 2 Router biên (`DAD-EDG1` & `DAD-EDG2`) và 1 Switch nội bộ (`DAD-ACC1`).

2. **Hai Nhà Mạng Internet (`ISP-A` và `ISP-B`):**

   * Giống như Viettel và VNPT ngoài đời. Mỗi chi nhánh đều thuê 2 đường truyền: Router số `1` (`HCM-EDG1`, `HAN-EDG1`, `DAD-EDG1`) cắm vào `ISP-A`; Router số `2` (`HCM-EDG2`, `HAN-EDG2`, `DAD-EDG2`) cắm vào `ISP-B`. Nếu đứt cáp nhà mạng A, toàn bộ lưu lượng tự động nhảy sang nhà mạng B.

3. **Đường hầm bảo mật xuyên Việt (GRE over IPsec + BGP):**

   * Vì dữ liệu đi qua mạng công cộng của ISP, các Router biên tự động tạo các "đường ống ngầm" mã hóa (**Tunnel 11, 12, 13, 21, 22, 23**) nối thẳng HCM ↔ Hà Nội, HCM ↔ Đà Nẵng, và Hà Nội ↔ Đà Nẵng.

4. **Trung tâm dữ liệu (Data Center) tại HCM:** 4 router `DC-SPINE1/2` và `DC-LEAF1/2` tạo thành mạng Spine-Leaf. Mỗi "khách thuê" (tenant) có một VRF riêng như một căn phòng có khóa: máy chủ `TENANT-PROD` nói chuyện được với nhau và với văn phòng, còn `TENANT-DEV` bị cách ly hoàn toàn.

5. **Mạng Quản Trị Riêng (`Cloud0` - `172.16.99.0/24`):**

   * Để bạn ngồi từ máy chủ EVE-NG chạy lệnh Python (`tvi_auto.py`) điều khiển toàn bộ 18 thiết bị cùng lúc qua SSH, cổng đầu tiên (`Gi0/0`) của tất cả 18 thiết bị đều được cắm chung vào một đám mây tên là `Management(Cloud0)`.

## PHẦN 3: CÀI ĐẶT 2 FILE IMAGE `.tgz` VÀO MÁY ẢO EVE-NG

Bạn đã tải sẵn 2 file:

* `vios-adventerprisek9-m.SPA.159-3.M6.tgz` (Dùng làm **Router** / Server)

* `viosl2-adventerprisek9-m.ssa.high_iron_20200929.tgz` (Dùng làm **Switch Layer 2 / Layer 3**)

Hãy làm chính xác từng bước sau để đưa 2 file này vào EVE-NG:

### Bước 3.1: Upload 2 file `.tgz` và thư mục bài làm lên EVE-NG

1. Bật máy ảo EVE-NG trên VMware/Proxmox. Trên màn hình đen của EVE-NG, bạn sẽ thấy địa chỉ IP của nó (ví dụ: `192.168.x.x`).

2. Mở phần mềm **WinSCP** hoặc **FileZilla** (hoặc dùng lệnh `scp` trên Terminal máy thật), đăng nhập vào EVE-NG với:

   * **Host:** `<IP_CỦA_EVE_NG>`

   * **Username:** `root`

   * **Password:** `eve`

   * **Port:** `22` (SFTP)

3. Kéo thả 2 file `vios-adventerprisek9-m.SPA.159-3.M6.tgz` và `viosl2-adventerprisek9-m.ssa.high_iron_20200929.tgz` vào thư mục `/root/` trên máy ảo EVE-NG.

4. Đồng thời, kéo thả luôn thư mục bài làm (hoặc file zip bài làm) vào `/root/tvi-project` để lát nữa chạy script Python ngay trên EVE-NG.

### Bước 3.2: Giải nén Image đúng chuẩn EVE-NG và cấp quyền

Mở **SSH** (bằng PuTTY, MobaXterm hoặc Terminal trên Windows/Mac: `ssh root@<IP_CỦA_EVE_NG>`, mật khẩu `eve`), sau đó **copy và dán nguyên khối lệnh dưới đây** vào cửa sổ lệnh của EVE-NG:

```
# 1. Giải nén 2 file .tgz trực tiếp vào thư mục qemu của EVE-NG
tar -xzvf /root/vios-adventerprisek9-m.SPA.159-3.M6.tgz -C /opt/unetlab/addons/qemu/
tar -xzvf /root/viosl2-adventerprisek9-m.ssa.high_iron_20200929.tgz -C /opt/unetlab/addons/qemu/

# 2. Kiểm tra xem thư mục đã tạo đúng tên chuẩn (vios-... và viosl2-...) và file bên trong là virtioa.qcow2 chưa
for dir in /opt/unetlab/addons/qemu/vios*; do
    echo "Kiểm tra thư mục: $dir"
    ls -la "$dir"
    # Nếu bên trong file có tên là hda.qcow2 thì tự động đổi sang virtioa.qcow2 cho chuẩn template
    if [ -f "$dir/hda.qcow2" ] && [ ! -f "$dir/virtioa.qcow2" ]; then
        mv "$dir/hda.qcow2" "$dir/virtioa.qcow2"
        echo " -> Đã tự động đổi tên hda.qcow2 thành virtioa.qcow2"
    fi
done

# 3. Chạy lệnh Fix Permissions (BẮT BUỘC trong EVE-NG, nếu quên bấm Start node sẽ bị tắt ngay)
/opt/unetlab/wrappers/unl_wrapper -a fixpermissions

```

### Bước 3.3: Gán IP quản trị `172.16.99.1` cho máy ảo EVE-NG

Máy ảo EVE-NG là nơi chạy script Python, nên nó cần một địa chỉ trong mạng quản trị `172.16.99.0/24` (mạng mà cổng `Gi0/0` của mọi thiết bị cắm vào):

```
ip addr add 172.16.99.1/24 dev pnet0
ip link set pnet0 up
```

Để không phải gõ lại mỗi lần khởi động, mở `/etc/network/interfaces`, tìm khối `iface pnet0` và thêm một dòng thụt lề: `post-up ip addr add 172.16.99.1/24 dev pnet0`.

*(Mẹo: Nếu bạn tắt máy ảo EVE-NG bật lại vào hôm sau, chỉ cần chạy lại dòng `ip addr add 172.16.99.1/24 dev pnet0` này trước khi chạy code Python).*

## PHẦN 4: HƯỚNG DẪN TẠO LAB, CHỌN THIẾT BỊ VÀ NỐI DÂY TỪNG CỔNG TRÊN WEB EVE-NG

Bây giờ, bạn mở trình duyệt web (Chrome/Edge/Firefox) trên máy tính thật, truy cập vào địa chỉ `http://<IP_CỦA_EVE_NG>`:

* **Username:** `admin`

* **Password:** `eve`

* **Console:** Chọn **Native console** (nếu máy bạn đã cài EVE-NG Client Pack) hoặc chọn **HTML5 console** (để bấm vào thiết bị là mở cửa sổ dòng lệnh ngay trên trình duyệt web cực tiện, không cần cài thêm phần mềm).

### Bước 4.1: Tạo bài Lab mới

1. Trên giao diện EVE-NG, bấm nút biểu tượng **Add new lab** (hình tờ giấy có dấu `+` ở góc trên bên trái).

2. Điền **Name:** `TVI_Enterprise_Network` → Bấm **Save**. Một bảng trắng (Canvas) sẽ hiện ra.

### Bước 4.2: Tạo Đám mây Quản trị (`Cloud0`)

1. **Click chuột phải** vào vùng trắng trên màn hình → Chọn **Network**.

2. Điền các thông số:

   * **Name/Prefix:** `OOB-MGMT`

   * **Type:** Chọn **`Management(Cloud0)`** (Mặc định chính là nó).

3. Bấm **Save**. Kéo đám mây `OOB-MGMT` này để ở góc trên hoặc chính giữa sơ đồ.

### Bước 4.3: Tạo toàn bộ Thiết bị (Nodes) — Chọn đúng loại và đúng số cổng!

Để không phải tạo từng con một lâu la, bạn làm theo **4 đợt tạo hàng loạt** dưới đây (chú ý thông số **Ethernet** rất quan trọng để có đủ cổng cắm dây):

#### Đợt 1: Tạo 9 Router/Server dùng image `vios`

1. **Click chuột phải** vào bảng trắng → Chọn **Node** → Gõ tìm và chọn **`Cisco vIOS Router`**.

2. Chỉnh chính xác các ô sau:

   * **Number of nodes to add:** `8`

   * **Image:** `vios-adventerprisek9-m.SPA.159-3.M6`

   * **RAM:** `512` (MB)

   * **Ethernet:** Đổi từ `4` thành **`6`** *(BẮT BUỘC đổi thành 6 để có từ cổng `Gi0/0` đến `Gi0/5`)*

3. Bấm **Save**. Sau khi 8 cục Router hiện ra, bạn **click chuột phải vào từng cục → chọn Edit** để đổi tên (**Name**) lần lượt cho 8 cục thành:

   1. `ISP-A`

   2. `ISP-B`

   3. `HCM-EDG1`

   4. `HCM-EDG2`

   5. `HCM-SRV1`

   6. `HAN-EDG1`

   7. `HAN-EDG2`

   8. `DAD-EDG1`
      *(Tạo thêm 1 cục `Cisco vIOS Router` nữa với thông số y hệt: RAM `512`, Ethernet `6` và đặt tên là **`DAD-EDG2`**. Như vậy cụm Campus/WAN có **9 cục vIOS Router**; 4 router Data Center tạo ở Phần 9).*

#### Đợt 2: Tạo 5 Switch dùng image `viosl2`

1. **Click chuột phải** vào bảng trắng → Chọn **Node** → Gõ tìm và chọn **`Cisco vIOS Switch`**.

2. Chỉnh chính xác các ô sau:

   * **Number of nodes to add:** `5`

   * **Image:** `viosl2-adventerprisek9-m.ssa.high_iron_20200929`

   * **RAM:** **`1024`** (MB) *(KHÔNG để 768: hướng dẫn của môn ghi vIOS-L2 dưới 1024 MB có thể treo khi khởi động)*

   * **Ethernet (groups of 4):** Để nguyên là **`4`** *(tương đương 16 cổng từ `Gi0/0` đến `Gi3/3`)*

3. Bấm **Save**. Sau đó **click chuột phải vào từng cục Switch → chọn Edit** để đổi tên lần lượt cho 5 cục thành:

   1. `HCM-CORE1`

   2. `HCM-CORE2`

   3. `HCM-ACC1`

   4. `HAN-ACC1`

   5. `DAD-ACC1`

#### Đợt 3: Tạo 11 Máy tính người dùng ảo (`Virtual PC - VPCS`)

1. **Click chuột phải** vào bảng trắng → Chọn **Node** → Gõ tìm và chọn **`Virtual PC (VPCS)`**.

2. Chỉnh **Number of nodes to add:** `11` → Bấm **Save**.

3. **Click chuột phải vào từng PC → chọn Edit** để đổi tên lần lượt thành:

   * Cụm TP.HCM (4 máy): `PC-HCM-EXEC`, `PC-HCM-CORP`, `PC-HCM-GUEST`, `PC-HCM-PHONE`

   * Cụm Hà Nội (3 máy): `PC-HAN-ENG`, `PC-HAN-PHONE`, `PC-HAN-GUEST`

   * Cụm Đà Nẵng (4 máy): `PC-DAD-LOG`, `PC-DAD-IOT`, `PC-DAD-PHONE`, `PC-DAD-GUEST`

*(Mẹo sắp xếp trên màn hình để dễ nhìn và nối dây không bị rối: Xếp `ISP-A` và `ISP-B` ở hàng trên cùng; chia màn hình làm 3 cột: cột trái là cụm `HCM-*`, cột giữa là cụm `HAN-*`, cột phải là cụm `DAD-*`, hàng dưới cùng là các máy `PC-*`).*

### Bước 4.4: BẢNG NỐI DÂY CHI TIẾT TỪNG CỔNG (CABLING GUIDE)

Cách nối dây trong EVE-NG: Di chuột vào thiết bị thứ nhất, thấy hiện ra **biểu tượng cái phích cắm màu cam** → giữ chuột trái kéo sang thiết bị thứ hai rồi thả ra → một hộp thoại hiện lên cho bạn chọn **Cổng nguồn (Source Port)** và **Cổng đích (Destination Port)** → bấm **Save**.

> **QUY TẮC SỐNG CÒN:** Bạn phải chọn **chính xác 100% tên cổng** như các bảng dưới đây, bởi vì trong các file cấu hình đã viết sẵn lệnh cho đúng từng cổng đó!

#### Bảng A: Nối dây Quản trị (Management) vào đám mây `OOB-MGMT` (`Cloud0`)

Hãy kéo dây từ cổng **`Gi0/0`** của tất cả **14 thiết bị Cisco Campus/WAN** dưới đây (và 4 router Data Center ở Bảng F, Phần 9) cắm vào đám mây **`OOB-MGMT`**:

| STT | Từ Thiết Bị | Cổng (Port) | Cắm vào | Mục đích & IP Quản trị (đã cấu hình sẵn trong file) | 
| ----- | ----- | ----- | ----- | ----- | 
| M1 | `ISP-A` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.101/24`) | 
| M2 | `ISP-B` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.102/24`) | 
| M3 | `HCM-EDG1` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.11/24`) | 
| M4 | `HCM-EDG2` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.12/24`) | 
| M5 | `HCM-CORE1` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.13/24`) | 
| M6 | `HCM-CORE2` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.14/24`) | 
| M7 | `HCM-ACC1` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.15/24`) | 
| M8 | `HCM-SRV1` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.16/24`) | 
| M9 | `HAN-EDG1` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.21/24`) | 
| M10 | `HAN-EDG2` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.22/24`) | 
| M11 | `HAN-ACC1` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.25/24`) | 
| M12 | `DAD-EDG1` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.31/24`) | 
| M13 | `DAD-EDG2` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.32/24`) | 
| M14 | `DAD-ACC1` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | Quản trị SSH (`172.16.99.35/24`) | 

#### Bảng B: Nối dây cụm Nhà mạng WAN (`ISP-A` và `ISP-B`) — 7 sợi cáp

| STT | Thiết bị 1 | Cổng Thiết bị 1 | Nối sang Thiết bị 2 | Cổng Thiết bị 2 | Giải thích kết nối | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| 1 | **`ISP-A`** | **`Gi0/1`** | **`HCM-EDG1`** | **`Gi0/1`** | Đường truyền WAN A của Trụ sở HCM (`203.0.113.0/30`) | 
| 2 | **`ISP-A`** | **`Gi0/2`** | **`HAN-EDG1`** | **`Gi0/1`** | Đường truyền WAN A của Chi nhánh Hà Nội (`203.0.113.4/30`) | 
| 3 | **`ISP-A`** | **`Gi0/3`** | **`DAD-EDG1`** | **`Gi0/1`** | Đường truyền WAN A của Chi nhánh Đà Nẵng (`203.0.113.8/30`) | 
| 4 | **`ISP-B`** | **`Gi0/1`** | **`HCM-EDG2`** | **`Gi0/1`** | Đường truyền WAN B của Trụ sở HCM (`198.51.100.0/30`) | 
| 5 | **`ISP-B`** | **`Gi0/2`** | **`HAN-EDG2`** | **`Gi0/1`** | Đường truyền WAN B của Chi nhánh Hà Nội (`198.51.100.4/30`) | 
| 6 | **`ISP-B`** | **`Gi0/3`** | **`DAD-EDG2`** | **`Gi0/1`** | Đường truyền WAN B của Chi nhánh Đà Nẵng (`198.51.100.8/30`) | 
| 7 | **`ISP-A`** | **`Gi0/4`** | **`ISP-B`** | **`Gi0/4`** | Liên kết eBGP giữa 2 nhà mạng (`203.0.113.248/30`) | 

#### Bảng C: Nối dây nội bộ Trụ sở chính TP.HCM (`HCM`) — 14 sợi cáp

| STT | Thiết bị 1 | Cổng Thiết bị 1 | Nối sang Thiết bị 2 | Cổng Thiết bị 2 | Giải thích kết nối | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| 8 | **`HCM-EDG1`** | **`Gi0/2`** | **`HCM-CORE1`** | **`Gi1/0`** | Liên kết L3 OSPF từ Edge 1 xuống Core 1 (`10.10.254.0/30`) | 
| 9 | **`HCM-EDG1`** | **`Gi0/3`** | **`HCM-CORE2`** | **`Gi1/0`** | Liên kết L3 OSPF từ Edge 1 xuống Core 2 (`10.10.254.4/30`) | 
| 10 | **`HCM-EDG2`** | **`Gi0/2`** | **`HCM-CORE1`** | **`Gi1/1`** | Liên kết L3 OSPF từ Edge 2 xuống Core 1 (`10.10.254.8/30`) | 
| 11 | **`HCM-EDG2`** | **`Gi0/3`** | **`HCM-CORE2`** | **`Gi1/1`** | Liên kết L3 OSPF từ Edge 2 xuống Core 2 (`10.10.254.12/30`) | 
| 12 | **`HCM-EDG1`** | **`Gi0/4`** | **`HCM-EDG2`** | **`Gi0/4`** | Liên kết iBGP/OSPF trực tiếp giữa 2 Edge (`10.10.254.16/30`) | 
| 15 | **`HCM-CORE1`** | **`Gi0/1`** | **`HCM-CORE2`** | **`Gi0/1`** | Sợi cáp số 1 của bó cáp LACP `Port-channel1` giữa 2 Core | 
| 16 | **`HCM-CORE1`** | **`Gi0/2`** | **`HCM-CORE2`** | **`Gi0/2`** | Sợi cáp số 2 của bó cáp LACP `Port-channel1` giữa 2 Core | 
| 17 | **`HCM-CORE1`** | **`Gi0/3`** | **`HCM-ACC1`** | **`Gi0/1`** | Đường Trunk 802.1Q từ Core 1 xuống Switch Access | 
| 18 | **`HCM-CORE2`** | **`Gi0/3`** | **`HCM-ACC1`** | **`Gi0/2`** | Đường Trunk 802.1Q dự phòng từ Core 2 xuống Switch Access | 
| 23 | **`HCM-ACC1`** | **`Gi1/0`** | **`PC-HCM-EXEC`** | **`eth0`** | Cổng Access VLAN 10 (Ban Giám Đốc & Tài Chính) | 
| 24 | **`HCM-ACC1`** | **`Gi1/1`** | **`PC-HCM-CORP`** | **`eth0`** | Cổng Access VLAN 12 (Nhân viên văn phòng) | 
| 25 | **`HCM-ACC1`** | **`Gi1/2`** | **`PC-HCM-GUEST`** | **`eth0`** | Cổng Access VLAN 60 (Mạng Khách - chỉ đi Internet) | 
| 26 | **`HCM-ACC1`** | **`Gi1/3`** | **`PC-HCM-PHONE`** | **`eth0`** | Cổng Access VLAN 40 (Điện thoại IP VoIP) | 
| 27 | **`HCM-ACC1`** | **`Gi2/0`** | **`HCM-SRV1`** | **`Gi0/1`** | Cổng Access VLAN 80 (Máy chủ DHCP, DNS, IP SLA) | 

#### Bảng D: Nối dây nội bộ Chi nhánh Hà Nội (`HAN`) — 6 sợi cáp

| STT | Thiết bị 1 | Cổng Thiết bị 1 | Nối sang Thiết bị 2 | Cổng Thiết bị 2 | Giải thích kết nối | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| 13 | **`HAN-EDG1`** | **`Gi0/3`** | **`HAN-EDG2`** | **`Gi0/3`** | Liên kết L3 OSPF/iBGP giữa 2 Router biên Hà Nội (`10.20.254.0/30`) | 
| 19 | **`HAN-EDG1`** | **`Gi0/2`** | **`HAN-ACC1`** | **`Gi0/1`** | Đường Trunk 802.1Q (Router-on-a-Stick) xuống Switch Hà Nội | 
| 20 | **`HAN-EDG2`** | **`Gi0/2`** | **`HAN-ACC1`** | **`Gi0/2`** | Đường Trunk 802.1Q dự phòng từ Edge 2 xuống Switch Hà Nội | 
| 28 | **`HAN-ACC1`** | **`Gi1/0`** | **`PC-HAN-ENG`** | **`eth0`** | Cổng Access VLAN 20 (Kỹ sư R&D & AI Lab) | 
| 29 | **`HAN-ACC1`** | **`Gi1/1`** | **`PC-HAN-PHONE`** | **`eth0`** | Cổng Access VLAN 40 (Điện thoại IP VoIP Hà Nội) | 
| 30 | **`HAN-ACC1`** | **`Gi1/2`** | **`PC-HAN-GUEST`** | **`eth0`** | Cổng Access VLAN 60 (Mạng Khách Hà Nội) | 

#### Bảng E: Nối dây nội bộ Chi nhánh Đà Nẵng (`DAD`) — 7 sợi cáp

| STT | Thiết bị 1 | Cổng Thiết bị 1 | Nối sang Thiết bị 2 | Cổng Thiết bị 2 | Giải thích kết nối | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| 14 | **`DAD-EDG1`** | **`Gi0/3`** | **`DAD-EDG2`** | **`Gi0/3`** | Liên kết L3 OSPF/iBGP giữa 2 Router biên Đà Nẵng (`10.30.254.0/30`) | 
| 21 | **`DAD-EDG1`** | **`Gi0/2`** | **`DAD-ACC1`** | **`Gi0/1`** | Đường Trunk 802.1Q xuống Switch Đà Nẵng | 
| 22 | **`DAD-EDG2`** | **`Gi0/2`** | **`DAD-ACC1`** | **`Gi0/2`** | Đường Trunk 802.1Q dự phòng xuống Switch Đà Nẵng | 
| 31 | **`DAD-ACC1`** | **`Gi1/0`** | **`PC-DAD-LOG`** | **`eth0`** | Cổng Access VLAN 30 (Vận hành Kho vận Logistics) | 
| 32 | **`DAD-ACC1`** | **`Gi1/1`** | **`PC-DAD-IOT`** | **`eth0`** | Cổng Access VLAN 50 (Thiết bị cảm biến/xe tự hành IoT) | 
| 33 | **`DAD-ACC1`** | **`Gi1/2`** | **`PC-DAD-PHONE`** | **`eth0`** | Cổng Access VLAN 40 (Điện thoại IP VoIP Đà Nẵng) | 
| 34 | **`DAD-ACC1`** | **`Gi1/3`** | **`PC-DAD-GUEST`** | **`eth0`** | Cổng Access VLAN 60 (Mạng Khách Đà Nẵng) | 

## PHẦN 5: QUY TRÌNH KHỞI ĐỘNG (START NODES) ĐỂ KHÔNG BỊ TREO MÁY 8 vCPU

Với 8 vCPU và 17.5 GB RAM, nếu bạn bấm "Start all nodes" cùng một lúc, cả 18 máy ảo Cisco sẽ đồng thời bung nhân Linux và ngốn 100% CPU gây treo boot. Hãy khởi động theo **5 đợt**, đợi mỗi đợt boot xong rồi mới bật đợt sau:

1. **Đợt 1 (Nhà mạng & Máy chủ):** Quét chuột chọn `ISP-A`, `ISP-B`, `HCM-SRV1` → Click chuột phải → **Start**. Đợi **45 giây**.

2. **Đợt 2 (6 Router Biên WAN):** Quét chuột chọn `HCM-EDG1`, `HCM-EDG2`, `HAN-EDG1`, `HAN-EDG2`, `DAD-EDG1`, `DAD-EDG2` → Click chuột phải → **Start**. Đợi **60 giây**.

3. **Đợt 3 (5 Switch Core & Access):** Quét chuột chọn `HCM-CORE1`, `HCM-CORE2`, `HCM-ACC1`, `HAN-ACC1`, `DAD-ACC1` → Click chuột phải → **Start**. Đợi **60 giây**.

4. **Đợt 4 (4 router Data Center):** `DC-SPINE1`, `DC-SPINE2`, `DC-LEAF1`, `DC-LEAF2` → **Start**. Đợi **60 giây**.

5. **Đợt 5 (15 Máy tính VPCS):** Quét chuột chọn toàn bộ 11 máy `PC-*` và 4 máy `DC-H*` → Click chuột phải → **Start** (VPCS khởi động tức thì trong 1 giây).

## PHẦN 6: TOÀN BỘ LỆNH CẤU HÌNH COPY-PASTE CHO TỪNG THIẾT BỊ

### Quy tắc dán lệnh vào Console của Router/Switch Cisco:

1. Click chuột trái vào thiết bị trên EVE-NG để mở cửa sổ Console.

2. Khi thiết bị khởi động xong, nếu nó hỏi:
   `Would you like to enter the initial configuration dialog? [yes/no]:`
   → Bạn gõ **`no`** rồi bấm **Enter**.

3. Bấm **Enter** vài lần để hiện dấu nhắc `Router>` hoặc `Switch>`, sau đó gõ 2 lệnh sau để vào chế độ cấu hình:

   ```
   enable
   configure terminal
   
   ```

4. **Copy khối lệnh** của thiết bị tương ứng bên dưới và **dán từng đoạn khoảng 40 dòng** vào cửa sổ Console (console của EVE-NG hay rơi ký tự khi dán một khối quá dài; dán xong một đoạn, đợi dấu nhắc hiện lại rồi mới dán đoạn tiếp). Nếu có dòng nào báo `% Invalid input` thì chụp lại gửi người giữ file nguồn để sửa trong `tools/sot.py`, không tự sửa tay.
   *(Lưu ý: Dòng lệnh `crypto key generate rsa modulus 2048` sẽ mất khoảng 2–3 giây để sinh khóa mã hóa SSH, các lệnh phía sau sẽ tự động chạy tiếp cho đến chữ `end`).*

5. Sau khi dán xong, gõ lệnh lưu cấu hình để tắt máy bật lại không bị mất:

   ```
   write memory
   
   ```

### 6.1. Thiết bị `ISP-A` — Nhà mạng WAN A (Cisco vIOS Router)

Mở Console của **`ISP-A`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- ISP-A
! Platform: vios   Role: isp   Site: WAN
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname ISP-A
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
interface Loopback0
 ip address 203.0.113.254 255.255.255.255
!
interface Loopback1
 description Public SaaS / cloud application
 ip address 192.0.2.10 255.255.255.255
!
interface Loopback2
 description Public DNS resolver
 ip address 192.0.2.53 255.255.255.255
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.101 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet0/1
 description Customer TVI HCM-EDG1 Gi0/1
 ip address 203.0.113.1 255.255.255.252
 no shutdown
!
interface GigabitEthernet0/2
 description Customer TVI HAN-EDG1 Gi0/1
 ip address 203.0.113.5 255.255.255.252
 no shutdown
!
interface GigabitEthernet0/3
 description Customer TVI DAD-EDG1 Gi0/1
 ip address 203.0.113.9 255.255.255.252
 no shutdown
!
interface GigabitEthernet0/4
 description Peering -> ISP-B
 ip address 203.0.113.249 255.255.255.252
 no shutdown
!
ip route 203.0.113.0 255.255.255.0 Null0
ip route 192.0.2.0 255.255.255.0 Null0
!
ip prefix-list PL-DEFAULT-ONLY seq 5 permit 0.0.0.0/0
ip prefix-list PL-DENY-ALL seq 5 deny 0.0.0.0/0 le 32
!
router bgp 65100
 bgp router-id 203.0.113.254
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 neighbor 203.0.113.2 remote-as 65010
 neighbor 203.0.113.2 description Customer TVI HCM-EDG1
 neighbor 203.0.113.6 remote-as 65020
 neighbor 203.0.113.6 description Customer TVI HAN-EDG1
 neighbor 203.0.113.10 remote-as 65030
 neighbor 203.0.113.10 description Customer TVI DAD-EDG1
 neighbor 203.0.113.250 remote-as 65200
 neighbor 203.0.113.250 description Peering ISP-B
 !
 address-family ipv4
  network 203.0.113.0 mask 255.255.255.0
  network 192.0.2.0 mask 255.255.255.0
  neighbor 203.0.113.2 activate
  neighbor 203.0.113.2 default-originate
  neighbor 203.0.113.2 prefix-list PL-DENY-ALL in
  neighbor 203.0.113.2 prefix-list PL-DEFAULT-ONLY out
  neighbor 203.0.113.6 activate
  neighbor 203.0.113.6 default-originate
  neighbor 203.0.113.6 prefix-list PL-DENY-ALL in
  neighbor 203.0.113.6 prefix-list PL-DEFAULT-ONLY out
  neighbor 203.0.113.10 activate
  neighbor 203.0.113.10 default-originate
  neighbor 203.0.113.10 prefix-list PL-DENY-ALL in
  neighbor 203.0.113.10 prefix-list PL-DEFAULT-ONLY out
  neighbor 203.0.113.250 activate
 exit-address-family
!
ip dns server
ip host saas.cloud.example 192.0.2.10
ip host www.example.com 192.0.2.10
ip host cloud-b.example 198.51.100.200
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.2. Thiết bị `ISP-B` — Nhà mạng WAN B (Cisco vIOS Router)

Mở Console của **`ISP-B`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- ISP-B
! Platform: vios   Role: isp   Site: WAN
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname ISP-B
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
interface Loopback0
 ip address 198.51.100.254 255.255.255.255
!
interface Loopback1
 description Public cloud target B
 ip address 198.51.100.200 255.255.255.255
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.102 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet0/1
 description Customer TVI HCM-EDG2 Gi0/1
 ip address 198.51.100.1 255.255.255.252
 no shutdown
!
interface GigabitEthernet0/2
 description Customer TVI HAN-EDG2 Gi0/1
 ip address 198.51.100.5 255.255.255.252
 no shutdown
!
interface GigabitEthernet0/3
 description Customer TVI DAD-EDG2 Gi0/1
 ip address 198.51.100.9 255.255.255.252
 no shutdown
!
interface GigabitEthernet0/4
 description Peering -> ISP-A
 ip address 203.0.113.250 255.255.255.252
 no shutdown
!
ip route 198.51.100.0 255.255.255.0 Null0
!
ip prefix-list PL-DEFAULT-ONLY seq 5 permit 0.0.0.0/0
ip prefix-list PL-DENY-ALL seq 5 deny 0.0.0.0/0 le 32
!
router bgp 65200
 bgp router-id 198.51.100.254
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 neighbor 198.51.100.2 remote-as 65010
 neighbor 198.51.100.2 description Customer TVI HCM-EDG2
 neighbor 198.51.100.6 remote-as 65020
 neighbor 198.51.100.6 description Customer TVI HAN-EDG2
 neighbor 198.51.100.10 remote-as 65030
 neighbor 198.51.100.10 description Customer TVI DAD-EDG2
 neighbor 203.0.113.249 remote-as 65100
 neighbor 203.0.113.249 description Peering ISP-A
 !
 address-family ipv4
  network 198.51.100.0 mask 255.255.255.0
  network 198.51.100.200 mask 255.255.255.255
  neighbor 198.51.100.2 activate
  neighbor 198.51.100.2 default-originate
  neighbor 198.51.100.2 prefix-list PL-DENY-ALL in
  neighbor 198.51.100.2 prefix-list PL-DEFAULT-ONLY out
  neighbor 198.51.100.6 activate
  neighbor 198.51.100.6 default-originate
  neighbor 198.51.100.6 prefix-list PL-DENY-ALL in
  neighbor 198.51.100.6 prefix-list PL-DEFAULT-ONLY out
  neighbor 198.51.100.10 activate
  neighbor 198.51.100.10 default-originate
  neighbor 198.51.100.10 prefix-list PL-DENY-ALL in
  neighbor 198.51.100.10 prefix-list PL-DEFAULT-ONLY out
  neighbor 203.0.113.249 activate
 exit-address-family
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.3. Thiết bị `HCM-SRV1` — Máy chủ trung tâm DHCP / DNS / IP SLA tại TP.HCM (Cisco vIOS Router)

Mở Console của **`HCM-SRV1`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- HCM-SRV1
! Platform: vios   Role: server   Site: HCM
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname HCM-SRV1
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
ip domain lookup
ip cef
ipv6 unicast-routing
ipv6 cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
interface GigabitEthernet0/1
 description Campus services NIC -> HCM-ACC1 Gi2/0 (VLAN 80)
 ip address 10.10.43.10 255.255.255.0
 ipv6 address 2001:db8:a010:8001::10/64
 no shutdown
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.16 255.255.255.0
 no cdp enable
 no shutdown
!
ip route 0.0.0.0 0.0.0.0 10.10.43.1 name HSRP-VIP
ipv6 route ::/0 GigabitEthernet0/1 FE80::1
!
! ---------------- Centralised DHCP for all three sites ----------------
ip dhcp excluded-address 10.10.32.1 10.10.32.20
ip dhcp excluded-address 10.10.0.1 10.10.0.20
ip dhcp excluded-address 10.10.16.1 10.10.16.20
ip dhcp excluded-address 10.10.36.1 10.10.36.20
ip dhcp excluded-address 10.10.42.1 10.10.42.20
ip dhcp excluded-address 10.20.0.1 10.20.0.20
ip dhcp excluded-address 10.20.16.1 10.20.16.20
ip dhcp excluded-address 10.20.24.1 10.20.24.20
ip dhcp excluded-address 10.30.128.1 10.30.128.20
ip dhcp excluded-address 10.30.136.1 10.30.136.20
ip dhcp excluded-address 10.30.0.1 10.30.0.20
ip dhcp excluded-address 10.30.140.1 10.30.140.20
!
ip dhcp pool HCM-V10-EXEC_FINANCE
 network 10.10.32.0 255.255.255.0
 default-router 10.10.32.1
 dns-server 10.10.43.10
 domain-name tvi.lab
 lease 1
!
ip dhcp pool HCM-V12-CORP_STAFF
 network 10.10.0.0 255.255.255.0
 default-router 10.10.0.1
 dns-server 10.10.43.10
 domain-name tvi.lab
 lease 1
!
ip dhcp pool HCM-V40-VOICE
 network 10.10.16.0 255.255.255.0
 default-router 10.10.16.1
 dns-server 10.10.43.10
 domain-name tvi.lab
 lease 1
!
ip dhcp pool HCM-V60-GUEST
 network 10.10.36.0 255.255.255.0
 default-router 10.10.36.1
 dns-server 192.0.2.53
 lease 0 4
!
ip dhcp pool HCM-V70-WLAN_AP
 network 10.10.42.0 255.255.255.0
 default-router 10.10.42.1
 dns-server 10.10.43.10
 domain-name tvi.lab
 lease 1
 option 43 hex f104.0a0a.2b14
!
ip dhcp pool HAN-V20-RND_ENGINEERING
 network 10.20.0.0 255.255.255.0
 default-router 10.20.0.1
 dns-server 10.10.43.10
 domain-name tvi.lab
 lease 1
!
ip dhcp pool HAN-V40-VOICE
 network 10.20.16.0 255.255.255.0
 default-router 10.20.16.1
 dns-server 10.10.43.10
 domain-name tvi.lab
 lease 1
!
ip dhcp pool HAN-V60-GUEST
 network 10.20.24.0 255.255.255.0
 default-router 10.20.24.1
 dns-server 192.0.2.53
 lease 0 4
!
ip dhcp pool DAD-V30-LOGISTICS_OPS
 network 10.30.128.0 255.255.255.0
 default-router 10.30.128.1
 dns-server 10.10.43.10
 domain-name tvi.lab
 lease 1
!
ip dhcp pool DAD-V40-VOICE
 network 10.30.136.0 255.255.255.0
 default-router 10.30.136.1
 dns-server 10.10.43.10
 domain-name tvi.lab
 lease 1
!
ip dhcp pool DAD-V50-IOT_DEVICES
 network 10.30.0.0 255.255.255.0
 default-router 10.30.0.1
 dns-server 10.10.43.10
 domain-name tvi.lab
 lease 1
!
ip dhcp pool DAD-V60-GUEST
 network 10.30.140.0 255.255.255.0
 default-router 10.30.140.1
 dns-server 192.0.2.53
 lease 0 4
!
! ---------------- Internal DNS (forwards unknown names to the Internet resolver) -----
ip dns server
ip name-server 192.0.2.53
ip host hcm-edg1.tvi.lab 10.10.255.1
ip host hcm-edg2.tvi.lab 10.10.255.2
ip host hcm-core1.tvi.lab 10.10.255.3
ip host hcm-core2.tvi.lab 10.10.255.4
ip host hcm-acc1.tvi.lab 10.10.44.15
ip host han-edg1.tvi.lab 10.20.255.1
ip host han-edg2.tvi.lab 10.20.255.2
ip host han-acc1.tvi.lab 10.20.31.15
ip host dad-edg1.tvi.lab 10.30.255.1
ip host dad-edg2.tvi.lab 10.30.255.2
ip host dad-acc1.tvi.lab 10.30.144.15
ip host hcm-srv1.tvi.lab 10.10.43.10
ip host wlc.tvi.lab 10.10.43.20
!
! ---------------- NTP master for the enterprise ----------------
ntp master 4
!
! ---------------- Simulated VoIP (G.711) towards each branch ----------------
ip sla 10
 udp-jitter 10.20.255.1 16384 source-ip 10.10.43.10 codec g711ulaw
  tos 184
  tag VOIP-HCM-TO-HAN
  frequency 30
ip sla schedule 10 life forever start-time now
ip sla 20
 udp-jitter 10.30.255.1 16386 source-ip 10.10.43.10 codec g711ulaw
  tos 184
  tag VOIP-HCM-TO-DAD
  frequency 30
ip sla schedule 20 life forever start-time now
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.4. Thiết bị `HCM-EDG1` — Router Biên WAN 1 tại TP.HCM (Cisco vIOS Router)

Mở Console của **`HCM-EDG1`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- HCM-EDG1
! Platform: vios   Role: edge   Site: HCM
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname HCM-EDG1
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
ipv6 unicast-routing
ipv6 cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
! ---------------- IPsec (IKEv2) protecting the GRE overlay ----------------
crypto ikev2 proposal TVI-IKEV2-PROP
 encryption aes-cbc-256
 integrity sha256
 group 14
crypto ikev2 policy TVI-IKEV2-POL
 proposal TVI-IKEV2-PROP
crypto ikev2 keyring TVI-KEYRING
 peer ANY-SITE
  address 0.0.0.0 0.0.0.0
  pre-shared-key TVI-Overlay-PSK-2026
crypto ikev2 profile TVI-IKEV2-PROFILE
 match identity remote address 0.0.0.0
 authentication remote pre-share
 authentication local pre-share
 keyring local TVI-KEYRING
 dpd 10 3 on-demand
!
crypto ipsec transform-set TVI-TS esp-aes 256 esp-sha256-hmac
 mode transport
crypto ipsec profile TVI-IPSEC-PROFILE
 set transform-set TVI-TS
 set ikev2-profile TVI-IKEV2-PROFILE
!
! ---------------- Zone-based firewall ----------------
zone security INSIDE
 description LAN, site interconnects and overlay tunnels
zone security OUTSIDE
 description ISP transport (untrusted)
!
class-map type inspect match-any CM-INSIDE-TO-OUTSIDE
 match protocol tcp
 match protocol udp
 match protocol icmp
policy-map type inspect PM-INSIDE-TO-OUTSIDE
 class type inspect CM-INSIDE-TO-OUTSIDE
  inspect
 class class-default
  drop log
!
ip access-list extended ACL-OUTSIDE-TO-SELF
 remark Control plane allowed from the ISP: IKE/IPsec, GRE, BGP, ICMP
 permit udp any any eq isakmp
 permit udp any any eq non500-isakmp
 permit esp any any
 permit gre any any
 permit tcp any any eq bgp
 permit tcp any eq bgp any
 permit icmp any any
class-map type inspect match-any CM-OUTSIDE-TO-SELF
 match access-group name ACL-OUTSIDE-TO-SELF
policy-map type inspect PM-OUTSIDE-TO-SELF
 class type inspect CM-OUTSIDE-TO-SELF
  pass
 class class-default
  drop log
!
zone-pair security ZP-INSIDE-OUTSIDE source INSIDE destination OUTSIDE
 service-policy type inspect PM-INSIDE-TO-OUTSIDE
zone-pair security ZP-OUTSIDE-SELF source OUTSIDE destination self
 service-policy type inspect PM-OUTSIDE-TO-SELF
!
! ---------------- QoS: classify & mark at the WAN-edge LAN side ----------------
ip access-list extended ACL-QOS-RTP
 remark RTP media (VoIP) -- also matches the IP SLA udp-jitter probes
 permit udp 10.0.0.0 0.255.255.255 any range 16384 32767
ip access-list extended ACL-QOS-SIGNALING
 permit udp 10.0.0.0 0.255.255.255 any range 5060 5061
 permit tcp 10.0.0.0 0.255.255.255 any range 5060 5061
ip access-list extended ACL-QOS-CRITICAL
 remark Executive/Finance and site-admin subnets
 permit ip 10.10.32.0 0.0.3.255 any
 permit ip 10.20.28.0 0.0.1.255 any
!
class-map match-any CM-IN-VOICE
 match access-group name ACL-QOS-RTP
class-map match-any CM-IN-SIGNALING
 match access-group name ACL-QOS-SIGNALING
class-map match-any CM-IN-CRITICAL
 match access-group name ACL-QOS-CRITICAL
!
policy-map PM-LAN-MARK-IN
 description Trust boundary: re-mark everything entering the WAN edge
 class CM-IN-VOICE
  set dscp ef
 class CM-IN-SIGNALING
  set dscp cs3
 class CM-IN-CRITICAL
  set dscp af31
 class class-default
  set dscp default
!
! ---------------- QoS: queue on the WAN transport (LLQ under a shaper) ----------
class-map match-any CM-WAN-VOICE
 match dscp ef
class-map match-any CM-WAN-SIGNALING
 match dscp cs3
class-map match-any CM-WAN-CRITICAL
 match dscp af31
!
policy-map PM-WAN-QUEUING
 class CM-WAN-VOICE
  priority percent 30
 class CM-WAN-SIGNALING
  bandwidth percent 5
 class CM-WAN-CRITICAL
  bandwidth percent 25
 class class-default
  fair-queue
!
policy-map PM-WAN-SHAPE
 description Shape to the 50 Mbps contracted WAN rate, then LLQ
 class class-default
  shape average 50000000
  service-policy PM-WAN-QUEUING
!
interface Loopback0
 description Router-ID / iBGP / management loopback
 ip address 10.10.255.1 255.255.255.255
 ipv6 address 2001:db8:a010:ff00::1/128
 ip ospf 10 area 0
 ipv6 ospf 10 area 0
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.11 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet0/1
 description WAN transport A -> ISP-A Gi0/1 (demarcation point)
 ip address 203.0.113.2 255.255.255.252
 ip nat outside
 zone-member security OUTSIDE
 no ip redirects
 no ip unreachables
 no ip proxy-arp
 no cdp enable
 service-policy output PM-WAN-SHAPE
 no shutdown
!
interface GigabitEthernet0/2
 description P2P -> HCM-CORE1 Gi1/0
 ip address 10.10.254.1 255.255.255.252
 ipv6 address 2001:db8:a010:fe01::1/64
 ip nat inside
 zone-member security INSIDE
 ip ospf network point-to-point
 ip ospf 10 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 10 area 0
 service-policy input PM-LAN-MARK-IN
 no shutdown
!
interface GigabitEthernet0/3
 description P2P -> HCM-CORE2 Gi1/0
 ip address 10.10.254.5 255.255.255.252
 ipv6 address 2001:db8:a010:fe02::1/64
 ip nat inside
 zone-member security INSIDE
 ip ospf network point-to-point
 ip ospf 10 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 10 area 0
 service-policy input PM-LAN-MARK-IN
 no shutdown
!
interface GigabitEthernet0/4
 description P2P -> HCM-EDG2 Gi0/4
 ip address 10.10.254.17 255.255.255.252
 ipv6 address 2001:db8:a010:fe05::1/64
 ip nat inside
 zone-member security INSIDE
 ip ospf network point-to-point
 ip ospf 10 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 10 area 0
 no shutdown
!
interface Tunnel11
 description Overlay plane A -> HAN-EDG1 Tunnel11 (GRE/IPsec)
 bandwidth 50000
 ip address 10.0.0.1 255.255.255.252
 ip mtu 1400
 ip tcp adjust-mss 1360
 ipv6 address 2001:db8:a000:11::1/64
 ipv6 mtu 1400
 zone-member security INSIDE
 qos pre-classify
 tunnel source GigabitEthernet0/1
 tunnel destination 203.0.113.6
 tunnel protection ipsec profile TVI-IPSEC-PROFILE
!
interface Tunnel12
 description Overlay plane A -> DAD-EDG1 Tunnel12 (GRE/IPsec)
 bandwidth 50000
 ip address 10.0.0.5 255.255.255.252
 ip mtu 1400
 ip tcp adjust-mss 1360
 ipv6 address 2001:db8:a000:12::1/64
 ipv6 mtu 1400
 zone-member security INSIDE
 qos pre-classify
 tunnel source GigabitEthernet0/1
 tunnel destination 203.0.113.10
 tunnel protection ipsec profile TVI-IPSEC-PROFILE
!
ip access-list extended ACL-NAT
 remark PAT for Internet-bound traffic only; site-to-site traffic is never translated
 deny   ip 10.0.0.0 0.255.255.255 10.0.0.0 0.255.255.255
 permit ip 10.10.0.0 0.0.255.255 any
ip nat inside source list ACL-NAT interface GigabitEthernet0/1 overload
!
ip route 10.10.0.0 255.255.0.0 Null0 254 name SITE-AGGREGATE
ipv6 route 2001:db8:a010::/48 Null0 254
!
ip prefix-list PL-DEFAULT-ONLY seq 5 permit 0.0.0.0/0
ip prefix-list PL-DENY-ALL seq 5 deny 0.0.0.0/0 le 32
ip prefix-list PL-ENTERPRISE-IN seq 5 permit 10.0.0.0/8 ge 16 le 24
ip prefix-list PL-SITE-OUT seq 5 permit 10.10.0.0/16
ipv6 prefix-list PL6-ENTERPRISE-IN seq 5 permit 2001:db8:a000::/40 ge 48 le 48
ipv6 prefix-list PL6-SITE-OUT seq 5 permit 2001:db8:a010::/48
!
ip prefix-list PL-OTHER-SITES seq 5 deny 10.10.0.0/16 le 32
ip prefix-list PL-OTHER-SITES seq 10 permit 10.0.0.0/8 ge 16 le 24
ipv6 prefix-list PL6-OTHER-SITES seq 5 deny 2001:db8:a010::/48 le 128
ipv6 prefix-list PL6-OTHER-SITES seq 10 permit 2001:db8:a000::/40 ge 48 le 48
!
route-map RM-BGP-TO-OSPF permit 10
 description Inject remote-site aggregates into the HQ underlay
 match ip address prefix-list PL-OTHER-SITES
route-map RM6-BGP-TO-OSPF permit 10
 match ipv6 address prefix-list PL6-OTHER-SITES
!
router ospf 10
 router-id 10.10.255.1
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/2
 no passive-interface GigabitEthernet0/3
 no passive-interface GigabitEthernet0/4
 default-information originate
 redistribute bgp 65010 subnets route-map RM-BGP-TO-OSPF
!
ipv6 router ospf 10
 router-id 10.10.255.1
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/2
 no passive-interface GigabitEthernet0/3
 no passive-interface GigabitEthernet0/4
 redistribute bgp 65010 route-map RM6-BGP-TO-OSPF
!
router bgp 65010
 bgp router-id 10.10.255.1
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 neighbor 203.0.113.1 remote-as 65100
 neighbor 203.0.113.1 description eBGP ISP-A (Internet transport A)
 neighbor 10.10.255.2 remote-as 65010
 neighbor 10.10.255.2 description iBGP HCM-EDG2
 neighbor 10.10.255.2 update-source Loopback0
 neighbor 2001:db8:a010:ff00::2 remote-as 65010
 neighbor 2001:db8:a010:ff00::2 description iBGP-v6 HCM-EDG2
 neighbor 2001:db8:a010:ff00::2 update-source Loopback0
 neighbor 10.0.0.2 remote-as 65020
 neighbor 10.0.0.2 description eBGP overlay HAN-EDG1 via Tunnel11
 neighbor 10.0.0.2 timers 5 15
 neighbor 2001:db8:a000:11::2 remote-as 65020
 neighbor 2001:db8:a000:11::2 description eBGP-v6 overlay HAN-EDG1 via Tunnel11
 neighbor 2001:db8:a000:11::2 timers 5 15
 neighbor 10.0.0.6 remote-as 65030
 neighbor 10.0.0.6 description eBGP overlay DAD-EDG1 via Tunnel12
 neighbor 10.0.0.6 timers 5 15
 neighbor 2001:db8:a000:12::2 remote-as 65030
 neighbor 2001:db8:a000:12::2 description eBGP-v6 overlay DAD-EDG1 via Tunnel12
 neighbor 2001:db8:a000:12::2 timers 5 15
 !
 address-family ipv4
  network 10.10.0.0 mask 255.255.0.0
  neighbor 203.0.113.1 activate
  neighbor 203.0.113.1 prefix-list PL-DEFAULT-ONLY in
  neighbor 203.0.113.1 prefix-list PL-DENY-ALL out
  neighbor 10.10.255.2 activate
  neighbor 10.10.255.2 next-hop-self
  neighbor 10.0.0.2 activate
  neighbor 10.0.0.2 prefix-list PL-ENTERPRISE-IN in
  neighbor 10.0.0.2 prefix-list PL-SITE-OUT out
  neighbor 10.0.0.6 activate
  neighbor 10.0.0.6 prefix-list PL-ENTERPRISE-IN in
  neighbor 10.0.0.6 prefix-list PL-SITE-OUT out
 exit-address-family
 !
 address-family ipv6
  network 2001:db8:a010::/48
  neighbor 2001:db8:a010:ff00::2 activate
  neighbor 2001:db8:a010:ff00::2 next-hop-self
  neighbor 2001:db8:a000:11::2 activate
  neighbor 2001:db8:a000:11::2 prefix-list PL6-ENTERPRISE-IN in
  neighbor 2001:db8:a000:11::2 prefix-list PL6-SITE-OUT out
  neighbor 2001:db8:a000:12::2 activate
  neighbor 2001:db8:a000:12::2 prefix-list PL6-ENTERPRISE-IN in
  neighbor 2001:db8:a000:12::2 prefix-list PL6-SITE-OUT out
 exit-address-family
!
ip sla responder
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.5. Thiết bị `HCM-EDG2` — Router Biên WAN 2 tại TP.HCM (Cisco vIOS Router)

Mở Console của **`HCM-EDG2`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- HCM-EDG2
! Platform: vios   Role: edge   Site: HCM
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname HCM-EDG2
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
ipv6 unicast-routing
ipv6 cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
! ---------------- IPsec (IKEv2) protecting the GRE overlay ----------------
crypto ikev2 proposal TVI-IKEV2-PROP
 encryption aes-cbc-256
 integrity sha256
 group 14
crypto ikev2 policy TVI-IKEV2-POL
 proposal TVI-IKEV2-PROP
crypto ikev2 keyring TVI-KEYRING
 peer ANY-SITE
  address 0.0.0.0 0.0.0.0
  pre-shared-key TVI-Overlay-PSK-2026
crypto ikev2 profile TVI-IKEV2-PROFILE
 match identity remote address 0.0.0.0
 authentication remote pre-share
 authentication local pre-share
 keyring local TVI-KEYRING
 dpd 10 3 on-demand
!
crypto ipsec transform-set TVI-TS esp-aes 256 esp-sha256-hmac
 mode transport
crypto ipsec profile TVI-IPSEC-PROFILE
 set transform-set TVI-TS
 set ikev2-profile TVI-IKEV2-PROFILE
!
! ---------------- Zone-based firewall ----------------
zone security INSIDE
 description LAN, site interconnects and overlay tunnels
zone security OUTSIDE
 description ISP transport (untrusted)
!
class-map type inspect match-any CM-INSIDE-TO-OUTSIDE
 match protocol tcp
 match protocol udp
 match protocol icmp
policy-map type inspect PM-INSIDE-TO-OUTSIDE
 class type inspect CM-INSIDE-TO-OUTSIDE
  inspect
 class class-default
  drop log
!
ip access-list extended ACL-OUTSIDE-TO-SELF
 remark Control plane allowed from the ISP: IKE/IPsec, GRE, BGP, ICMP
 permit udp any any eq isakmp
 permit udp any any eq non500-isakmp
 permit esp any any
 permit gre any any
 permit tcp any any eq bgp
 permit tcp any eq bgp any
 permit icmp any any
class-map type inspect match-any CM-OUTSIDE-TO-SELF
 match access-group name ACL-OUTSIDE-TO-SELF
policy-map type inspect PM-OUTSIDE-TO-SELF
 class type inspect CM-OUTSIDE-TO-SELF
  pass
 class class-default
  drop log
!
zone-pair security ZP-INSIDE-OUTSIDE source INSIDE destination OUTSIDE
 service-policy type inspect PM-INSIDE-TO-OUTSIDE
zone-pair security ZP-OUTSIDE-SELF source OUTSIDE destination self
 service-policy type inspect PM-OUTSIDE-TO-SELF
!
! ---------------- QoS: classify & mark at the WAN-edge LAN side ----------------
ip access-list extended ACL-QOS-RTP
 remark RTP media (VoIP) -- also matches the IP SLA udp-jitter probes
 permit udp 10.0.0.0 0.255.255.255 any range 16384 32767
ip access-list extended ACL-QOS-SIGNALING
 permit udp 10.0.0.0 0.255.255.255 any range 5060 5061
 permit tcp 10.0.0.0 0.255.255.255 any range 5060 5061
ip access-list extended ACL-QOS-CRITICAL
 remark Executive/Finance and site-admin subnets
 permit ip 10.10.32.0 0.0.3.255 any
 permit ip 10.20.28.0 0.0.1.255 any
!
class-map match-any CM-IN-VOICE
 match access-group name ACL-QOS-RTP
class-map match-any CM-IN-SIGNALING
 match access-group name ACL-QOS-SIGNALING
class-map match-any CM-IN-CRITICAL
 match access-group name ACL-QOS-CRITICAL
!
policy-map PM-LAN-MARK-IN
 description Trust boundary: re-mark everything entering the WAN edge
 class CM-IN-VOICE
  set dscp ef
 class CM-IN-SIGNALING
  set dscp cs3
 class CM-IN-CRITICAL
  set dscp af31
 class class-default
  set dscp default
!
! ---------------- QoS: queue on the WAN transport (LLQ under a shaper) ----------
class-map match-any CM-WAN-VOICE
 match dscp ef
class-map match-any CM-WAN-SIGNALING
 match dscp cs3
class-map match-any CM-WAN-CRITICAL
 match dscp af31
!
policy-map PM-WAN-QUEUING
 class CM-WAN-VOICE
  priority percent 30
 class CM-WAN-SIGNALING
  bandwidth percent 5
 class CM-WAN-CRITICAL
  bandwidth percent 25
 class class-default
  fair-queue
!
policy-map PM-WAN-SHAPE
 description Shape to the 50 Mbps contracted WAN rate, then LLQ
 class class-default
  shape average 50000000
  service-policy PM-WAN-QUEUING
!
interface Loopback0
 description Router-ID / iBGP / management loopback
 ip address 10.10.255.2 255.255.255.255
 ipv6 address 2001:db8:a010:ff00::2/128
 ip ospf 10 area 0
 ipv6 ospf 10 area 0
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.12 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet0/1
 description WAN transport B -> ISP-B Gi0/1 (demarcation point)
 ip address 198.51.100.2 255.255.255.252
 ip nat outside
 zone-member security OUTSIDE
 no ip redirects
 no ip unreachables
 no ip proxy-arp
 no cdp enable
 service-policy output PM-WAN-SHAPE
 no shutdown
!
interface GigabitEthernet0/2
 description P2P -> HCM-CORE1 Gi1/1
 ip address 10.10.254.9 255.255.255.252
 ipv6 address 2001:db8:a010:fe03::1/64
 ip nat inside
 zone-member security INSIDE
 ip ospf network point-to-point
 ip ospf 10 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 10 area 0
 service-policy input PM-LAN-MARK-IN
 no shutdown
!
interface GigabitEthernet0/3
 description P2P -> HCM-CORE2 Gi1/1
 ip address 10.10.254.13 255.255.255.252
 ipv6 address 2001:db8:a010:fe04::1/64
 ip nat inside
 zone-member security INSIDE
 ip ospf network point-to-point
 ip ospf 10 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 10 area 0
 service-policy input PM-LAN-MARK-IN
 no shutdown
!
interface GigabitEthernet0/4
 description P2P -> HCM-EDG1 Gi0/4
 ip address 10.10.254.18 255.255.255.252
 ipv6 address 2001:db8:a010:fe05::2/64
 ip nat inside
 zone-member security INSIDE
 ip ospf network point-to-point
 ip ospf 10 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 10 area 0
 no shutdown
!
interface Tunnel21
 description Overlay plane B -> HAN-EDG2 Tunnel21 (GRE/IPsec)
 bandwidth 50000
 ip address 10.0.0.9 255.255.255.252
 ip mtu 1400
 ip tcp adjust-mss 1360
 ipv6 address 2001:db8:a000:21::1/64
 ipv6 mtu 1400
 zone-member security INSIDE
 qos pre-classify
 tunnel source GigabitEthernet0/1
 tunnel destination 198.51.100.6
 tunnel protection ipsec profile TVI-IPSEC-PROFILE
!
interface Tunnel22
 description Overlay plane B -> DAD-EDG2 Tunnel22 (GRE/IPsec)
 bandwidth 50000
 ip address 10.0.0.13 255.255.255.252
 ip mtu 1400
 ip tcp adjust-mss 1360
 ipv6 address 2001:db8:a000:22::1/64
 ipv6 mtu 1400
 zone-member security INSIDE
 qos pre-classify
 tunnel source GigabitEthernet0/1
 tunnel destination 198.51.100.10
 tunnel protection ipsec profile TVI-IPSEC-PROFILE
!
ip access-list extended ACL-NAT
 remark PAT for Internet-bound traffic only; site-to-site traffic is never translated
 deny   ip 10.0.0.0 0.255.255.255 10.0.0.0 0.255.255.255
 permit ip 10.10.0.0 0.0.255.255 any
ip nat inside source list ACL-NAT interface GigabitEthernet0/1 overload
!
ip route 10.10.0.0 255.255.0.0 Null0 254 name SITE-AGGREGATE
ipv6 route 2001:db8:a010::/48 Null0 254
!
ip prefix-list PL-DEFAULT-ONLY seq 5 permit 0.0.0.0/0
ip prefix-list PL-DENY-ALL seq 5 deny 0.0.0.0/0 le 32
ip prefix-list PL-ENTERPRISE-IN seq 5 permit 10.0.0.0/8 ge 16 le 24
ip prefix-list PL-SITE-OUT seq 5 permit 10.10.0.0/16
ipv6 prefix-list PL6-ENTERPRISE-IN seq 5 permit 2001:db8:a000::/40 ge 48 le 48
ipv6 prefix-list PL6-SITE-OUT seq 5 permit 2001:db8:a010::/48
!
ip prefix-list PL-OTHER-SITES seq 5 deny 10.10.0.0/16 le 32
ip prefix-list PL-OTHER-SITES seq 10 permit 10.0.0.0/8 ge 16 le 24
ipv6 prefix-list PL6-OTHER-SITES seq 5 deny 2001:db8:a010::/48 le 128
ipv6 prefix-list PL6-OTHER-SITES seq 10 permit 2001:db8:a000::/40 ge 48 le 48
!
route-map RM-BGP-TO-OSPF permit 10
 description Inject remote-site aggregates into the HQ underlay
 match ip address prefix-list PL-OTHER-SITES
route-map RM6-BGP-TO-OSPF permit 10
 match ipv6 address prefix-list PL6-OTHER-SITES
!
router ospf 10
 router-id 10.10.255.2
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/2
 no passive-interface GigabitEthernet0/3
 no passive-interface GigabitEthernet0/4
 default-information originate
 redistribute bgp 65010 subnets route-map RM-BGP-TO-OSPF
!
ipv6 router ospf 10
 router-id 10.10.255.2
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/2
 no passive-interface GigabitEthernet0/3
 no passive-interface GigabitEthernet0/4
 redistribute bgp 65010 route-map RM6-BGP-TO-OSPF
!
router bgp 65010
 bgp router-id 10.10.255.2
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 neighbor 198.51.100.1 remote-as 65200
 neighbor 198.51.100.1 description eBGP ISP-B (Internet transport B)
 neighbor 10.10.255.1 remote-as 65010
 neighbor 10.10.255.1 description iBGP HCM-EDG1
 neighbor 10.10.255.1 update-source Loopback0
 neighbor 2001:db8:a010:ff00::1 remote-as 65010
 neighbor 2001:db8:a010:ff00::1 description iBGP-v6 HCM-EDG1
 neighbor 2001:db8:a010:ff00::1 update-source Loopback0
 neighbor 10.0.0.10 remote-as 65020
 neighbor 10.0.0.10 description eBGP overlay HAN-EDG2 via Tunnel21
 neighbor 10.0.0.10 timers 5 15
 neighbor 2001:db8:a000:21::2 remote-as 65020
 neighbor 2001:db8:a000:21::2 description eBGP-v6 overlay HAN-EDG2 via Tunnel21
 neighbor 2001:db8:a000:21::2 timers 5 15
 neighbor 10.0.0.14 remote-as 65030
 neighbor 10.0.0.14 description eBGP overlay DAD-EDG2 via Tunnel22
 neighbor 10.0.0.14 timers 5 15
 neighbor 2001:db8:a000:22::2 remote-as 65030
 neighbor 2001:db8:a000:22::2 description eBGP-v6 overlay DAD-EDG2 via Tunnel22
 neighbor 2001:db8:a000:22::2 timers 5 15
 !
 address-family ipv4
  network 10.10.0.0 mask 255.255.0.0
  neighbor 198.51.100.1 activate
  neighbor 198.51.100.1 prefix-list PL-DEFAULT-ONLY in
  neighbor 198.51.100.1 prefix-list PL-DENY-ALL out
  neighbor 10.10.255.1 activate
  neighbor 10.10.255.1 next-hop-self
  neighbor 10.0.0.10 activate
  neighbor 10.0.0.10 prefix-list PL-ENTERPRISE-IN in
  neighbor 10.0.0.10 prefix-list PL-SITE-OUT out
  neighbor 10.0.0.14 activate
  neighbor 10.0.0.14 prefix-list PL-ENTERPRISE-IN in
  neighbor 10.0.0.14 prefix-list PL-SITE-OUT out
 exit-address-family
 !
 address-family ipv6
  network 2001:db8:a010::/48
  neighbor 2001:db8:a010:ff00::1 activate
  neighbor 2001:db8:a010:ff00::1 next-hop-self
  neighbor 2001:db8:a000:21::2 activate
  neighbor 2001:db8:a000:21::2 prefix-list PL6-ENTERPRISE-IN in
  neighbor 2001:db8:a000:21::2 prefix-list PL6-SITE-OUT out
  neighbor 2001:db8:a000:22::2 activate
  neighbor 2001:db8:a000:22::2 prefix-list PL6-ENTERPRISE-IN in
  neighbor 2001:db8:a000:22::2 prefix-list PL6-SITE-OUT out
 exit-address-family
!
ip sla responder
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.6. Thiết bị `HCM-CORE1` — Switch Core L3 số 1 tại TP.HCM (Cisco vIOS Switch)

Mở Console của **`HCM-CORE1`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- HCM-CORE1
! Platform: viosl2   Role: core   Site: HCM
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname HCM-CORE1
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
ipv6 unicast-routing
ipv6 cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
ip routing
!
vtp mode transparent
!
spanning-tree mode rapid-pvst
spanning-tree extend system-id
spanning-tree loopguard default
spanning-tree vlan 10,12,40,80,900 priority 24576
spanning-tree vlan 60,70,99 priority 28672
!
vlan 10
 name EXEC_FINANCE
vlan 12
 name CORP_STAFF
vlan 40
 name VOICE
vlan 60
 name GUEST
vlan 70
 name WLAN_AP
vlan 80
 name SERVERS
vlan 99
 name MANAGEMENT
vlan 900
 name CORE_TRANSIT
vlan 999
 name NATIVE_UNUSED
!
interface Port-channel1
 description LACP L2 trunk -> HCM-CORE2 Po1
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 10,12,40,60,70,80,99,900
 switchport nonegotiate
!
interface GigabitEthernet0/1
 description Po1 member -> HCM-CORE2 Gi0/1
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 10,12,40,60,70,80,99,900
 switchport nonegotiate
 channel-group 1 mode active
 no shutdown
!
interface GigabitEthernet0/2
 description Po1 member -> HCM-CORE2 Gi0/2
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 10,12,40,60,70,80,99,900
 switchport nonegotiate
 channel-group 1 mode active
 no shutdown
!
interface GigabitEthernet0/3
 description L2 trunk -> HCM-ACC1 Gi0/1
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 10,12,40,60,70,80,99
 switchport nonegotiate
 spanning-tree guard root
 no shutdown
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 no switchport
 ip address 172.16.99.13 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet1/0
 description L3 uplink -> HCM-EDG1 Gi0/2
 no switchport
 ip address 10.10.254.2 255.255.255.252
 ipv6 address 2001:db8:a010:fe01::2/64
 ip ospf network point-to-point
 ip ospf 10 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 10 area 0
 no shutdown
!
interface GigabitEthernet1/1
 description L3 uplink -> HCM-EDG2 Gi0/2
 no switchport
 ip address 10.10.254.10 255.255.255.252
 ipv6 address 2001:db8:a010:fe03::2/64
 ip ospf network point-to-point
 ip ospf 10 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 10 area 0
 no shutdown
!
interface Vlan900
 description OSPF transit -> HCM-CORE2 (over Po1)
 ip address 10.10.254.21 255.255.255.252
 ipv6 address 2001:db8:a010:fe06::1/64
 ip ospf network point-to-point
 ip ospf 10 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 10 area 0
 no shutdown
!
interface GigabitEthernet1/2
 description DC border -> DC-LEAF1 Gi0/5 (VRF TENANT-PROD on the leaf)
 no switchport
 ip address 10.10.189.1 255.255.255.252
 ip ospf network point-to-point
 ip ospf 10 area 0
 no shutdown
!
interface Loopback0
 ip address 10.10.255.3 255.255.255.255
 ipv6 address 2001:db8:a010:ff00::3/128
 ip ospf 10 area 0
 ipv6 ospf 10 area 0
!
interface Vlan10
 description Gateway EXEC_FINANCE (HSRP active)
 ip address 10.10.32.2 255.255.255.0
 ip helper-address 10.10.43.10
 ip access-group ACL-EXEC-PROTECT out
 no ip redirects
 ipv6 address 2001:db8:a010:1001::2/64
 ipv6 traffic-filter ACL6-EXEC-PROTECT out
 ipv6 ospf 10 area 0
 ip ospf 10 area 0
 standby version 2
 standby 10 ip 10.10.32.1
 standby 10 priority 110
 standby 10 preempt delay minimum 10
 standby 10 timers 1 3
 standby 10 name HSRP-V10
 standby 1010 ipv6 FE80::1
 standby 1010 priority 110
 standby 1010 preempt delay minimum 10
 standby 1010 timers 1 3
 no shutdown
!
interface Vlan12
 description Gateway CORP_STAFF (HSRP active)
 ip address 10.10.0.2 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a010:1201::2/64
 ipv6 ospf 10 area 0
 ip ospf 10 area 0
 standby version 2
 standby 12 ip 10.10.0.1
 standby 12 priority 110
 standby 12 preempt delay minimum 10
 standby 12 timers 1 3
 standby 12 name HSRP-V12
 standby 1012 ipv6 FE80::1
 standby 1012 priority 110
 standby 1012 preempt delay minimum 10
 standby 1012 timers 1 3
 no shutdown
!
interface Vlan40
 description Gateway VOICE (HSRP active)
 ip address 10.10.16.2 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a010:4001::2/64
 ipv6 ospf 10 area 0
 ip ospf 10 area 0
 standby version 2
 standby 40 ip 10.10.16.1
 standby 40 priority 110
 standby 40 preempt delay minimum 10
 standby 40 timers 1 3
 standby 40 name HSRP-V40
 standby 1040 ipv6 FE80::1
 standby 1040 priority 110
 standby 1040 preempt delay minimum 10
 standby 1040 timers 1 3
 no shutdown
!
interface Vlan60
 description Gateway GUEST (HSRP standby)
 ip address 10.10.36.2 255.255.255.0
 ip helper-address 10.10.43.10
 ip access-group ACL-GUEST-IN in
 no ip redirects
 ip ospf 10 area 0
 standby version 2
 standby 60 ip 10.10.36.1
 standby 60 priority 100
 standby 60 preempt delay minimum 10
 standby 60 timers 1 3
 standby 60 name HSRP-V60
 no shutdown
!
interface Vlan70
 description Gateway WLAN_AP (HSRP standby)
 ip address 10.10.42.2 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a010:7001::2/64
 ipv6 ospf 10 area 0
 ip ospf 10 area 0
 standby version 2
 standby 70 ip 10.10.42.1
 standby 70 priority 100
 standby 70 preempt delay minimum 10
 standby 70 timers 1 3
 standby 70 name HSRP-V70
 standby 1070 ipv6 FE80::1
 standby 1070 priority 100
 standby 1070 preempt delay minimum 10
 standby 1070 timers 1 3
 no shutdown
!
interface Vlan80
 description Gateway SERVERS (HSRP active)
 ip address 10.10.43.2 255.255.255.0
 no ip redirects
 ipv6 address 2001:db8:a010:8001::2/64
 ipv6 ospf 10 area 0
 ip ospf 10 area 0
 standby version 2
 standby 80 ip 10.10.43.1
 standby 80 priority 110
 standby 80 preempt delay minimum 10
 standby 80 timers 1 3
 standby 80 name HSRP-V80
 standby 1080 ipv6 FE80::1
 standby 1080 priority 110
 standby 1080 preempt delay minimum 10
 standby 1080 timers 1 3
 no shutdown
!
interface Vlan99
 description Gateway MANAGEMENT (HSRP standby)
 ip address 10.10.44.2 255.255.255.0
 no ip redirects
 ipv6 address 2001:db8:a010:9901::2/64
 ipv6 ospf 10 area 0
 ip ospf 10 area 0
 standby version 2
 standby 99 ip 10.10.44.1
 standby 99 priority 100
 standby 99 preempt delay minimum 10
 standby 99 timers 1 3
 standby 99 name HSRP-V99
 standby 1099 ipv6 FE80::1
 standby 1099 priority 100
 standby 1099 preempt delay minimum 10
 standby 1099 timers 1 3
 no shutdown
!
interface GigabitEthernet1/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet2/0
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet2/1
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet2/2
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet2/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet3/0
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet3/1
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet3/2
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet3/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
ip access-list extended ACL-EXEC-PROTECT
 remark Applied OUT on Vlan10: only servers, management and replies may enter the Executive VLAN
 permit tcp any 10.10.32.0 0.0.0.255 established
 permit ip 10.10.43.0 0.0.0.255 10.10.32.0 0.0.0.255
 permit ip 10.10.44.0 0.0.0.255 10.10.32.0 0.0.0.255
 permit icmp any 10.10.32.0 0.0.0.255 echo-reply
 permit icmp any 10.10.32.0 0.0.0.255 unreachable
 permit icmp any 10.10.32.0 0.0.0.255 time-exceeded
 deny   ip 10.0.0.0 0.255.255.255 10.10.32.0 0.0.0.255 log
 permit ip any any
!
ipv6 access-list ACL6-EXEC-PROTECT
 permit tcp any 2001:db8:a010:1001::/64 established
 permit ipv6 2001:db8:a010:8001::/64 2001:db8:a010:1001::/64
 permit ipv6 2001:db8:a010:9901::/64 2001:db8:a010:1001::/64
 permit icmp any 2001:db8:a010:1001::/64 echo-reply
 permit icmp any 2001:db8:a010:1001::/64 unreachable
 permit icmp any 2001:db8:a010:1001::/64 time-exceeded
 permit icmp any 2001:db8:a010:1001::/64 packet-too-big
 deny   ipv6 2001:db8:a000::/40 2001:db8:a010:1001::/64 log
 permit ipv6 any any
!
ip access-list extended ACL-GUEST-IN
 remark GUEST: DHCP + Internet only. No RFC1918 destination, no infrastructure.
 permit udp any eq bootpc any eq bootps
 permit udp any eq bootpc host 10.10.43.10 eq bootps
 deny   ip any 10.0.0.0 0.255.255.255 log
 deny   ip any 172.16.0.0 0.15.255.255 log
 deny   ip any 192.168.0.0 0.0.255.255 log
 permit ip any any
!
router ospf 10
 router-id 10.10.255.3
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet1/0
 no passive-interface GigabitEthernet1/1
 no passive-interface Vlan900
 no passive-interface GigabitEthernet1/2
!
ipv6 router ospf 10
 router-id 10.10.255.3
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet1/0
 no passive-interface GigabitEthernet1/1
 no passive-interface Vlan900
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.7. Thiết bị `HCM-CORE2` — Switch Core L3 số 2 tại TP.HCM (Cisco vIOS Switch)

Mở Console của **`HCM-CORE2`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- HCM-CORE2
! Platform: viosl2   Role: core   Site: HCM
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname HCM-CORE2
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
ipv6 unicast-routing
ipv6 cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
ip routing
!
vtp mode transparent
!
spanning-tree mode rapid-pvst
spanning-tree extend system-id
spanning-tree loopguard default
spanning-tree vlan 60,70,99 priority 24576
spanning-tree vlan 10,12,40,80,900 priority 28672
!
vlan 10
 name EXEC_FINANCE
vlan 12
 name CORP_STAFF
vlan 40
 name VOICE
vlan 60
 name GUEST
vlan 70
 name WLAN_AP
vlan 80
 name SERVERS
vlan 99
 name MANAGEMENT
vlan 900
 name CORE_TRANSIT
vlan 999
 name NATIVE_UNUSED
!
interface Port-channel1
 description LACP L2 trunk -> HCM-CORE1 Po1
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 10,12,40,60,70,80,99,900
 switchport nonegotiate
!
interface GigabitEthernet0/1
 description Po1 member -> HCM-CORE1 Gi0/1
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 10,12,40,60,70,80,99,900
 switchport nonegotiate
 channel-group 1 mode active
 no shutdown
!
interface GigabitEthernet0/2
 description Po1 member -> HCM-CORE1 Gi0/2
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 10,12,40,60,70,80,99,900
 switchport nonegotiate
 channel-group 1 mode active
 no shutdown
!
interface GigabitEthernet0/3
 description L2 trunk -> HCM-ACC1 Gi0/2
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 10,12,40,60,70,80,99
 switchport nonegotiate
 spanning-tree guard root
 no shutdown
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 no switchport
 ip address 172.16.99.14 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet1/0
 description L3 uplink -> HCM-EDG1 Gi0/3
 no switchport
 ip address 10.10.254.6 255.255.255.252
 ipv6 address 2001:db8:a010:fe02::2/64
 ip ospf network point-to-point
 ip ospf 10 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 10 area 0
 no shutdown
!
interface GigabitEthernet1/1
 description L3 uplink -> HCM-EDG2 Gi0/3
 no switchport
 ip address 10.10.254.14 255.255.255.252
 ipv6 address 2001:db8:a010:fe04::2/64
 ip ospf network point-to-point
 ip ospf 10 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 10 area 0
 no shutdown
!
interface Vlan900
 description OSPF transit -> HCM-CORE1 (over Po1)
 ip address 10.10.254.22 255.255.255.252
 ipv6 address 2001:db8:a010:fe06::2/64
 ip ospf network point-to-point
 ip ospf 10 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 10 area 0
 no shutdown
!
interface GigabitEthernet1/2
 description DC border -> DC-LEAF2 Gi0/5 (VRF TENANT-PROD on the leaf)
 no switchport
 ip address 10.10.189.5 255.255.255.252
 ip ospf network point-to-point
 ip ospf 10 area 0
 no shutdown
!
interface Loopback0
 ip address 10.10.255.4 255.255.255.255
 ipv6 address 2001:db8:a010:ff00::4/128
 ip ospf 10 area 0
 ipv6 ospf 10 area 0
!
interface Vlan10
 description Gateway EXEC_FINANCE (HSRP standby)
 ip address 10.10.32.3 255.255.255.0
 ip helper-address 10.10.43.10
 ip access-group ACL-EXEC-PROTECT out
 no ip redirects
 ipv6 address 2001:db8:a010:1001::3/64
 ipv6 traffic-filter ACL6-EXEC-PROTECT out
 ipv6 ospf 10 area 0
 ip ospf 10 area 0
 standby version 2
 standby 10 ip 10.10.32.1
 standby 10 priority 100
 standby 10 preempt delay minimum 10
 standby 10 timers 1 3
 standby 10 name HSRP-V10
 standby 1010 ipv6 FE80::1
 standby 1010 priority 100
 standby 1010 preempt delay minimum 10
 standby 1010 timers 1 3
 no shutdown
!
interface Vlan12
 description Gateway CORP_STAFF (HSRP standby)
 ip address 10.10.0.3 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a010:1201::3/64
 ipv6 ospf 10 area 0
 ip ospf 10 area 0
 standby version 2
 standby 12 ip 10.10.0.1
 standby 12 priority 100
 standby 12 preempt delay minimum 10
 standby 12 timers 1 3
 standby 12 name HSRP-V12
 standby 1012 ipv6 FE80::1
 standby 1012 priority 100
 standby 1012 preempt delay minimum 10
 standby 1012 timers 1 3
 no shutdown
!
interface Vlan40
 description Gateway VOICE (HSRP standby)
 ip address 10.10.16.3 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a010:4001::3/64
 ipv6 ospf 10 area 0
 ip ospf 10 area 0
 standby version 2
 standby 40 ip 10.10.16.1
 standby 40 priority 100
 standby 40 preempt delay minimum 10
 standby 40 timers 1 3
 standby 40 name HSRP-V40
 standby 1040 ipv6 FE80::1
 standby 1040 priority 100
 standby 1040 preempt delay minimum 10
 standby 1040 timers 1 3
 no shutdown
!
interface Vlan60
 description Gateway GUEST (HSRP active)
 ip address 10.10.36.3 255.255.255.0
 ip helper-address 10.10.43.10
 ip access-group ACL-GUEST-IN in
 no ip redirects
 ip ospf 10 area 0
 standby version 2
 standby 60 ip 10.10.36.1
 standby 60 priority 110
 standby 60 preempt delay minimum 10
 standby 60 timers 1 3
 standby 60 name HSRP-V60
 no shutdown
!
interface Vlan70
 description Gateway WLAN_AP (HSRP active)
 ip address 10.10.42.3 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a010:7001::3/64
 ipv6 ospf 10 area 0
 ip ospf 10 area 0
 standby version 2
 standby 70 ip 10.10.42.1
 standby 70 priority 110
 standby 70 preempt delay minimum 10
 standby 70 timers 1 3
 standby 70 name HSRP-V70
 standby 1070 ipv6 FE80::1
 standby 1070 priority 110
 standby 1070 preempt delay minimum 10
 standby 1070 timers 1 3
 no shutdown
!
interface Vlan80
 description Gateway SERVERS (HSRP standby)
 ip address 10.10.43.3 255.255.255.0
 no ip redirects
 ipv6 address 2001:db8:a010:8001::3/64
 ipv6 ospf 10 area 0
 ip ospf 10 area 0
 standby version 2
 standby 80 ip 10.10.43.1
 standby 80 priority 100
 standby 80 preempt delay minimum 10
 standby 80 timers 1 3
 standby 80 name HSRP-V80
 standby 1080 ipv6 FE80::1
 standby 1080 priority 100
 standby 1080 preempt delay minimum 10
 standby 1080 timers 1 3
 no shutdown
!
interface Vlan99
 description Gateway MANAGEMENT (HSRP active)
 ip address 10.10.44.3 255.255.255.0
 no ip redirects
 ipv6 address 2001:db8:a010:9901::3/64
 ipv6 ospf 10 area 0
 ip ospf 10 area 0
 standby version 2
 standby 99 ip 10.10.44.1
 standby 99 priority 110
 standby 99 preempt delay minimum 10
 standby 99 timers 1 3
 standby 99 name HSRP-V99
 standby 1099 ipv6 FE80::1
 standby 1099 priority 110
 standby 1099 preempt delay minimum 10
 standby 1099 timers 1 3
 no shutdown
!
interface GigabitEthernet1/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet2/0
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet2/1
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet2/2
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet2/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet3/0
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet3/1
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet3/2
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
interface GigabitEthernet3/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 shutdown
!
ip access-list extended ACL-EXEC-PROTECT
 remark Applied OUT on Vlan10: only servers, management and replies may enter the Executive VLAN
 permit tcp any 10.10.32.0 0.0.0.255 established
 permit ip 10.10.43.0 0.0.0.255 10.10.32.0 0.0.0.255
 permit ip 10.10.44.0 0.0.0.255 10.10.32.0 0.0.0.255
 permit icmp any 10.10.32.0 0.0.0.255 echo-reply
 permit icmp any 10.10.32.0 0.0.0.255 unreachable
 permit icmp any 10.10.32.0 0.0.0.255 time-exceeded
 deny   ip 10.0.0.0 0.255.255.255 10.10.32.0 0.0.0.255 log
 permit ip any any
!
ipv6 access-list ACL6-EXEC-PROTECT
 permit tcp any 2001:db8:a010:1001::/64 established
 permit ipv6 2001:db8:a010:8001::/64 2001:db8:a010:1001::/64
 permit ipv6 2001:db8:a010:9901::/64 2001:db8:a010:1001::/64
 permit icmp any 2001:db8:a010:1001::/64 echo-reply
 permit icmp any 2001:db8:a010:1001::/64 unreachable
 permit icmp any 2001:db8:a010:1001::/64 time-exceeded
 permit icmp any 2001:db8:a010:1001::/64 packet-too-big
 deny   ipv6 2001:db8:a000::/40 2001:db8:a010:1001::/64 log
 permit ipv6 any any
!
ip access-list extended ACL-GUEST-IN
 remark GUEST: DHCP + Internet only. No RFC1918 destination, no infrastructure.
 permit udp any eq bootpc any eq bootps
 permit udp any eq bootpc host 10.10.43.10 eq bootps
 deny   ip any 10.0.0.0 0.255.255.255 log
 deny   ip any 172.16.0.0 0.15.255.255 log
 deny   ip any 192.168.0.0 0.0.255.255 log
 permit ip any any
!
router ospf 10
 router-id 10.10.255.4
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet1/0
 no passive-interface GigabitEthernet1/1
 no passive-interface Vlan900
 no passive-interface GigabitEthernet1/2
!
ipv6 router ospf 10
 router-id 10.10.255.4
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet1/0
 no passive-interface GigabitEthernet1/1
 no passive-interface Vlan900
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.8. Thiết bị `HCM-ACC1` — Switch Access L2 tại TP.HCM (Cisco vIOS Switch)

Mở Console của **`HCM-ACC1`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- HCM-ACC1
! Platform: viosl2   Role: access   Site: HCM
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname HCM-ACC1
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
no ip routing
ip default-gateway 10.10.44.1
!
vtp mode transparent
!
spanning-tree mode rapid-pvst
spanning-tree extend system-id
!
vlan 10
 name EXEC_FINANCE
vlan 12
 name CORP_STAFF
vlan 40
 name VOICE
vlan 60
 name GUEST
vlan 70
 name WLAN_AP
vlan 80
 name SERVERS
vlan 99
 name MANAGEMENT
vlan 999
 name NATIVE_UNUSED
!
ip dhcp snooping vlan 10,12,40,60
no ip dhcp snooping information option
ip dhcp snooping
ip arp inspection vlan 10,12,40,60
ip arp inspection validate src-mac dst-mac
ip arp inspection log-buffer entries 64
errdisable recovery cause bpduguard
errdisable recovery cause psecure-violation
errdisable recovery interval 120
!
interface GigabitEthernet0/1
 description Uplink trunk -> HCM-CORE1 Gi0/3
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 10,12,40,60,70,80,99
 switchport nonegotiate
 ip dhcp snooping trust
 ip arp inspection trust
 no shutdown
!
interface GigabitEthernet0/2
 description Uplink trunk -> HCM-CORE2 Gi0/3
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 10,12,40,60,70,80,99
 switchport nonegotiate
 ip dhcp snooping trust
 ip arp inspection trust
 no shutdown
!
interface GigabitEthernet1/0
 description Access -> PC-HCM-EXEC eth0 (VLAN 10 EXEC_FINANCE)
 switchport mode access
 switchport access vlan 10
 switchport voice vlan 40
 switchport nonegotiate
 switchport port-security maximum 3
 switchport port-security violation restrict
 switchport port-security mac-address sticky
 switchport port-security
 spanning-tree portfast
 spanning-tree bpduguard enable
 ip dhcp snooping limit rate 15
 no shutdown
!
interface GigabitEthernet1/1
 description Access -> PC-HCM-CORP eth0 (VLAN 12 CORP_STAFF)
 switchport mode access
 switchport access vlan 12
 switchport voice vlan 40
 switchport nonegotiate
 switchport port-security maximum 3
 switchport port-security violation restrict
 switchport port-security mac-address sticky
 switchport port-security
 spanning-tree portfast
 spanning-tree bpduguard enable
 ip dhcp snooping limit rate 15
 no shutdown
!
interface GigabitEthernet1/2
 description Access -> PC-HCM-GUEST eth0 (VLAN 60 GUEST)
 switchport mode access
 switchport access vlan 60
 switchport nonegotiate
 switchport port-security maximum 2
 switchport port-security violation restrict
 switchport port-security mac-address sticky
 switchport port-security
 spanning-tree portfast
 spanning-tree bpduguard enable
 ip dhcp snooping limit rate 15
 no shutdown
!
interface GigabitEthernet1/3
 description Access -> PC-HCM-PHONE eth0 (VLAN 40 VOICE)
 switchport mode access
 switchport access vlan 40
 switchport nonegotiate
 switchport port-security maximum 2
 switchport port-security violation restrict
 switchport port-security mac-address sticky
 switchport port-security
 spanning-tree portfast
 spanning-tree bpduguard enable
 ip dhcp snooping limit rate 15
 no shutdown
!
interface GigabitEthernet2/0
 description Access -> HCM-SRV1 Gi0/1 (VLAN 80 SERVERS)
 switchport mode access
 switchport access vlan 80
 switchport nonegotiate
 switchport port-security maximum 2
 switchport port-security violation restrict
 switchport port-security mac-address sticky
 switchport port-security
 spanning-tree portfast
 spanning-tree bpduguard enable
 no shutdown
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 no switchport
 ip address 172.16.99.15 255.255.255.0
 no cdp enable
 no shutdown
!
interface Vlan99
 description In-band management
 ip address 10.10.44.15 255.255.255.0
 no shutdown
!
interface Vlan1
 no ip address
 shutdown
!
interface GigabitEthernet0/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet2/1
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet2/2
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet2/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet3/0
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet3/1
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet3/2
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet3/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.9. Thiết bị `HAN-EDG1` — Router Biên & Gateway 1 tại Hà Nội (Cisco vIOS Router)

Mở Console của **`HAN-EDG1`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- HAN-EDG1
! Platform: vios   Role: edge   Site: HAN
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname HAN-EDG1
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
ipv6 unicast-routing
ipv6 cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
! ---------------- IPsec (IKEv2) protecting the GRE overlay ----------------
crypto ikev2 proposal TVI-IKEV2-PROP
 encryption aes-cbc-256
 integrity sha256
 group 14
crypto ikev2 policy TVI-IKEV2-POL
 proposal TVI-IKEV2-PROP
crypto ikev2 keyring TVI-KEYRING
 peer ANY-SITE
  address 0.0.0.0 0.0.0.0
  pre-shared-key TVI-Overlay-PSK-2026
crypto ikev2 profile TVI-IKEV2-PROFILE
 match identity remote address 0.0.0.0
 authentication remote pre-share
 authentication local pre-share
 keyring local TVI-KEYRING
 dpd 10 3 on-demand
!
crypto ipsec transform-set TVI-TS esp-aes 256 esp-sha256-hmac
 mode transport
crypto ipsec profile TVI-IPSEC-PROFILE
 set transform-set TVI-TS
 set ikev2-profile TVI-IKEV2-PROFILE
!
! ---------------- Zone-based firewall ----------------
zone security INSIDE
 description LAN, site interconnects and overlay tunnels
zone security OUTSIDE
 description ISP transport (untrusted)
!
class-map type inspect match-any CM-INSIDE-TO-OUTSIDE
 match protocol tcp
 match protocol udp
 match protocol icmp
policy-map type inspect PM-INSIDE-TO-OUTSIDE
 class type inspect CM-INSIDE-TO-OUTSIDE
  inspect
 class class-default
  drop log
!
ip access-list extended ACL-OUTSIDE-TO-SELF
 remark Control plane allowed from the ISP: IKE/IPsec, GRE, BGP, ICMP
 permit udp any any eq isakmp
 permit udp any any eq non500-isakmp
 permit esp any any
 permit gre any any
 permit tcp any any eq bgp
 permit tcp any eq bgp any
 permit icmp any any
class-map type inspect match-any CM-OUTSIDE-TO-SELF
 match access-group name ACL-OUTSIDE-TO-SELF
policy-map type inspect PM-OUTSIDE-TO-SELF
 class type inspect CM-OUTSIDE-TO-SELF
  pass
 class class-default
  drop log
!
zone-pair security ZP-INSIDE-OUTSIDE source INSIDE destination OUTSIDE
 service-policy type inspect PM-INSIDE-TO-OUTSIDE
zone-pair security ZP-OUTSIDE-SELF source OUTSIDE destination self
 service-policy type inspect PM-OUTSIDE-TO-SELF
!
! ---------------- QoS: classify & mark at the WAN-edge LAN side ----------------
ip access-list extended ACL-QOS-RTP
 remark RTP media (VoIP) -- also matches the IP SLA udp-jitter probes
 permit udp 10.0.0.0 0.255.255.255 any range 16384 32767
ip access-list extended ACL-QOS-SIGNALING
 permit udp 10.0.0.0 0.255.255.255 any range 5060 5061
 permit tcp 10.0.0.0 0.255.255.255 any range 5060 5061
ip access-list extended ACL-QOS-CRITICAL
 remark Executive/Finance and site-admin subnets
 permit ip 10.10.32.0 0.0.3.255 any
 permit ip 10.20.28.0 0.0.1.255 any
!
class-map match-any CM-IN-VOICE
 match access-group name ACL-QOS-RTP
class-map match-any CM-IN-SIGNALING
 match access-group name ACL-QOS-SIGNALING
class-map match-any CM-IN-CRITICAL
 match access-group name ACL-QOS-CRITICAL
!
policy-map PM-LAN-MARK-IN
 description Trust boundary: re-mark everything entering the WAN edge
 class CM-IN-VOICE
  set dscp ef
 class CM-IN-SIGNALING
  set dscp cs3
 class CM-IN-CRITICAL
  set dscp af31
 class class-default
  set dscp default
!
! ---------------- QoS: queue on the WAN transport (LLQ under a shaper) ----------
class-map match-any CM-WAN-VOICE
 match dscp ef
class-map match-any CM-WAN-SIGNALING
 match dscp cs3
class-map match-any CM-WAN-CRITICAL
 match dscp af31
!
policy-map PM-WAN-QUEUING
 class CM-WAN-VOICE
  priority percent 30
 class CM-WAN-SIGNALING
  bandwidth percent 5
 class CM-WAN-CRITICAL
  bandwidth percent 25
 class class-default
  fair-queue
!
policy-map PM-WAN-SHAPE
 description Shape to the 50 Mbps contracted WAN rate, then LLQ
 class class-default
  shape average 50000000
  service-policy PM-WAN-QUEUING
!
interface Loopback0
 description Router-ID / iBGP / management loopback
 ip address 10.20.255.1 255.255.255.255
 ipv6 address 2001:db8:a020:ff00::1/128
 ip ospf 20 area 0
 ipv6 ospf 20 area 0
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.21 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet0/1
 description WAN transport A -> ISP-A Gi0/2 (demarcation point)
 ip address 203.0.113.6 255.255.255.252
 ip nat outside
 zone-member security OUTSIDE
 no ip redirects
 no ip unreachables
 no ip proxy-arp
 no cdp enable
 service-policy output PM-WAN-SHAPE
 no shutdown
!
interface GigabitEthernet0/3
 description P2P -> HAN-EDG2 Gi0/3
 ip address 10.20.254.1 255.255.255.252
 ipv6 address 2001:db8:a020:fe01::1/64
 ip nat inside
 zone-member security INSIDE
 ip ospf network point-to-point
 ip ospf 20 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 20 area 0
 no shutdown
!
interface GigabitEthernet0/2
 description 802.1Q trunk -> HAN-ACC1 Gi0/1
 no ip address
 no shutdown
!
interface GigabitEthernet0/2.20
 description Gateway VLAN 20 RND_ENGINEERING
 encapsulation dot1Q 20
 ip address 10.20.0.2 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a020:2001::2/64
 ipv6 ospf 20 area 0
 ip ospf 20 area 0
 standby version 2
 standby 20 ip 10.20.0.1
 standby 20 priority 110
 standby 20 preempt delay minimum 10
 standby 20 timers 1 3
 standby 20 name HSRP-V20
 standby 1020 ipv6 FE80::1
 standby 1020 priority 110
 standby 1020 preempt delay minimum 10
 standby 1020 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.40
 description Gateway VLAN 40 VOICE
 encapsulation dot1Q 40
 ip address 10.20.16.2 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a020:4001::2/64
 ipv6 ospf 20 area 0
 ip ospf 20 area 0
 standby version 2
 standby 40 ip 10.20.16.1
 standby 40 priority 100
 standby 40 preempt delay minimum 10
 standby 40 timers 1 3
 standby 40 name HSRP-V40
 standby 1040 ipv6 FE80::1
 standby 1040 priority 100
 standby 1040 preempt delay minimum 10
 standby 1040 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.60
 description Gateway VLAN 60 GUEST
 encapsulation dot1Q 60
 ip address 10.20.24.2 255.255.255.0
 ip helper-address 10.10.43.10
 ip access-group ACL-GUEST-IN in
 no ip redirects
 ip ospf 20 area 0
 standby version 2
 standby 60 ip 10.20.24.1
 standby 60 priority 100
 standby 60 preempt delay minimum 10
 standby 60 timers 1 3
 standby 60 name HSRP-V60
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.99
 description Gateway VLAN 99 MANAGEMENT
 encapsulation dot1Q 99
 ip address 10.20.31.2 255.255.255.0
 no ip redirects
 ipv6 address 2001:db8:a020:9901::2/64
 ipv6 ospf 20 area 0
 ip ospf 20 area 0
 standby version 2
 standby 99 ip 10.20.31.1
 standby 99 priority 110
 standby 99 preempt delay minimum 10
 standby 99 timers 1 3
 standby 99 name HSRP-V99
 standby 1099 ipv6 FE80::1
 standby 1099 priority 110
 standby 1099 preempt delay minimum 10
 standby 1099 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface Tunnel11
 description Overlay plane A -> HCM-EDG1 Tunnel11 (GRE/IPsec)
 bandwidth 50000
 ip address 10.0.0.2 255.255.255.252
 ip mtu 1400
 ip tcp adjust-mss 1360
 ipv6 address 2001:db8:a000:11::2/64
 ipv6 mtu 1400
 zone-member security INSIDE
 qos pre-classify
 tunnel source GigabitEthernet0/1
 tunnel destination 203.0.113.2
 tunnel protection ipsec profile TVI-IPSEC-PROFILE
!
interface Tunnel13
 description Overlay plane A -> DAD-EDG1 Tunnel13 (GRE/IPsec)
 bandwidth 50000
 ip address 10.0.0.17 255.255.255.252
 ip mtu 1400
 ip tcp adjust-mss 1360
 ipv6 address 2001:db8:a000:13::1/64
 ipv6 mtu 1400
 zone-member security INSIDE
 qos pre-classify
 tunnel source GigabitEthernet0/1
 tunnel destination 203.0.113.10
 tunnel protection ipsec profile TVI-IPSEC-PROFILE
!
ip access-list extended ACL-GUEST-IN
 remark GUEST: DHCP + Internet only. No RFC1918 destination, no infrastructure.
 permit udp any eq bootpc any eq bootps
 permit udp any eq bootpc host 10.10.43.10 eq bootps
 deny   ip any 10.0.0.0 0.255.255.255 log
 deny   ip any 172.16.0.0 0.15.255.255 log
 deny   ip any 192.168.0.0 0.0.255.255 log
 permit ip any any
!
ip access-list extended ACL-NAT
 remark PAT for Internet-bound traffic only; site-to-site traffic is never translated
 deny   ip 10.0.0.0 0.255.255.255 10.0.0.0 0.255.255.255
 permit ip 10.20.0.0 0.0.255.255 any
ip nat inside source list ACL-NAT interface GigabitEthernet0/1 overload
!
ip route 10.20.0.0 255.255.0.0 Null0 254 name SITE-AGGREGATE
ipv6 route 2001:db8:a020::/48 Null0 254
!
ip prefix-list PL-DEFAULT-ONLY seq 5 permit 0.0.0.0/0
ip prefix-list PL-DENY-ALL seq 5 deny 0.0.0.0/0 le 32
ip prefix-list PL-ENTERPRISE-IN seq 5 permit 10.0.0.0/8 ge 16 le 24
ip prefix-list PL-SITE-OUT seq 5 permit 10.20.0.0/16
ipv6 prefix-list PL6-ENTERPRISE-IN seq 5 permit 2001:db8:a000::/40 ge 48 le 48
ipv6 prefix-list PL6-SITE-OUT seq 5 permit 2001:db8:a020::/48
!
router ospf 20
 router-id 10.20.255.1
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/3
!
ipv6 router ospf 20
 router-id 10.20.255.1
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/3
!
router bgp 65020
 bgp router-id 10.20.255.1
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 neighbor 203.0.113.5 remote-as 65100
 neighbor 203.0.113.5 description eBGP ISP-A (Internet transport A)
 neighbor 10.20.255.2 remote-as 65020
 neighbor 10.20.255.2 description iBGP HAN-EDG2
 neighbor 10.20.255.2 update-source Loopback0
 neighbor 2001:db8:a020:ff00::2 remote-as 65020
 neighbor 2001:db8:a020:ff00::2 description iBGP-v6 HAN-EDG2
 neighbor 2001:db8:a020:ff00::2 update-source Loopback0
 neighbor 10.0.0.1 remote-as 65010
 neighbor 10.0.0.1 description eBGP overlay HCM-EDG1 via Tunnel11
 neighbor 10.0.0.1 timers 5 15
 neighbor 2001:db8:a000:11::1 remote-as 65010
 neighbor 2001:db8:a000:11::1 description eBGP-v6 overlay HCM-EDG1 via Tunnel11
 neighbor 2001:db8:a000:11::1 timers 5 15
 neighbor 10.0.0.18 remote-as 65030
 neighbor 10.0.0.18 description eBGP overlay DAD-EDG1 via Tunnel13
 neighbor 10.0.0.18 timers 5 15
 neighbor 2001:db8:a000:13::2 remote-as 65030
 neighbor 2001:db8:a000:13::2 description eBGP-v6 overlay DAD-EDG1 via Tunnel13
 neighbor 2001:db8:a000:13::2 timers 5 15
 !
 address-family ipv4
  network 10.20.0.0 mask 255.255.0.0
  neighbor 203.0.113.5 activate
  neighbor 203.0.113.5 prefix-list PL-DEFAULT-ONLY in
  neighbor 203.0.113.5 prefix-list PL-DENY-ALL out
  neighbor 10.20.255.2 activate
  neighbor 10.20.255.2 next-hop-self
  neighbor 10.0.0.1 activate
  neighbor 10.0.0.1 prefix-list PL-ENTERPRISE-IN in
  neighbor 10.0.0.1 prefix-list PL-SITE-OUT out
  neighbor 10.0.0.18 activate
  neighbor 10.0.0.18 prefix-list PL-ENTERPRISE-IN in
  neighbor 10.0.0.18 prefix-list PL-SITE-OUT out
 exit-address-family
 !
 address-family ipv6
  network 2001:db8:a020::/48
  neighbor 2001:db8:a020:ff00::2 activate
  neighbor 2001:db8:a020:ff00::2 next-hop-self
  neighbor 2001:db8:a000:11::1 activate
  neighbor 2001:db8:a000:11::1 prefix-list PL6-ENTERPRISE-IN in
  neighbor 2001:db8:a000:11::1 prefix-list PL6-SITE-OUT out
  neighbor 2001:db8:a000:13::2 activate
  neighbor 2001:db8:a000:13::2 prefix-list PL6-ENTERPRISE-IN in
  neighbor 2001:db8:a000:13::2 prefix-list PL6-SITE-OUT out
 exit-address-family
!
ip sla responder
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.10. Thiết bị `HAN-EDG2` — Router Biên & Gateway 2 tại Hà Nội (Cisco vIOS Router)

Mở Console của **`HAN-EDG2`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- HAN-EDG2
! Platform: vios   Role: edge   Site: HAN
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname HAN-EDG2
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
ipv6 unicast-routing
ipv6 cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
! ---------------- IPsec (IKEv2) protecting the GRE overlay ----------------
crypto ikev2 proposal TVI-IKEV2-PROP
 encryption aes-cbc-256
 integrity sha256
 group 14
crypto ikev2 policy TVI-IKEV2-POL
 proposal TVI-IKEV2-PROP
crypto ikev2 keyring TVI-KEYRING
 peer ANY-SITE
  address 0.0.0.0 0.0.0.0
  pre-shared-key TVI-Overlay-PSK-2026
crypto ikev2 profile TVI-IKEV2-PROFILE
 match identity remote address 0.0.0.0
 authentication remote pre-share
 authentication local pre-share
 keyring local TVI-KEYRING
 dpd 10 3 on-demand
!
crypto ipsec transform-set TVI-TS esp-aes 256 esp-sha256-hmac
 mode transport
crypto ipsec profile TVI-IPSEC-PROFILE
 set transform-set TVI-TS
 set ikev2-profile TVI-IKEV2-PROFILE
!
! ---------------- Zone-based firewall ----------------
zone security INSIDE
 description LAN, site interconnects and overlay tunnels
zone security OUTSIDE
 description ISP transport (untrusted)
!
class-map type inspect match-any CM-INSIDE-TO-OUTSIDE
 match protocol tcp
 match protocol udp
 match protocol icmp
policy-map type inspect PM-INSIDE-TO-OUTSIDE
 class type inspect CM-INSIDE-TO-OUTSIDE
  inspect
 class class-default
  drop log
!
ip access-list extended ACL-OUTSIDE-TO-SELF
 remark Control plane allowed from the ISP: IKE/IPsec, GRE, BGP, ICMP
 permit udp any any eq isakmp
 permit udp any any eq non500-isakmp
 permit esp any any
 permit gre any any
 permit tcp any any eq bgp
 permit tcp any eq bgp any
 permit icmp any any
class-map type inspect match-any CM-OUTSIDE-TO-SELF
 match access-group name ACL-OUTSIDE-TO-SELF
policy-map type inspect PM-OUTSIDE-TO-SELF
 class type inspect CM-OUTSIDE-TO-SELF
  pass
 class class-default
  drop log
!
zone-pair security ZP-INSIDE-OUTSIDE source INSIDE destination OUTSIDE
 service-policy type inspect PM-INSIDE-TO-OUTSIDE
zone-pair security ZP-OUTSIDE-SELF source OUTSIDE destination self
 service-policy type inspect PM-OUTSIDE-TO-SELF
!
! ---------------- QoS: classify & mark at the WAN-edge LAN side ----------------
ip access-list extended ACL-QOS-RTP
 remark RTP media (VoIP) -- also matches the IP SLA udp-jitter probes
 permit udp 10.0.0.0 0.255.255.255 any range 16384 32767
ip access-list extended ACL-QOS-SIGNALING
 permit udp 10.0.0.0 0.255.255.255 any range 5060 5061
 permit tcp 10.0.0.0 0.255.255.255 any range 5060 5061
ip access-list extended ACL-QOS-CRITICAL
 remark Executive/Finance and site-admin subnets
 permit ip 10.10.32.0 0.0.3.255 any
 permit ip 10.20.28.0 0.0.1.255 any
!
class-map match-any CM-IN-VOICE
 match access-group name ACL-QOS-RTP
class-map match-any CM-IN-SIGNALING
 match access-group name ACL-QOS-SIGNALING
class-map match-any CM-IN-CRITICAL
 match access-group name ACL-QOS-CRITICAL
!
policy-map PM-LAN-MARK-IN
 description Trust boundary: re-mark everything entering the WAN edge
 class CM-IN-VOICE
  set dscp ef
 class CM-IN-SIGNALING
  set dscp cs3
 class CM-IN-CRITICAL
  set dscp af31
 class class-default
  set dscp default
!
! ---------------- QoS: queue on the WAN transport (LLQ under a shaper) ----------
class-map match-any CM-WAN-VOICE
 match dscp ef
class-map match-any CM-WAN-SIGNALING
 match dscp cs3
class-map match-any CM-WAN-CRITICAL
 match dscp af31
!
policy-map PM-WAN-QUEUING
 class CM-WAN-VOICE
  priority percent 30
 class CM-WAN-SIGNALING
  bandwidth percent 5
 class CM-WAN-CRITICAL
  bandwidth percent 25
 class class-default
  fair-queue
!
policy-map PM-WAN-SHAPE
 description Shape to the 50 Mbps contracted WAN rate, then LLQ
 class class-default
  shape average 50000000
  service-policy PM-WAN-QUEUING
!
interface Loopback0
 description Router-ID / iBGP / management loopback
 ip address 10.20.255.2 255.255.255.255
 ipv6 address 2001:db8:a020:ff00::2/128
 ip ospf 20 area 0
 ipv6 ospf 20 area 0
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.22 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet0/1
 description WAN transport B -> ISP-B Gi0/2 (demarcation point)
 ip address 198.51.100.6 255.255.255.252
 ip nat outside
 zone-member security OUTSIDE
 no ip redirects
 no ip unreachables
 no ip proxy-arp
 no cdp enable
 service-policy output PM-WAN-SHAPE
 no shutdown
!
interface GigabitEthernet0/3
 description P2P -> HAN-EDG1 Gi0/3
 ip address 10.20.254.2 255.255.255.252
 ipv6 address 2001:db8:a020:fe01::2/64
 ip nat inside
 zone-member security INSIDE
 ip ospf network point-to-point
 ip ospf 20 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 20 area 0
 no shutdown
!
interface GigabitEthernet0/2
 description 802.1Q trunk -> HAN-ACC1 Gi0/2
 no ip address
 no shutdown
!
interface GigabitEthernet0/2.20
 description Gateway VLAN 20 RND_ENGINEERING
 encapsulation dot1Q 20
 ip address 10.20.0.3 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a020:2001::3/64
 ipv6 ospf 20 area 0
 ip ospf 20 area 0
 standby version 2
 standby 20 ip 10.20.0.1
 standby 20 priority 100
 standby 20 preempt delay minimum 10
 standby 20 timers 1 3
 standby 20 name HSRP-V20
 standby 1020 ipv6 FE80::1
 standby 1020 priority 100
 standby 1020 preempt delay minimum 10
 standby 1020 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.40
 description Gateway VLAN 40 VOICE
 encapsulation dot1Q 40
 ip address 10.20.16.3 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a020:4001::3/64
 ipv6 ospf 20 area 0
 ip ospf 20 area 0
 standby version 2
 standby 40 ip 10.20.16.1
 standby 40 priority 110
 standby 40 preempt delay minimum 10
 standby 40 timers 1 3
 standby 40 name HSRP-V40
 standby 1040 ipv6 FE80::1
 standby 1040 priority 110
 standby 1040 preempt delay minimum 10
 standby 1040 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.60
 description Gateway VLAN 60 GUEST
 encapsulation dot1Q 60
 ip address 10.20.24.3 255.255.255.0
 ip helper-address 10.10.43.10
 ip access-group ACL-GUEST-IN in
 no ip redirects
 ip ospf 20 area 0
 standby version 2
 standby 60 ip 10.20.24.1
 standby 60 priority 110
 standby 60 preempt delay minimum 10
 standby 60 timers 1 3
 standby 60 name HSRP-V60
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.99
 description Gateway VLAN 99 MANAGEMENT
 encapsulation dot1Q 99
 ip address 10.20.31.3 255.255.255.0
 no ip redirects
 ipv6 address 2001:db8:a020:9901::3/64
 ipv6 ospf 20 area 0
 ip ospf 20 area 0
 standby version 2
 standby 99 ip 10.20.31.1
 standby 99 priority 100
 standby 99 preempt delay minimum 10
 standby 99 timers 1 3
 standby 99 name HSRP-V99
 standby 1099 ipv6 FE80::1
 standby 1099 priority 100
 standby 1099 preempt delay minimum 10
 standby 1099 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface Tunnel21
 description Overlay plane B -> HCM-EDG2 Tunnel21 (GRE/IPsec)
 bandwidth 50000
 ip address 10.0.0.10 255.255.255.252
 ip mtu 1400
 ip tcp adjust-mss 1360
 ipv6 address 2001:db8:a000:21::2/64
 ipv6 mtu 1400
 zone-member security INSIDE
 qos pre-classify
 tunnel source GigabitEthernet0/1
 tunnel destination 198.51.100.2
 tunnel protection ipsec profile TVI-IPSEC-PROFILE
!
interface Tunnel23
 description Overlay plane B -> DAD-EDG2 Tunnel23 (GRE/IPsec)
 bandwidth 50000
 ip address 10.0.0.21 255.255.255.252
 ip mtu 1400
 ip tcp adjust-mss 1360
 ipv6 address 2001:db8:a000:23::1/64
 ipv6 mtu 1400
 zone-member security INSIDE
 qos pre-classify
 tunnel source GigabitEthernet0/1
 tunnel destination 198.51.100.10
 tunnel protection ipsec profile TVI-IPSEC-PROFILE
!
ip access-list extended ACL-GUEST-IN
 remark GUEST: DHCP + Internet only. No RFC1918 destination, no infrastructure.
 permit udp any eq bootpc any eq bootps
 permit udp any eq bootpc host 10.10.43.10 eq bootps
 deny   ip any 10.0.0.0 0.255.255.255 log
 deny   ip any 172.16.0.0 0.15.255.255 log
 deny   ip any 192.168.0.0 0.0.255.255 log
 permit ip any any
!
ip access-list extended ACL-NAT
 remark PAT for Internet-bound traffic only; site-to-site traffic is never translated
 deny   ip 10.0.0.0 0.255.255.255 10.0.0.0 0.255.255.255
 permit ip 10.20.0.0 0.0.255.255 any
ip nat inside source list ACL-NAT interface GigabitEthernet0/1 overload
!
ip route 10.20.0.0 255.255.0.0 Null0 254 name SITE-AGGREGATE
ipv6 route 2001:db8:a020::/48 Null0 254
!
ip prefix-list PL-DEFAULT-ONLY seq 5 permit 0.0.0.0/0
ip prefix-list PL-DENY-ALL seq 5 deny 0.0.0.0/0 le 32
ip prefix-list PL-ENTERPRISE-IN seq 5 permit 10.0.0.0/8 ge 16 le 24
ip prefix-list PL-SITE-OUT seq 5 permit 10.20.0.0/16
ipv6 prefix-list PL6-ENTERPRISE-IN seq 5 permit 2001:db8:a000::/40 ge 48 le 48
ipv6 prefix-list PL6-SITE-OUT seq 5 permit 2001:db8:a020::/48
!
router ospf 20
 router-id 10.20.255.2
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/3
!
ipv6 router ospf 20
 router-id 10.20.255.2
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/3
!
router bgp 65020
 bgp router-id 10.20.255.2
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 neighbor 198.51.100.5 remote-as 65200
 neighbor 198.51.100.5 description eBGP ISP-B (Internet transport B)
 neighbor 10.20.255.1 remote-as 65020
 neighbor 10.20.255.1 description iBGP HAN-EDG1
 neighbor 10.20.255.1 update-source Loopback0
 neighbor 2001:db8:a020:ff00::1 remote-as 65020
 neighbor 2001:db8:a020:ff00::1 description iBGP-v6 HAN-EDG1
 neighbor 2001:db8:a020:ff00::1 update-source Loopback0
 neighbor 10.0.0.9 remote-as 65010
 neighbor 10.0.0.9 description eBGP overlay HCM-EDG2 via Tunnel21
 neighbor 10.0.0.9 timers 5 15
 neighbor 2001:db8:a000:21::1 remote-as 65010
 neighbor 2001:db8:a000:21::1 description eBGP-v6 overlay HCM-EDG2 via Tunnel21
 neighbor 2001:db8:a000:21::1 timers 5 15
 neighbor 10.0.0.22 remote-as 65030
 neighbor 10.0.0.22 description eBGP overlay DAD-EDG2 via Tunnel23
 neighbor 10.0.0.22 timers 5 15
 neighbor 2001:db8:a000:23::2 remote-as 65030
 neighbor 2001:db8:a000:23::2 description eBGP-v6 overlay DAD-EDG2 via Tunnel23
 neighbor 2001:db8:a000:23::2 timers 5 15
 !
 address-family ipv4
  network 10.20.0.0 mask 255.255.0.0
  neighbor 198.51.100.5 activate
  neighbor 198.51.100.5 prefix-list PL-DEFAULT-ONLY in
  neighbor 198.51.100.5 prefix-list PL-DENY-ALL out
  neighbor 10.20.255.1 activate
  neighbor 10.20.255.1 next-hop-self
  neighbor 10.0.0.9 activate
  neighbor 10.0.0.9 prefix-list PL-ENTERPRISE-IN in
  neighbor 10.0.0.9 prefix-list PL-SITE-OUT out
  neighbor 10.0.0.22 activate
  neighbor 10.0.0.22 prefix-list PL-ENTERPRISE-IN in
  neighbor 10.0.0.22 prefix-list PL-SITE-OUT out
 exit-address-family
 !
 address-family ipv6
  network 2001:db8:a020::/48
  neighbor 2001:db8:a020:ff00::1 activate
  neighbor 2001:db8:a020:ff00::1 next-hop-self
  neighbor 2001:db8:a000:21::1 activate
  neighbor 2001:db8:a000:21::1 prefix-list PL6-ENTERPRISE-IN in
  neighbor 2001:db8:a000:21::1 prefix-list PL6-SITE-OUT out
  neighbor 2001:db8:a000:23::2 activate
  neighbor 2001:db8:a000:23::2 prefix-list PL6-ENTERPRISE-IN in
  neighbor 2001:db8:a000:23::2 prefix-list PL6-SITE-OUT out
 exit-address-family
!
ip sla responder
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.11. Thiết bị `HAN-ACC1` — Switch Access L2 tại Hà Nội (Cisco vIOS Switch)

Mở Console của **`HAN-ACC1`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- HAN-ACC1
! Platform: viosl2   Role: access   Site: HAN
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname HAN-ACC1
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
no ip routing
ip default-gateway 10.20.31.1
!
vtp mode transparent
!
spanning-tree mode rapid-pvst
spanning-tree extend system-id
spanning-tree vlan 20,40,60,99 priority 24576
!
vlan 20
 name RND_ENGINEERING
vlan 40
 name VOICE
vlan 60
 name GUEST
vlan 99
 name MANAGEMENT
vlan 999
 name NATIVE_UNUSED
!
ip dhcp snooping vlan 20,40,60
no ip dhcp snooping information option
ip dhcp snooping
ip arp inspection vlan 20,40,60
ip arp inspection validate src-mac dst-mac
ip arp inspection log-buffer entries 64
errdisable recovery cause bpduguard
errdisable recovery cause psecure-violation
errdisable recovery interval 120
!
interface GigabitEthernet0/1
 description Uplink trunk -> HAN-EDG1 Gi0/2
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 20,40,60,99
 switchport nonegotiate
 ip dhcp snooping trust
 ip arp inspection trust
 no shutdown
!
interface GigabitEthernet0/2
 description Uplink trunk -> HAN-EDG2 Gi0/2
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 20,40,60,99
 switchport nonegotiate
 ip dhcp snooping trust
 ip arp inspection trust
 no shutdown
!
interface GigabitEthernet1/0
 description Access -> PC-HAN-ENG eth0 (VLAN 20 RND_ENGINEERING)
 switchport mode access
 switchport access vlan 20
 switchport voice vlan 40
 switchport nonegotiate
 switchport port-security maximum 3
 switchport port-security violation restrict
 switchport port-security mac-address sticky
 switchport port-security
 spanning-tree portfast
 spanning-tree bpduguard enable
 ip dhcp snooping limit rate 15
 no shutdown
!
interface GigabitEthernet1/1
 description Access -> PC-HAN-PHONE eth0 (VLAN 40 VOICE)
 switchport mode access
 switchport access vlan 40
 switchport nonegotiate
 switchport port-security maximum 2
 switchport port-security violation restrict
 switchport port-security mac-address sticky
 switchport port-security
 spanning-tree portfast
 spanning-tree bpduguard enable
 ip dhcp snooping limit rate 15
 no shutdown
!
interface GigabitEthernet1/2
 description Access -> PC-HAN-GUEST eth0 (VLAN 60 GUEST)
 switchport mode access
 switchport access vlan 60
 switchport nonegotiate
 switchport port-security maximum 2
 switchport port-security violation restrict
 switchport port-security mac-address sticky
 switchport port-security
 spanning-tree portfast
 spanning-tree bpduguard enable
 ip dhcp snooping limit rate 15
 no shutdown
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 no switchport
 ip address 172.16.99.25 255.255.255.0
 no cdp enable
 no shutdown
!
interface Vlan99
 description In-band management
 ip address 10.20.31.15 255.255.255.0
 no shutdown
!
interface Vlan1
 no ip address
 shutdown
!
interface GigabitEthernet0/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet1/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet2/0
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet2/1
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet2/2
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet2/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet3/0
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet3/1
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet3/2
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet3/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.12. Thiết bị `DAD-EDG1` — Router Biên & Gateway 1 tại Đà Nẵng (Cisco vIOS Router)

Mở Console của **`DAD-EDG1`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- DAD-EDG1
! Platform: vios   Role: edge   Site: DAD
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname DAD-EDG1
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
ipv6 unicast-routing
ipv6 cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
! ---------------- IPsec (IKEv2) protecting the GRE overlay ----------------
crypto ikev2 proposal TVI-IKEV2-PROP
 encryption aes-cbc-256
 integrity sha256
 group 14
crypto ikev2 policy TVI-IKEV2-POL
 proposal TVI-IKEV2-PROP
crypto ikev2 keyring TVI-KEYRING
 peer ANY-SITE
  address 0.0.0.0 0.0.0.0
  pre-shared-key TVI-Overlay-PSK-2026
crypto ikev2 profile TVI-IKEV2-PROFILE
 match identity remote address 0.0.0.0
 authentication remote pre-share
 authentication local pre-share
 keyring local TVI-KEYRING
 dpd 10 3 on-demand
!
crypto ipsec transform-set TVI-TS esp-aes 256 esp-sha256-hmac
 mode transport
crypto ipsec profile TVI-IPSEC-PROFILE
 set transform-set TVI-TS
 set ikev2-profile TVI-IKEV2-PROFILE
!
! ---------------- Zone-based firewall ----------------
zone security INSIDE
 description LAN, site interconnects and overlay tunnels
zone security OUTSIDE
 description ISP transport (untrusted)
!
class-map type inspect match-any CM-INSIDE-TO-OUTSIDE
 match protocol tcp
 match protocol udp
 match protocol icmp
policy-map type inspect PM-INSIDE-TO-OUTSIDE
 class type inspect CM-INSIDE-TO-OUTSIDE
  inspect
 class class-default
  drop log
!
ip access-list extended ACL-OUTSIDE-TO-SELF
 remark Control plane allowed from the ISP: IKE/IPsec, GRE, BGP, ICMP
 permit udp any any eq isakmp
 permit udp any any eq non500-isakmp
 permit esp any any
 permit gre any any
 permit tcp any any eq bgp
 permit tcp any eq bgp any
 permit icmp any any
class-map type inspect match-any CM-OUTSIDE-TO-SELF
 match access-group name ACL-OUTSIDE-TO-SELF
policy-map type inspect PM-OUTSIDE-TO-SELF
 class type inspect CM-OUTSIDE-TO-SELF
  pass
 class class-default
  drop log
!
zone-pair security ZP-INSIDE-OUTSIDE source INSIDE destination OUTSIDE
 service-policy type inspect PM-INSIDE-TO-OUTSIDE
zone-pair security ZP-OUTSIDE-SELF source OUTSIDE destination self
 service-policy type inspect PM-OUTSIDE-TO-SELF
!
! ---------------- QoS: classify & mark at the WAN-edge LAN side ----------------
ip access-list extended ACL-QOS-RTP
 remark RTP media (VoIP) -- also matches the IP SLA udp-jitter probes
 permit udp 10.0.0.0 0.255.255.255 any range 16384 32767
ip access-list extended ACL-QOS-SIGNALING
 permit udp 10.0.0.0 0.255.255.255 any range 5060 5061
 permit tcp 10.0.0.0 0.255.255.255 any range 5060 5061
ip access-list extended ACL-QOS-CRITICAL
 remark Executive/Finance and site-admin subnets
 permit ip 10.10.32.0 0.0.3.255 any
 permit ip 10.20.28.0 0.0.1.255 any
!
class-map match-any CM-IN-VOICE
 match access-group name ACL-QOS-RTP
class-map match-any CM-IN-SIGNALING
 match access-group name ACL-QOS-SIGNALING
class-map match-any CM-IN-CRITICAL
 match access-group name ACL-QOS-CRITICAL
!
policy-map PM-LAN-MARK-IN
 description Trust boundary: re-mark everything entering the WAN edge
 class CM-IN-VOICE
  set dscp ef
 class CM-IN-SIGNALING
  set dscp cs3
 class CM-IN-CRITICAL
  set dscp af31
 class class-default
  set dscp default
!
! ---------------- QoS: queue on the WAN transport (LLQ under a shaper) ----------
class-map match-any CM-WAN-VOICE
 match dscp ef
class-map match-any CM-WAN-SIGNALING
 match dscp cs3
class-map match-any CM-WAN-CRITICAL
 match dscp af31
!
policy-map PM-WAN-QUEUING
 class CM-WAN-VOICE
  priority percent 30
 class CM-WAN-SIGNALING
  bandwidth percent 5
 class CM-WAN-CRITICAL
  bandwidth percent 25
 class class-default
  fair-queue
!
policy-map PM-WAN-SHAPE
 description Shape to the 50 Mbps contracted WAN rate, then LLQ
 class class-default
  shape average 50000000
  service-policy PM-WAN-QUEUING
!
interface Loopback0
 description Router-ID / iBGP / management loopback
 ip address 10.30.255.1 255.255.255.255
 ipv6 address 2001:db8:a030:ff00::1/128
 ip ospf 30 area 0
 ipv6 ospf 30 area 0
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.31 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet0/1
 description WAN transport A -> ISP-A Gi0/3 (demarcation point)
 ip address 203.0.113.10 255.255.255.252
 ip nat outside
 zone-member security OUTSIDE
 no ip redirects
 no ip unreachables
 no ip proxy-arp
 no cdp enable
 service-policy output PM-WAN-SHAPE
 no shutdown
!
interface GigabitEthernet0/3
 description P2P -> DAD-EDG2 Gi0/3
 ip address 10.30.254.1 255.255.255.252
 ipv6 address 2001:db8:a030:fe01::1/64
 ip nat inside
 zone-member security INSIDE
 ip ospf network point-to-point
 ip ospf 30 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 30 area 0
 no shutdown
!
interface GigabitEthernet0/2
 description 802.1Q trunk -> DAD-ACC1 Gi0/1
 no ip address
 no shutdown
!
interface GigabitEthernet0/2.30
 description Gateway VLAN 30 LOGISTICS_OPS
 encapsulation dot1Q 30
 ip address 10.30.128.2 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a030:3001::2/64
 ipv6 ospf 30 area 0
 ip ospf 30 area 0
 standby version 2
 standby 30 ip 10.30.128.1
 standby 30 priority 110
 standby 30 preempt delay minimum 10
 standby 30 timers 1 3
 standby 30 name HSRP-V30
 standby 1030 ipv6 FE80::1
 standby 1030 priority 110
 standby 1030 preempt delay minimum 10
 standby 1030 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.40
 description Gateway VLAN 40 VOICE
 encapsulation dot1Q 40
 ip address 10.30.136.2 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a030:4001::2/64
 ipv6 ospf 30 area 0
 ip ospf 30 area 0
 standby version 2
 standby 40 ip 10.30.136.1
 standby 40 priority 100
 standby 40 preempt delay minimum 10
 standby 40 timers 1 3
 standby 40 name HSRP-V40
 standby 1040 ipv6 FE80::1
 standby 1040 priority 100
 standby 1040 preempt delay minimum 10
 standby 1040 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.50
 description Gateway VLAN 50 IOT_DEVICES
 encapsulation dot1Q 50
 ip address 10.30.0.2 255.255.255.0
 ip helper-address 10.10.43.10
 ip access-group ACL-IOT-IN in
 no ip redirects
 ipv6 address 2001:db8:a030:5001::2/64
 ipv6 traffic-filter ACL6-IOT-IN in
 ipv6 ospf 30 area 0
 ip ospf 30 area 0
 standby version 2
 standby 50 ip 10.30.0.1
 standby 50 priority 100
 standby 50 preempt delay minimum 10
 standby 50 timers 1 3
 standby 50 name HSRP-V50
 standby 1050 ipv6 FE80::1
 standby 1050 priority 100
 standby 1050 preempt delay minimum 10
 standby 1050 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.60
 description Gateway VLAN 60 GUEST
 encapsulation dot1Q 60
 ip address 10.30.140.2 255.255.255.0
 ip helper-address 10.10.43.10
 ip access-group ACL-GUEST-IN in
 no ip redirects
 ip ospf 30 area 0
 standby version 2
 standby 60 ip 10.30.140.1
 standby 60 priority 100
 standby 60 preempt delay minimum 10
 standby 60 timers 1 3
 standby 60 name HSRP-V60
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.99
 description Gateway VLAN 99 MANAGEMENT
 encapsulation dot1Q 99
 ip address 10.30.144.2 255.255.255.0
 no ip redirects
 ipv6 address 2001:db8:a030:9901::2/64
 ipv6 ospf 30 area 0
 ip ospf 30 area 0
 standby version 2
 standby 99 ip 10.30.144.1
 standby 99 priority 110
 standby 99 preempt delay minimum 10
 standby 99 timers 1 3
 standby 99 name HSRP-V99
 standby 1099 ipv6 FE80::1
 standby 1099 priority 110
 standby 1099 preempt delay minimum 10
 standby 1099 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface Tunnel12
 description Overlay plane A -> HCM-EDG1 Tunnel12 (GRE/IPsec)
 bandwidth 50000
 ip address 10.0.0.6 255.255.255.252
 ip mtu 1400
 ip tcp adjust-mss 1360
 ipv6 address 2001:db8:a000:12::2/64
 ipv6 mtu 1400
 zone-member security INSIDE
 qos pre-classify
 tunnel source GigabitEthernet0/1
 tunnel destination 203.0.113.2
 tunnel protection ipsec profile TVI-IPSEC-PROFILE
!
interface Tunnel13
 description Overlay plane A -> HAN-EDG1 Tunnel13 (GRE/IPsec)
 bandwidth 50000
 ip address 10.0.0.18 255.255.255.252
 ip mtu 1400
 ip tcp adjust-mss 1360
 ipv6 address 2001:db8:a000:13::2/64
 ipv6 mtu 1400
 zone-member security INSIDE
 qos pre-classify
 tunnel source GigabitEthernet0/1
 tunnel destination 203.0.113.6
 tunnel protection ipsec profile TVI-IPSEC-PROFILE
!
ip access-list extended ACL-GUEST-IN
 remark GUEST: DHCP + Internet only. No RFC1918 destination, no infrastructure.
 permit udp any eq bootpc any eq bootps
 permit udp any eq bootpc host 10.10.43.10 eq bootps
 deny   ip any 10.0.0.0 0.255.255.255 log
 deny   ip any 172.16.0.0 0.15.255.255 log
 deny   ip any 192.168.0.0 0.0.255.255 log
 permit ip any any
!
ip access-list extended ACL-IOT-IN
 remark IoT: DHCP/DNS/NTP + MQTT to the IoT platform at HQ + cloud IoT hub. Nothing else.
 permit udp any eq bootpc any eq bootps
 permit udp any eq bootpc host 10.10.43.10 eq bootps
 permit udp any host 10.10.43.10 eq domain
 permit udp any host 10.10.43.10 eq ntp
 permit tcp any 10.10.43.0 0.0.0.255 eq 1883
 permit tcp any 10.10.43.0 0.0.0.255 eq 8883
 permit icmp any 10.10.43.0 0.0.0.255
 permit tcp any host 192.0.2.10 eq 8883
 deny   ip any any log
!
ipv6 access-list ACL6-IOT-IN
 permit icmp any any nd-ns
 permit icmp any any nd-na
 permit icmp any any router-solicitation
 permit ipv6 any 2001:db8:a010:8001::/64
 deny   ipv6 any any log
!
ip access-list extended ACL-NAT
 remark PAT for Internet-bound traffic only; site-to-site traffic is never translated
 deny   ip 10.0.0.0 0.255.255.255 10.0.0.0 0.255.255.255
 permit ip 10.30.0.0 0.0.255.255 any
ip nat inside source list ACL-NAT interface GigabitEthernet0/1 overload
!
ip route 10.30.0.0 255.255.0.0 Null0 254 name SITE-AGGREGATE
ipv6 route 2001:db8:a030::/48 Null0 254
!
ip prefix-list PL-DEFAULT-ONLY seq 5 permit 0.0.0.0/0
ip prefix-list PL-DENY-ALL seq 5 deny 0.0.0.0/0 le 32
ip prefix-list PL-ENTERPRISE-IN seq 5 permit 10.0.0.0/8 ge 16 le 24
ip prefix-list PL-SITE-OUT seq 5 permit 10.30.0.0/16
ipv6 prefix-list PL6-ENTERPRISE-IN seq 5 permit 2001:db8:a000::/40 ge 48 le 48
ipv6 prefix-list PL6-SITE-OUT seq 5 permit 2001:db8:a030::/48
!
router ospf 30
 router-id 10.30.255.1
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/3
!
ipv6 router ospf 30
 router-id 10.30.255.1
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/3
!
router bgp 65030
 bgp router-id 10.30.255.1
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 neighbor 203.0.113.9 remote-as 65100
 neighbor 203.0.113.9 description eBGP ISP-A (Internet transport A)
 neighbor 10.30.255.2 remote-as 65030
 neighbor 10.30.255.2 description iBGP DAD-EDG2
 neighbor 10.30.255.2 update-source Loopback0
 neighbor 2001:db8:a030:ff00::2 remote-as 65030
 neighbor 2001:db8:a030:ff00::2 description iBGP-v6 DAD-EDG2
 neighbor 2001:db8:a030:ff00::2 update-source Loopback0
 neighbor 10.0.0.5 remote-as 65010
 neighbor 10.0.0.5 description eBGP overlay HCM-EDG1 via Tunnel12
 neighbor 10.0.0.5 timers 5 15
 neighbor 2001:db8:a000:12::1 remote-as 65010
 neighbor 2001:db8:a000:12::1 description eBGP-v6 overlay HCM-EDG1 via Tunnel12
 neighbor 2001:db8:a000:12::1 timers 5 15
 neighbor 10.0.0.17 remote-as 65020
 neighbor 10.0.0.17 description eBGP overlay HAN-EDG1 via Tunnel13
 neighbor 10.0.0.17 timers 5 15
 neighbor 2001:db8:a000:13::1 remote-as 65020
 neighbor 2001:db8:a000:13::1 description eBGP-v6 overlay HAN-EDG1 via Tunnel13
 neighbor 2001:db8:a000:13::1 timers 5 15
 !
 address-family ipv4
  network 10.30.0.0 mask 255.255.0.0
  neighbor 203.0.113.9 activate
  neighbor 203.0.113.9 prefix-list PL-DEFAULT-ONLY in
  neighbor 203.0.113.9 prefix-list PL-DENY-ALL out
  neighbor 10.30.255.2 activate
  neighbor 10.30.255.2 next-hop-self
  neighbor 10.0.0.5 activate
  neighbor 10.0.0.5 prefix-list PL-ENTERPRISE-IN in
  neighbor 10.0.0.5 prefix-list PL-SITE-OUT out
  neighbor 10.0.0.17 activate
  neighbor 10.0.0.17 prefix-list PL-ENTERPRISE-IN in
  neighbor 10.0.0.17 prefix-list PL-SITE-OUT out
 exit-address-family
 !
 address-family ipv6
  network 2001:db8:a030::/48
  neighbor 2001:db8:a030:ff00::2 activate
  neighbor 2001:db8:a030:ff00::2 next-hop-self
  neighbor 2001:db8:a000:12::1 activate
  neighbor 2001:db8:a000:12::1 prefix-list PL6-ENTERPRISE-IN in
  neighbor 2001:db8:a000:12::1 prefix-list PL6-SITE-OUT out
  neighbor 2001:db8:a000:13::1 activate
  neighbor 2001:db8:a000:13::1 prefix-list PL6-ENTERPRISE-IN in
  neighbor 2001:db8:a000:13::1 prefix-list PL6-SITE-OUT out
 exit-address-family
!
ip sla responder
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.13. Thiết bị `DAD-EDG2` — Router Biên & Gateway 2 tại Đà Nẵng (Cisco vIOS Router)

Mở Console của **`DAD-EDG2`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- DAD-EDG2
! Platform: vios   Role: edge   Site: DAD
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname DAD-EDG2
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
ipv6 unicast-routing
ipv6 cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
! ---------------- IPsec (IKEv2) protecting the GRE overlay ----------------
crypto ikev2 proposal TVI-IKEV2-PROP
 encryption aes-cbc-256
 integrity sha256
 group 14
crypto ikev2 policy TVI-IKEV2-POL
 proposal TVI-IKEV2-PROP
crypto ikev2 keyring TVI-KEYRING
 peer ANY-SITE
  address 0.0.0.0 0.0.0.0
  pre-shared-key TVI-Overlay-PSK-2026
crypto ikev2 profile TVI-IKEV2-PROFILE
 match identity remote address 0.0.0.0
 authentication remote pre-share
 authentication local pre-share
 keyring local TVI-KEYRING
 dpd 10 3 on-demand
!
crypto ipsec transform-set TVI-TS esp-aes 256 esp-sha256-hmac
 mode transport
crypto ipsec profile TVI-IPSEC-PROFILE
 set transform-set TVI-TS
 set ikev2-profile TVI-IKEV2-PROFILE
!
! ---------------- Zone-based firewall ----------------
zone security INSIDE
 description LAN, site interconnects and overlay tunnels
zone security OUTSIDE
 description ISP transport (untrusted)
!
class-map type inspect match-any CM-INSIDE-TO-OUTSIDE
 match protocol tcp
 match protocol udp
 match protocol icmp
policy-map type inspect PM-INSIDE-TO-OUTSIDE
 class type inspect CM-INSIDE-TO-OUTSIDE
  inspect
 class class-default
  drop log
!
ip access-list extended ACL-OUTSIDE-TO-SELF
 remark Control plane allowed from the ISP: IKE/IPsec, GRE, BGP, ICMP
 permit udp any any eq isakmp
 permit udp any any eq non500-isakmp
 permit esp any any
 permit gre any any
 permit tcp any any eq bgp
 permit tcp any eq bgp any
 permit icmp any any
class-map type inspect match-any CM-OUTSIDE-TO-SELF
 match access-group name ACL-OUTSIDE-TO-SELF
policy-map type inspect PM-OUTSIDE-TO-SELF
 class type inspect CM-OUTSIDE-TO-SELF
  pass
 class class-default
  drop log
!
zone-pair security ZP-INSIDE-OUTSIDE source INSIDE destination OUTSIDE
 service-policy type inspect PM-INSIDE-TO-OUTSIDE
zone-pair security ZP-OUTSIDE-SELF source OUTSIDE destination self
 service-policy type inspect PM-OUTSIDE-TO-SELF
!
! ---------------- QoS: classify & mark at the WAN-edge LAN side ----------------
ip access-list extended ACL-QOS-RTP
 remark RTP media (VoIP) -- also matches the IP SLA udp-jitter probes
 permit udp 10.0.0.0 0.255.255.255 any range 16384 32767
ip access-list extended ACL-QOS-SIGNALING
 permit udp 10.0.0.0 0.255.255.255 any range 5060 5061
 permit tcp 10.0.0.0 0.255.255.255 any range 5060 5061
ip access-list extended ACL-QOS-CRITICAL
 remark Executive/Finance and site-admin subnets
 permit ip 10.10.32.0 0.0.3.255 any
 permit ip 10.20.28.0 0.0.1.255 any
!
class-map match-any CM-IN-VOICE
 match access-group name ACL-QOS-RTP
class-map match-any CM-IN-SIGNALING
 match access-group name ACL-QOS-SIGNALING
class-map match-any CM-IN-CRITICAL
 match access-group name ACL-QOS-CRITICAL
!
policy-map PM-LAN-MARK-IN
 description Trust boundary: re-mark everything entering the WAN edge
 class CM-IN-VOICE
  set dscp ef
 class CM-IN-SIGNALING
  set dscp cs3
 class CM-IN-CRITICAL
  set dscp af31
 class class-default
  set dscp default
!
! ---------------- QoS: queue on the WAN transport (LLQ under a shaper) ----------
class-map match-any CM-WAN-VOICE
 match dscp ef
class-map match-any CM-WAN-SIGNALING
 match dscp cs3
class-map match-any CM-WAN-CRITICAL
 match dscp af31
!
policy-map PM-WAN-QUEUING
 class CM-WAN-VOICE
  priority percent 30
 class CM-WAN-SIGNALING
  bandwidth percent 5
 class CM-WAN-CRITICAL
  bandwidth percent 25
 class class-default
  fair-queue
!
policy-map PM-WAN-SHAPE
 description Shape to the 50 Mbps contracted WAN rate, then LLQ
 class class-default
  shape average 50000000
  service-policy PM-WAN-QUEUING
!
interface Loopback0
 description Router-ID / iBGP / management loopback
 ip address 10.30.255.2 255.255.255.255
 ipv6 address 2001:db8:a030:ff00::2/128
 ip ospf 30 area 0
 ipv6 ospf 30 area 0
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.32 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet0/1
 description WAN transport B -> ISP-B Gi0/3 (demarcation point)
 ip address 198.51.100.10 255.255.255.252
 ip nat outside
 zone-member security OUTSIDE
 no ip redirects
 no ip unreachables
 no ip proxy-arp
 no cdp enable
 service-policy output PM-WAN-SHAPE
 no shutdown
!
interface GigabitEthernet0/3
 description P2P -> DAD-EDG1 Gi0/3
 ip address 10.30.254.2 255.255.255.252
 ipv6 address 2001:db8:a030:fe01::2/64
 ip nat inside
 zone-member security INSIDE
 ip ospf network point-to-point
 ip ospf 30 area 0
 ipv6 ospf network point-to-point
 ipv6 ospf 30 area 0
 no shutdown
!
interface GigabitEthernet0/2
 description 802.1Q trunk -> DAD-ACC1 Gi0/2
 no ip address
 no shutdown
!
interface GigabitEthernet0/2.30
 description Gateway VLAN 30 LOGISTICS_OPS
 encapsulation dot1Q 30
 ip address 10.30.128.3 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a030:3001::3/64
 ipv6 ospf 30 area 0
 ip ospf 30 area 0
 standby version 2
 standby 30 ip 10.30.128.1
 standby 30 priority 100
 standby 30 preempt delay minimum 10
 standby 30 timers 1 3
 standby 30 name HSRP-V30
 standby 1030 ipv6 FE80::1
 standby 1030 priority 100
 standby 1030 preempt delay minimum 10
 standby 1030 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.40
 description Gateway VLAN 40 VOICE
 encapsulation dot1Q 40
 ip address 10.30.136.3 255.255.255.0
 ip helper-address 10.10.43.10
 no ip redirects
 ipv6 address 2001:db8:a030:4001::3/64
 ipv6 ospf 30 area 0
 ip ospf 30 area 0
 standby version 2
 standby 40 ip 10.30.136.1
 standby 40 priority 110
 standby 40 preempt delay minimum 10
 standby 40 timers 1 3
 standby 40 name HSRP-V40
 standby 1040 ipv6 FE80::1
 standby 1040 priority 110
 standby 1040 preempt delay minimum 10
 standby 1040 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.50
 description Gateway VLAN 50 IOT_DEVICES
 encapsulation dot1Q 50
 ip address 10.30.0.3 255.255.255.0
 ip helper-address 10.10.43.10
 ip access-group ACL-IOT-IN in
 no ip redirects
 ipv6 address 2001:db8:a030:5001::3/64
 ipv6 traffic-filter ACL6-IOT-IN in
 ipv6 ospf 30 area 0
 ip ospf 30 area 0
 standby version 2
 standby 50 ip 10.30.0.1
 standby 50 priority 110
 standby 50 preempt delay minimum 10
 standby 50 timers 1 3
 standby 50 name HSRP-V50
 standby 1050 ipv6 FE80::1
 standby 1050 priority 110
 standby 1050 preempt delay minimum 10
 standby 1050 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.60
 description Gateway VLAN 60 GUEST
 encapsulation dot1Q 60
 ip address 10.30.140.3 255.255.255.0
 ip helper-address 10.10.43.10
 ip access-group ACL-GUEST-IN in
 no ip redirects
 ip ospf 30 area 0
 standby version 2
 standby 60 ip 10.30.140.1
 standby 60 priority 110
 standby 60 preempt delay minimum 10
 standby 60 timers 1 3
 standby 60 name HSRP-V60
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface GigabitEthernet0/2.99
 description Gateway VLAN 99 MANAGEMENT
 encapsulation dot1Q 99
 ip address 10.30.144.3 255.255.255.0
 no ip redirects
 ipv6 address 2001:db8:a030:9901::3/64
 ipv6 ospf 30 area 0
 ip ospf 30 area 0
 standby version 2
 standby 99 ip 10.30.144.1
 standby 99 priority 100
 standby 99 preempt delay minimum 10
 standby 99 timers 1 3
 standby 99 name HSRP-V99
 standby 1099 ipv6 FE80::1
 standby 1099 priority 100
 standby 1099 preempt delay minimum 10
 standby 1099 timers 1 3
 ip nat inside
 zone-member security INSIDE
 service-policy input PM-LAN-MARK-IN
!
interface Tunnel22
 description Overlay plane B -> HCM-EDG2 Tunnel22 (GRE/IPsec)
 bandwidth 50000
 ip address 10.0.0.14 255.255.255.252
 ip mtu 1400
 ip tcp adjust-mss 1360
 ipv6 address 2001:db8:a000:22::2/64
 ipv6 mtu 1400
 zone-member security INSIDE
 qos pre-classify
 tunnel source GigabitEthernet0/1
 tunnel destination 198.51.100.2
 tunnel protection ipsec profile TVI-IPSEC-PROFILE
!
interface Tunnel23
 description Overlay plane B -> HAN-EDG2 Tunnel23 (GRE/IPsec)
 bandwidth 50000
 ip address 10.0.0.22 255.255.255.252
 ip mtu 1400
 ip tcp adjust-mss 1360
 ipv6 address 2001:db8:a000:23::2/64
 ipv6 mtu 1400
 zone-member security INSIDE
 qos pre-classify
 tunnel source GigabitEthernet0/1
 tunnel destination 198.51.100.6
 tunnel protection ipsec profile TVI-IPSEC-PROFILE
!
ip access-list extended ACL-GUEST-IN
 remark GUEST: DHCP + Internet only. No RFC1918 destination, no infrastructure.
 permit udp any eq bootpc any eq bootps
 permit udp any eq bootpc host 10.10.43.10 eq bootps
 deny   ip any 10.0.0.0 0.255.255.255 log
 deny   ip any 172.16.0.0 0.15.255.255 log
 deny   ip any 192.168.0.0 0.0.255.255 log
 permit ip any any
!
ip access-list extended ACL-IOT-IN
 remark IoT: DHCP/DNS/NTP + MQTT to the IoT platform at HQ + cloud IoT hub. Nothing else.
 permit udp any eq bootpc any eq bootps
 permit udp any eq bootpc host 10.10.43.10 eq bootps
 permit udp any host 10.10.43.10 eq domain
 permit udp any host 10.10.43.10 eq ntp
 permit tcp any 10.10.43.0 0.0.0.255 eq 1883
 permit tcp any 10.10.43.0 0.0.0.255 eq 8883
 permit icmp any 10.10.43.0 0.0.0.255
 permit tcp any host 192.0.2.10 eq 8883
 deny   ip any any log
!
ipv6 access-list ACL6-IOT-IN
 permit icmp any any nd-ns
 permit icmp any any nd-na
 permit icmp any any router-solicitation
 permit ipv6 any 2001:db8:a010:8001::/64
 deny   ipv6 any any log
!
ip access-list extended ACL-NAT
 remark PAT for Internet-bound traffic only; site-to-site traffic is never translated
 deny   ip 10.0.0.0 0.255.255.255 10.0.0.0 0.255.255.255
 permit ip 10.30.0.0 0.0.255.255 any
ip nat inside source list ACL-NAT interface GigabitEthernet0/1 overload
!
ip route 10.30.0.0 255.255.0.0 Null0 254 name SITE-AGGREGATE
ipv6 route 2001:db8:a030::/48 Null0 254
!
ip prefix-list PL-DEFAULT-ONLY seq 5 permit 0.0.0.0/0
ip prefix-list PL-DENY-ALL seq 5 deny 0.0.0.0/0 le 32
ip prefix-list PL-ENTERPRISE-IN seq 5 permit 10.0.0.0/8 ge 16 le 24
ip prefix-list PL-SITE-OUT seq 5 permit 10.30.0.0/16
ipv6 prefix-list PL6-ENTERPRISE-IN seq 5 permit 2001:db8:a000::/40 ge 48 le 48
ipv6 prefix-list PL6-SITE-OUT seq 5 permit 2001:db8:a030::/48
!
router ospf 30
 router-id 10.30.255.2
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/3
!
ipv6 router ospf 30
 router-id 10.30.255.2
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/3
!
router bgp 65030
 bgp router-id 10.30.255.2
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 neighbor 198.51.100.9 remote-as 65200
 neighbor 198.51.100.9 description eBGP ISP-B (Internet transport B)
 neighbor 10.30.255.1 remote-as 65030
 neighbor 10.30.255.1 description iBGP DAD-EDG1
 neighbor 10.30.255.1 update-source Loopback0
 neighbor 2001:db8:a030:ff00::1 remote-as 65030
 neighbor 2001:db8:a030:ff00::1 description iBGP-v6 DAD-EDG1
 neighbor 2001:db8:a030:ff00::1 update-source Loopback0
 neighbor 10.0.0.13 remote-as 65010
 neighbor 10.0.0.13 description eBGP overlay HCM-EDG2 via Tunnel22
 neighbor 10.0.0.13 timers 5 15
 neighbor 2001:db8:a000:22::1 remote-as 65010
 neighbor 2001:db8:a000:22::1 description eBGP-v6 overlay HCM-EDG2 via Tunnel22
 neighbor 2001:db8:a000:22::1 timers 5 15
 neighbor 10.0.0.21 remote-as 65020
 neighbor 10.0.0.21 description eBGP overlay HAN-EDG2 via Tunnel23
 neighbor 10.0.0.21 timers 5 15
 neighbor 2001:db8:a000:23::1 remote-as 65020
 neighbor 2001:db8:a000:23::1 description eBGP-v6 overlay HAN-EDG2 via Tunnel23
 neighbor 2001:db8:a000:23::1 timers 5 15
 !
 address-family ipv4
  network 10.30.0.0 mask 255.255.0.0
  neighbor 198.51.100.9 activate
  neighbor 198.51.100.9 prefix-list PL-DEFAULT-ONLY in
  neighbor 198.51.100.9 prefix-list PL-DENY-ALL out
  neighbor 10.30.255.1 activate
  neighbor 10.30.255.1 next-hop-self
  neighbor 10.0.0.13 activate
  neighbor 10.0.0.13 prefix-list PL-ENTERPRISE-IN in
  neighbor 10.0.0.13 prefix-list PL-SITE-OUT out
  neighbor 10.0.0.21 activate
  neighbor 10.0.0.21 prefix-list PL-ENTERPRISE-IN in
  neighbor 10.0.0.21 prefix-list PL-SITE-OUT out
 exit-address-family
 !
 address-family ipv6
  network 2001:db8:a030::/48
  neighbor 2001:db8:a030:ff00::1 activate
  neighbor 2001:db8:a030:ff00::1 next-hop-self
  neighbor 2001:db8:a000:22::1 activate
  neighbor 2001:db8:a000:22::1 prefix-list PL6-ENTERPRISE-IN in
  neighbor 2001:db8:a000:22::1 prefix-list PL6-SITE-OUT out
  neighbor 2001:db8:a000:23::1 activate
  neighbor 2001:db8:a000:23::1 prefix-list PL6-ENTERPRISE-IN in
  neighbor 2001:db8:a000:23::1 prefix-list PL6-SITE-OUT out
 exit-address-family
!
ip sla responder
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.14. Thiết bị `DAD-ACC1` — Switch Access L2 tại Đà Nẵng (Cisco vIOS Switch)

Mở Console của **`DAD-ACC1`**, gõ `enable` → `configure terminal`, sau đó copy-paste toàn bộ khối dưới đây rồi gõ `write memory`:

```
!==========================================================================
! TechViet Innovations (TVI) -- DAD-ACC1
! Platform: viosl2   Role: access   Site: DAD
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname DAD-ACC1
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
no ip routing
ip default-gateway 10.30.144.1
!
vtp mode transparent
!
spanning-tree mode rapid-pvst
spanning-tree extend system-id
spanning-tree vlan 30,40,50,60,99 priority 24576
!
vlan 30
 name LOGISTICS_OPS
vlan 40
 name VOICE
vlan 50
 name IOT_DEVICES
vlan 60
 name GUEST
vlan 99
 name MANAGEMENT
vlan 999
 name NATIVE_UNUSED
!
ip dhcp snooping vlan 30,40,50,60
no ip dhcp snooping information option
ip dhcp snooping
ip arp inspection vlan 30,40,50,60
ip arp inspection validate src-mac dst-mac
ip arp inspection log-buffer entries 64
errdisable recovery cause bpduguard
errdisable recovery cause psecure-violation
errdisable recovery interval 120
!
interface GigabitEthernet0/1
 description Uplink trunk -> DAD-EDG1 Gi0/2
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 30,40,50,60,99
 switchport nonegotiate
 ip dhcp snooping trust
 ip arp inspection trust
 no shutdown
!
interface GigabitEthernet0/2
 description Uplink trunk -> DAD-EDG2 Gi0/2
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk native vlan 999
 switchport trunk allowed vlan 30,40,50,60,99
 switchport nonegotiate
 ip dhcp snooping trust
 ip arp inspection trust
 no shutdown
!
interface GigabitEthernet1/0
 description Access -> PC-DAD-LOG eth0 (VLAN 30 LOGISTICS_OPS)
 switchport mode access
 switchport access vlan 30
 switchport voice vlan 40
 switchport nonegotiate
 switchport port-security maximum 3
 switchport port-security violation restrict
 switchport port-security mac-address sticky
 switchport port-security
 spanning-tree portfast
 spanning-tree bpduguard enable
 ip dhcp snooping limit rate 15
 no shutdown
!
interface GigabitEthernet1/1
 description Access -> PC-DAD-IOT eth0 (VLAN 50 IOT_DEVICES)
 switchport mode access
 switchport access vlan 50
 switchport nonegotiate
 switchport port-security maximum 2
 switchport port-security violation restrict
 switchport port-security mac-address sticky
 switchport port-security
 spanning-tree portfast
 spanning-tree bpduguard enable
 ip dhcp snooping limit rate 15
 no shutdown
!
interface GigabitEthernet1/2
 description Access -> PC-DAD-PHONE eth0 (VLAN 40 VOICE)
 switchport mode access
 switchport access vlan 40
 switchport nonegotiate
 switchport port-security maximum 2
 switchport port-security violation restrict
 switchport port-security mac-address sticky
 switchport port-security
 spanning-tree portfast
 spanning-tree bpduguard enable
 ip dhcp snooping limit rate 15
 no shutdown
!
interface GigabitEthernet1/3
 description Access -> PC-DAD-GUEST eth0 (VLAN 60 GUEST)
 switchport mode access
 switchport access vlan 60
 switchport nonegotiate
 switchport port-security maximum 2
 switchport port-security violation restrict
 switchport port-security mac-address sticky
 switchport port-security
 spanning-tree portfast
 spanning-tree bpduguard enable
 ip dhcp snooping limit rate 15
 no shutdown
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 no switchport
 ip address 172.16.99.35 255.255.255.0
 no cdp enable
 no shutdown
!
interface Vlan99
 description In-band management
 ip address 10.30.144.15 255.255.255.0
 no shutdown
!
interface Vlan1
 no ip address
 shutdown
!
interface GigabitEthernet0/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet2/0
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet2/1
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet2/2
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet2/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet3/0
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet3/1
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet3/2
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
interface GigabitEthernet3/3
 description UNUSED
 switchport mode access
 switchport access vlan 999
 spanning-tree bpduguard enable
 shutdown
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 6.15. Cấu hình 11 Máy tính người dùng ảo (`VPCS`)

> **Lưu ý quan trọng:** Bạn chỉ chạy lệnh trên các máy `PC-*` **SAU KHI** đã dán xong cấu hình của cả 14 thiết bị Router/Switch Campus/WAN ở trên và đợi khoảng 30 giây để cổng Switch chuyển sang trạng thái Forwarding (đèn xanh STP) và OSPF hội tụ xong. Khi đó máy tính xin IP động (`ip dhcp`) từ máy chủ `HCM-SRV1` mới thành công ngay lần đầu!

Mở Console của từng máy `PC-*` và dán đúng các dòng lệnh tương ứng dưới đây:

#### Máy `PC-HCM-EXEC`:

```
# PC-HCM-EXEC -- VLAN 10 EXEC_FINANCE on HCM-ACC1 Gi1/0
set pcname PC-HCM-EXEC
ip dhcp
ip auto
save
show ip
show ipv6

```

#### Máy `PC-HCM-CORP`:

```
# PC-HCM-CORP -- VLAN 12 CORP_STAFF on HCM-ACC1 Gi1/1
set pcname PC-HCM-CORP
ip dhcp
ip auto
save
show ip
show ipv6

```

#### Máy `PC-HCM-GUEST`:

```
# PC-HCM-GUEST -- VLAN 60 GUEST on HCM-ACC1 Gi1/2
set pcname PC-HCM-GUEST
ip dhcp
save
show ip
show ipv6

```

#### Máy `PC-HCM-PHONE`:

```
# PC-HCM-PHONE -- VLAN 40 VOICE on HCM-ACC1 Gi1/3
set pcname PC-HCM-PHONE
ip dhcp
ip auto
save
show ip
show ipv6

```

#### Máy `PC-HAN-ENG`:

```
# PC-HAN-ENG -- VLAN 20 RND_ENGINEERING on HAN-ACC1 Gi1/0
set pcname PC-HAN-ENG
ip dhcp
ip auto
save
show ip
show ipv6

```

#### Máy `PC-HAN-PHONE`:

```
# PC-HAN-PHONE -- VLAN 40 VOICE on HAN-ACC1 Gi1/1
set pcname PC-HAN-PHONE
ip dhcp
ip auto
save
show ip
show ipv6

```

#### Máy `PC-HAN-GUEST`:

```
# PC-HAN-GUEST -- VLAN 60 GUEST on HAN-ACC1 Gi1/2
set pcname PC-HAN-GUEST
ip dhcp
save
show ip
show ipv6

```

#### Máy `PC-DAD-LOG`:

```
# PC-DAD-LOG -- VLAN 30 LOGISTICS_OPS on DAD-ACC1 Gi1/0
set pcname PC-DAD-LOG
ip dhcp
ip auto
save
show ip
show ipv6

```

#### Máy `PC-DAD-IOT`:

```
# PC-DAD-IOT -- VLAN 50 IOT_DEVICES on DAD-ACC1 Gi1/1
set pcname PC-DAD-IOT
ip dhcp
ip auto
save
show ip
show ipv6

```

#### Máy `PC-DAD-PHONE`:

```
# PC-DAD-PHONE -- VLAN 40 VOICE on DAD-ACC1 Gi1/2
set pcname PC-DAD-PHONE
ip dhcp
ip auto
save
show ip
show ipv6

```

#### Máy `PC-DAD-GUEST`:

```
# PC-DAD-GUEST -- VLAN 60 GUEST on DAD-ACC1 Gi1/3
set pcname PC-DAD-GUEST
ip dhcp
save
show ip
show ipv6

```

## PHẦN 7: HƯỚNG DẪN CHẠY SCRIPT PYTHON AUTOMATION (PYYAML + NETMIKO)

Bài làm của bạn đã có sẵn bộ công cụ tự động hóa cực kỳ hoàn chỉnh trong thư mục `automation/` (sử dụng **Python + PyYAML + Netmiko**, hoàn toàn không cần dùng Ansible).

### Bước 7.1: Kiểm tra kết nối từ máy ảo EVE-NG tới các thiết bị

Mở cửa sổ **SSH vào máy ảo EVE-NG** (`root@<IP_EVE_NG>`), chạy lệnh ping thử tới các IP quản trị trong dải `172.16.99.0/24`:

```
# Đảm bảo cổng pnet0 trên EVE-NG đã có IP 172.16.99.1/24
ip addr add 172.16.99.1/24 dev pnet0 2>/dev/null || true
ip link set pnet0 up

# Ping kiểm tra tới HCM-EDG1 (.11), HCM-CORE1 (.13), HAN-EDG1 (.21), DAD-EDG1 (.31)
ping -c 2 172.16.99.11
ping -c 2 172.16.99.13
ping -c 2 172.16.99.21
ping -c 2 172.16.99.31

```

### Bước 7.2: Cài đặt thư viện `pyyaml` và `netmiko`

Di chuyển vào thư mục `automation` (nơi bạn đã copy bài làm vào ở Bước 3.1) và cài đặt thư viện:

```
cd /root/tvi-project/automation

# Tạo môi trường ảo Python và cài đặt netmiko, pyyaml, pytest
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install netmiko pyyaml pytest

```

### Bước 7.3: Thiết lập tài khoản SSH qua biến môi trường (Không lưu mật khẩu trong code)

Tất cả 18 thiết bị Cisco trong bài đều được cấu hình sẵn tài khoản SSH là:

* **Username:** `tviadmin`

* **Password:** `Tvi@Lab2026`

Bạn gõ lệnh sau trên cửa sổ SSH của EVE-NG để nạp thông tin đăng nhập vào biến môi trường:

```
export TVI_SSH_USER="tviadmin"
# Không export mật khẩu khi demo trước giảng viên: để trống TVI_SSH_PASS,
# script sẽ hỏi mật khẩu bằng getpass (gõ không hiện ký tự).
# Khi tự luyện tập ở nhà có thể export cho nhanh:
# export TVI_SSH_PASS="Tvi@Lab2026"

```

### Bước 7.4: Các câu lệnh chạy Automation & Ý nghĩa từng lệnh

> **Lưu ý:** Bản mới chạy toàn bộ 18 thiết bị trong một lab, nên **không cần cờ `--lab A`** nữa: script mặc định chạy cả Campus/WAN và Data Center. Bốn router Data Center chỉ được sao lưu, nhận baseline và thu telemetry (OSPF, LDP, VPNv4); VLAN chỉ đẩy xuống các switch Core/Access.

```
# 1. Chạy kiểm thử Offline (8 bài Unit Test tự động không cần mạng):
python3 -m pytest -v

# 2. Chạy chế độ Dry-Run (Xem trước các lệnh sẽ đẩy xuống từng thiết bị mà chưa kết nối SSH thật):
python3 tvi_auto.py --dry-run

# 3. Sao lưu toàn bộ cấu hình (running-config & ip interface brief) của cả 18 thiết bị vào thư mục backups/:
python3 tvi_auto.py --task backup

# 4. Chạy trọn quy trình tự động hóa (Pre-backup -> Đẩy Baseline & VLAN -> Write Memory -> Post-backup -> Xuất file Diff -> Kiểm tra tuân thủ Verify):
python3 tvi_auto.py --task all

# 5. Thu thập thông số trạng thái mạng (OSPF, BGP, HSRP, LACP, STP, Tunnel, LDP, VPNv4) ra file JSON trong thư mục telemetry/:
python3 tvi_auto.py --task telemetry

```

### Bước 7.5: Kịch bản biểu diễn tạo VLAN mới tự động khi chấm Demo trực tiếp

Khi giảng viên yêu cầu: *"Em hãy dùng script Python tạo thêm một VLAN mới (ví dụ VLAN 25 tên là `AI_TRAINING`) cho chi nhánh Hà Nội"*, bạn làm đúng 3 lệnh sau:

```
# 1. Mở file cấu hình biến VLAN
nano vars/vlans.yaml

```

Trong file, dòng `HAN: []` nghĩa là Hà Nội chưa có VLAN riêng. Đổi dòng đó thành hai dòng sau (giữ đúng 2 và 4 dấu cách đầu dòng), lưu bằng `Ctrl+O` → `Enter`, thoát bằng `Ctrl+X`:

```
  HAN:
    - {id: 25, name: AI_TRAINING}
```

Hoặc dùng lệnh sửa tự động (chỉ chạy **một lần**):

```
sed -i 's/^  HAN: \[\]$/  HAN:\n    - {id: 25, name: AI_TRAINING}/' vars/vlans.yaml
grep -A1 '^  HAN' vars/vlans.yaml     # phải thấy dòng AI_TRAINING ngay dưới HAN:

# 2. Chạy script đẩy cấu hình riêng cho chi nhánh Hà Nội (HAN):
python3 tvi_auto.py --task all --site HAN --role access

# 3. Xem kết quả so sánh cấu hình trước và sau khi chạy (file _diff.txt) và file log:
ls -lh backups/
cat backups/HAN-ACC1_*_diff.txt | tail -n 25
tail -n 20 logs/automation.log

```

Sau đó mở Console của **`HAN-ACC1`** gõ `show vlan brief`, bạn sẽ thấy **`25 AI_TRAINING active`** xuất hiện ngay lập tức!

## PHẦN 8: KỊCH BẢN THỬ NGHIỆM, KIỂM TRA (TESTING) & CHỊU LỖI (FAILOVER)

Sau khi cấu hình xong, bạn lần lượt chạy các lệnh kiểm tra dưới đây. **Hãy chụp màn hình hoặc copy kết quả chữ trả về** để dán vào các khung màu vàng `Evidence E1 -> E17` trong báo cáo `report/main.tex` (tên file và lệnh cho từng khung có trong tài liệu *TVI Lab Build & Demo Guide*, bước 7)!

### 8.1. Kiểm tra Layer 2: Trunking, LACP EtherChannel & Spanning-Tree (Step 3)

* Trên **`HCM-CORE1`**, gõ:

  ```
  show interfaces trunk
  show etherchannel summary
  
  ```

  * **Kết quả chuẩn:** Cổng `Po1` và `Gi0/3` ở trạng thái `trunking`, Native VLAN là `999`. Trong bảng EtherChannel, nhóm `1` hiện **`Po1(SU)`** với 2 cổng thành viên **`Gi0/1(P)`** và **`Gi0/2(P)`**.

* Trên **`HCM-ACC1`**, gõ:

  ```
  show spanning-tree root
  show spanning-tree vlan 10
  
  ```

  * **Kết quả chuẩn:** Các VLAN `10, 12, 40, 80` có Root ID trỏ về địa chỉ MAC của `HCM-CORE1` (cổng `Gi0/1` là `Root FWD`, cổng `Gi0/2` là `Altn BLK`). Các VLAN `60, 70, 99` có Root ID trỏ về `HCM-CORE2`.

### 8.2. Kiểm tra HSRP Gateway dự phòng, DHCP tập trung & DNS (Step 4)

* Trên **`HCM-CORE1`** và **`HAN-EDG1`**, gõ:

  ```
  show standby brief
  
  ```

  * **Kết quả chuẩn:** Trên `HCM-CORE1`, các nhóm VLAN `10, 12, 40, 80` hiện trạng thái **`Active`** (Priority 110), các nhóm `60, 70, 99` hiện **`Standby`** (Priority 100), có đầy đủ cả IPv4 và IPv6 (`FE80::1`).

* Trên **`HCM-SRV1`**, gõ:

  ```
  show ip dhcp binding
  show ip dhcp pool
  
  ```

  * **Kết quả chuẩn:** Hiển thị danh sách địa chỉ IP đã cấp thành công cho toàn bộ 11 máy tính `PC-*` ở cả 3 miền TP.HCM (`10.10.x.x`), Hà Nội (`10.20.x.x`), và Đà Nẵng (`10.30.x.x`).

* Trên **`PC-HCM-CORP`**, gõ:

  ```
  ping hcm-edg1.tvi.lab
  
  ```

  * **Kết quả chuẩn:** Máy tính tự động phân giải tên miền `hcm-edg1.tvi.lab` ra IP `10.10.255.1` thông qua DNS Server trên `HCM-SRV1` (`10.10.43.10`) và ping trả lời thành công.

### 8.3. Kiểm tra Định tuyến Nội vùng OSPF Underlay (Step 5)

* Trên **`HCM-CORE1`**, gõ:

  ```
  show ip ospf neighbor
  show ipv6 ospf neighbor
  ping 10.10.255.1 source loopback0
  ping 10.10.255.2 source loopback0
  ping 10.10.255.4 source loopback0
  
  ```

  * **Kết quả chuẩn:** Hiển thị 3 láng giềng OSPF ở trạng thái **`FULL`** (`10.10.255.1` là EDG1, `10.10.255.2` là EDG2, `10.10.255.4` là CORE2). Ping thông suốt 100% giữa các Loopback.

### 8.4. Kiểm tra Định tuyến Liên vùng BGP & Đường hầm GRE/IPsec WAN (Step 6)

* Trên **`HCM-EDG1`**, gõ:

  ```
  show bgp ipv4 unicast summary
  show bgp ipv6 unicast summary
  show crypto ikev2 sa
  show crypto ipsec sa | include ident|encaps|decaps
  show ip route bgp
  
  ```

  * **Kết quả chuẩn:**

    * Tất cả các phiên BGP (`203.0.113.1` - ISP-A, `10.10.255.2` - HCM-EDG2, `10.0.0.2` - HAN-EDG1, `10.0.0.6` - DAD-EDG1) đều hiện con số ở cột **`State/PfxRcd`** (đã nhận prefix thành công).

    * `show crypto ikev2 sa` hiện trạng thái **`READY`** cho 2 đường hầm đi Hà Nội và Đà Nẵng; bộ đếm `#pkts encaps` và `#pkts decaps` tăng lên khi có lưu lượng đi qua.

    * Bảng định tuyến BGP có tuyến `10.20.0.0/16` (Hà Nội), `10.30.0.0/16` (Đà Nẵng) và `0.0.0.0/0` (Default route ra Internet).

### 8.5. Kiểm tra Kết nối Đầu-Cuối (End-to-End) & Đi tắt trực tiếp giữa các chi nhánh (Step 10)

* Mở Console của máy **`PC-HAN-ENG`** (Kỹ sư Hà Nội), kiểm tra IP của máy `PC-HCM-CORP` (ví dụ `10.10.0.21`) và `PC-DAD-LOG` (ví dụ `10.30.128.21`), sau đó gõ:

  ```
  trace 10.10.0.21
  trace 10.30.128.21
  
  ```

  * **Kết quả chuẩn:**

    * Khi `trace` từ Hà Nội vào TP.HCM (`10.10.0.21`), gói tin đi qua `10.20.0.2` (`HAN-EDG1`) → nhảy thẳng sang `10.0.0.1` (`HCM-EDG1` qua Tunnel 11).

    * Khi `trace` từ Hà Nội vào Đà Nẵng (`10.30.128.21`), chặng thứ 2 là **`10.0.0.18`** (`DAD-EDG1` qua **Tunnel 13 nối trực tiếp Hà Nội – Đà Nẵng**, chứng minh lưu lượng giữa 2 chi nhánh đi thẳng chứ không bị vòng qua trụ sở HCM).

### 8.6. Kiểm tra Bảo mật: Local Internet Breakout (NAT), Cô lập Guest/IoT/Exec, ZBF & DAI (Step 7)

1. **Chứng minh Chi nhánh đi thẳng ra Internet (Direct Cloud Access / Local NAT):**

   * Trên **`PC-HAN-ENG`**, gõ:

     ```
     ping 192.0.2.10
     
     ```

     *(Trong đó `192.0.2.10` là IP mô phỏng dịch vụ Cloud/SaaS công cộng đặt trên ISP).*

   * Ngay sau đó, trên **`HAN-EDG1`**, gõ:

     ```
     show ip nat translations
     show policy-map type inspect zone-pair sessions
     
     ```

   * **Kết quả chuẩn:** Địa chỉ nội bộ `10.20.0.x` của Hà Nội được dịch (NAT Overload) trực tiếp ra địa chỉ WAN của Hà Nội (`203.0.113.6`) và được kiểm duyệt bởi tường lửa Zone-Based Firewall (`ZP-INSIDE-OUTSIDE`).

2. **Chứng minh mạng Khách (`GUEST`) chỉ đi được Internet, bị chặn hoàn toàn vào mạng Nội bộ:**

   * Trên **`PC-HCM-GUEST`**, gõ:

     ```
     ping 192.0.2.10
     ping 10.10.43.10
     
     ```

   * **Kết quả chuẩn:** Ping `192.0.2.10` (Internet) **thành công**, nhưng ping `10.10.43.10` (Máy chủ nội bộ) **bị chặn (`timeout` / `unreachable`)**.

3. **Chứng minh thiết bị IoT (`PC-DAD-IOT`) chỉ được phép gửi dữ liệu về Server trung tâm, bị chặn truy cập ngang sang máy nhân viên:**

   * Trên **`PC-DAD-IOT`**, gõ:

     ```
     ping 10.10.43.10
     ping 10.30.128.21
     
     ```

   * **Kết quả chuẩn:** Ping về Server trung tâm `10.10.43.10` **thành công**, nhưng ping sang máy nhân viên kho `10.30.128.21` **bị chặn**.

4. **Chứng minh bảo vệ 1 chiều cho VLAN Ban Giám Đốc (`VLAN 10 EXEC_FINANCE`):**

   * Từ `PC-HAN-ENG` ping vào IP của `PC-HCM-EXEC` (`10.10.32.21`) → **Bị chặn**. Nhưng từ `PC-HCM-EXEC` ping ngược ra `PC-HAN-ENG` → **Thành công**! Kiểm tra bộ đếm chặn trên `HCM-CORE1` bằng lệnh:

     ```
     show access-lists ACL-EXEC-PROTECT
     
     ```

5. **Kiểm tra bảo mật Layer 2 (DHCP Snooping & Dynamic ARP Inspection):**

   * Trên **`DAD-ACC1`** (hoặc `HCM-ACC1`), gõ:

     ```
     show ip dhcp snooping binding
     show ip arp inspection statistics
     
     ```

### 8.7. Kiểm tra Chất lượng Dịch vụ QoS cho thoại VoIP (Step 8)

Máy chủ `HCM-SRV1` đã được cấu hình sẵn bộ phát lưu lượng giả lập cuộc gọi VoIP (**IP SLA 10 và 20** gửi các gói UDP cổng `16384` mang nhãn `DSCP EF - 46` đi Hà Nội và Đà Nẵng mỗi 30 giây).

* Trên **`HCM-SRV1`**, gõ:

  ```
  show ip sla statistics
  
  ```

  * **Kết quả chuẩn:** Hiển thị `Latest operation return code: OK`, kèm theo thông số độ trễ (`RTT`), độ rung pha (`Jitter`) và điểm chất lượng thoại (`MOS`).

* Trên **`HCM-EDG1`**, gõ:

  ```
  show policy-map interface GigabitEthernet0/1
  
  ```

  * **Kết quả chuẩn:** Dưới mục `Class-map: CM-WAN-VOICE (match-any)`, bộ đếm `packets, bytes` và `Queueing -> Strict Priority` tăng liên tục, chứng minh lưu lượng thoại đã được đưa vào hàng đợi ưu tiên tuyệt đối (LLQ 30%).

### 8.8. Kịch bản Biểu diễn Chịu lỗi (Failover Simulation - Ăn điểm tuyệt đối khi Vấn đáp)

Trong buổi bảo vệ, giảng viên sẽ yêu cầu bạn cắt thử cáp hoặc tắt nóng thiết bị khi đang ping liên tục. Dưới đây là 2 bài biểu diễn ấn tượng nhất:

#### Bài Failover 1: Tắt nóng Switch Lõi `HCM-CORE1` (Kiểm tra HSRP + RSTP + OSPF hội tụ)

1. Trên máy **`PC-HCM-CORP`**, gõ lệnh ping liên tục sang Đà Nẵng:

   ```
   ping 10.30.128.21 -t
   
   ```

2. Trong lúc các dòng trả lời ping đang chạy đều đặn, bạn quay ra màn hình EVE-NG, **click chuột phải vào node `HCM-CORE1` → chọn Stop** (giả lập `HCM-CORE1` bị cháy nguồn đột ngột).

3. Mở ngay Console của **`HCM-CORE2`** và gõ:

   ```
   show standby brief
   
   ```

4. **Kết quả quan sát:** Thường mất khoảng **2 đến 4 gói ping** (HSRP hold 3 giây + RSTP), `HCM-CORE2` lập tức chuyển từ `Standby` sang **`Active`** cho toàn bộ các VLAN, và dòng lệnh ping trên `PC-HCM-CORP` chạy thông suốt trở lại qua `HCM-CORE2`!

5. Khởi động lại `HCM-CORE1` (Click phải → **Start**). Sau khi `HCM-CORE1` khởi động xong và giữ ổn định 10 giây (`preempt delay minimum 10`), nó tự động lấy lại quyền `Active` mà không làm rớt gói tin nào.

#### Bài Failover 2: Đứt cáp quang nhà mạng `ISP-A` tại Hà Nội (Kiểm tra chuyển mạch WAN BGP + IPsec sang `ISP-B`)

1. Trên máy **`PC-HAN-ENG`**, gõ lệnh ping liên tục về TP.HCM:

   ```
   ping 10.10.0.21 -t
   
   ```

2. Mở Console của **`HAN-EDG1`** và ngắt cổng WAN nối với nhà mạng `ISP-A`:

   ```
   configure terminal
   interface GigabitEthernet0/1
    shutdown
   end
   
   ```

3. **Kết quả quan sát:** Sau khoảng **10–15 giây** (nhờ BGP Timers đã được tối ưu xuống `5 15` và IPsec DPD `10 3`), phiên BGP trên `Tunnel11` (Plane A) ngắt và lưu lượng tự động bẻ lái sang `HAN-EDG2` đi qua `Tunnel21` trên nhà mạng `ISP-B` (Plane B)! Bạn có thể gõ `trace 10.10.0.21` trên `PC-HAN-ENG` để chứng minh đường đi mới: gói tin vẫn vào gateway `10.20.0.2` (`HAN-EDG1` vẫn là HSRP Active vì cổng LAN của nó không hỏng), sau đó sang `10.20.254.2` (`HAN-EDG2` qua đường nối trực tiếp) rồi đi `Tunnel21` trên nhà mạng `ISP-B`.

4. Khôi phục lại đường truyền trên **`HAN-EDG1`**:

   ```
   configure terminal
   interface GigabitEthernet0/1
    no shutdown
   end
   
   ```

## PHẦN 9: CỤM DATA CENTER — 4 ROUTER vIOS CHẠY MPLS L3VPN (BẮT BUỘC, CHẠY CHUNG LAB)

Bản cũ dùng Arista vEOS với EVPN-VXLAN. Image vIOS không hỗ trợ VXLAN, nên bản mới dựng cùng kiến trúc (underlay OSPF, overlay BGP, tách tenant bằng VRF) bằng **MPLS L3VPN**. Báo cáo vẫn trình bày EVPN-VXLAN là thiết kế cho thiết bị thật, còn lab dùng MPLS L3VPN.

### 9.1. Tạo 4 router và 4 máy chủ ảo

1. Chuột phải → **Node** → **`Cisco vIOS Router`** → Number of nodes `4`, Image `vios-adventerprisek9-m.SPA.159-3.M6`, RAM **`512`**, Ethernet **`6`**. Đổi tên thành `DC-SPINE1`, `DC-SPINE2`, `DC-LEAF1`, `DC-LEAF2`.
2. Chuột phải → **Node** → **`Virtual PC (VPCS)`** → Number of nodes `4`. Đổi tên thành `DC-H1`, `DC-H2`, `DC-H3`, `DC-H4`.

### 9.2. Bảng F: nối dây cụm Data Center

| STT | Thiết bị 1 | Cổng Thiết bị 1 | Nối sang Thiết bị 2 | Cổng Thiết bị 2 | Giải thích kết nối | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| M15 | `DC-SPINE1` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | — | Quản trị SSH (`172.16.99.41/24`) | 
| M16 | `DC-SPINE2` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | — | Quản trị SSH (`172.16.99.42/24`) | 
| M17 | `DC-LEAF1` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | — | Quản trị SSH (`172.16.99.43/24`) | 
| M18 | `DC-LEAF2` | **`Gi0/0`** | `OOB-MGMT (Cloud0)` | — | Quản trị SSH (`172.16.99.44/24`) | 
| 35 | **`HCM-CORE1`** | **`Gi1/2`** | **`DC-LEAF1`** | **`Gi0/5`** | Liên kết biên DC ↔ Campus (`10.10.189.0/30`, OSPF; phía Leaf nằm trong VRF `TENANT-PROD`) | 
| 36 | **`HCM-CORE2`** | **`Gi1/2`** | **`DC-LEAF2`** | **`Gi0/5`** | Liên kết biên DC ↔ Campus (`10.10.189.4/30`, OSPF; phía Leaf nằm trong VRF `TENANT-PROD`) | 
| 37 | **`DC-SPINE1`** | **`Gi0/1`** | **`DC-LEAF1`** | **`Gi0/1`** | Liên kết Fabric underlay (`10.10.190.0/30`, OSPF + LDP) | 
| 38 | **`DC-SPINE1`** | **`Gi0/2`** | **`DC-LEAF2`** | **`Gi0/1`** | Liên kết Fabric underlay (`10.10.190.4/30`, OSPF + LDP) | 
| 39 | **`DC-SPINE2`** | **`Gi0/1`** | **`DC-LEAF1`** | **`Gi0/2`** | Liên kết Fabric underlay (`10.10.190.8/30`, OSPF + LDP) | 
| 40 | **`DC-SPINE2`** | **`Gi0/2`** | **`DC-LEAF2`** | **`Gi0/2`** | Liên kết Fabric underlay (`10.10.190.12/30`, OSPF + LDP) | 
| 41 | **`DC-LEAF1`** | **`Gi0/3`** | **`DC-H1`** | **`eth0`** | Máy chủ tenant `TENANT-PROD` (`10.10.128.11`, gateway `10.10.128.1`) | 
| 42 | **`DC-LEAF2`** | **`Gi0/3`** | **`DC-H2`** | **`eth0`** | Máy chủ tenant `TENANT-PROD` (`10.10.129.12`, gateway `10.10.129.1`) | 
| 43 | **`DC-LEAF1`** | **`Gi0/4`** | **`DC-H3`** | **`eth0`** | Máy chủ tenant `TENANT-DEV` (`10.10.130.13`, gateway `10.10.130.1`) | 
| 44 | **`DC-LEAF2`** | **`Gi0/4`** | **`DC-H4`** | **`eth0`** | Máy chủ tenant `TENANT-DEV` (`10.10.131.14`, gateway `10.10.131.1`) | 

> Sửa nhỏ so với bản cũ: cổng biên phía Leaf giờ là **`Gi0/5`** (không còn `Ethernet5`); mô tả cổng `Gi1/2` trên `HCM-CORE1/2` ở mục 6.6–6.7 đã được cập nhật theo.

### 9.3. Cấu hình 4 router Data Center

Cách dán giống hệt các router vIOS ở Phần 6 (`enable` → `configure terminal` → dán từng đoạn → `write memory`). Nên cấu hình 2 Spine trước, sau đó 2 Leaf.

#### 9.3.1. `DC-SPINE1` — Spine: router lõi P + Route Reflector VPNv4 (Cisco vIOS Router)

```
!==========================================================================
! TechViet Innovations (TVI) -- DC-SPINE1
! Platform: vios   Role: spine   Site: HCM
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname DC-SPINE1
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
mpls label protocol ldp
mpls ldp router-id Loopback0 force
!
interface Loopback0
 description Router-ID / LDP / VPNv4 route reflector
 ip address 10.10.191.1 255.255.255.255
 ip ospf 1 area 0
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.41 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet0/1
 description Fabric -> DC-LEAF1 Gi0/1
 ip address 10.10.190.1 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 mpls ip
 no shutdown
!
interface GigabitEthernet0/2
 description Fabric -> DC-LEAF2 Gi0/1
 ip address 10.10.190.5 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 mpls ip
 no shutdown
!
router ospf 1
 router-id 10.10.191.1
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/1
 no passive-interface GigabitEthernet0/2
!
router bgp 65011
 bgp router-id 10.10.191.1
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 no bgp default route-target filter
 neighbor 10.10.191.11 remote-as 65011
 neighbor 10.10.191.11 description iBGP VPNv4 DC-LEAF1
 neighbor 10.10.191.11 update-source Loopback0
 neighbor 10.10.191.12 remote-as 65011
 neighbor 10.10.191.12 description iBGP VPNv4 DC-LEAF2
 neighbor 10.10.191.12 update-source Loopback0
 !
 address-family vpnv4
  neighbor 10.10.191.11 activate
  neighbor 10.10.191.11 send-community extended
  neighbor 10.10.191.11 route-reflector-client
  neighbor 10.10.191.12 activate
  neighbor 10.10.191.12 send-community extended
  neighbor 10.10.191.12 route-reflector-client
 exit-address-family
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

#### 9.3.2. `DC-SPINE2` — Spine: router lõi P + Route Reflector VPNv4 (Cisco vIOS Router)

```
!==========================================================================
! TechViet Innovations (TVI) -- DC-SPINE2
! Platform: vios   Role: spine   Site: HCM
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname DC-SPINE2
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
mpls label protocol ldp
mpls ldp router-id Loopback0 force
!
interface Loopback0
 description Router-ID / LDP / VPNv4 route reflector
 ip address 10.10.191.2 255.255.255.255
 ip ospf 1 area 0
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.42 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet0/1
 description Fabric -> DC-LEAF1 Gi0/2
 ip address 10.10.190.9 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 mpls ip
 no shutdown
!
interface GigabitEthernet0/2
 description Fabric -> DC-LEAF2 Gi0/2
 ip address 10.10.190.13 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 mpls ip
 no shutdown
!
router ospf 1
 router-id 10.10.191.2
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/1
 no passive-interface GigabitEthernet0/2
!
router bgp 65011
 bgp router-id 10.10.191.2
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 no bgp default route-target filter
 neighbor 10.10.191.11 remote-as 65011
 neighbor 10.10.191.11 description iBGP VPNv4 DC-LEAF1
 neighbor 10.10.191.11 update-source Loopback0
 neighbor 10.10.191.12 remote-as 65011
 neighbor 10.10.191.12 description iBGP VPNv4 DC-LEAF2
 neighbor 10.10.191.12 update-source Loopback0
 !
 address-family vpnv4
  neighbor 10.10.191.11 activate
  neighbor 10.10.191.11 send-community extended
  neighbor 10.10.191.11 route-reflector-client
  neighbor 10.10.191.12 activate
  neighbor 10.10.191.12 send-community extended
  neighbor 10.10.191.12 route-reflector-client
 exit-address-family
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

#### 9.3.3. `DC-LEAF1` — Leaf: router PE, gateway cho các tenant, cổng biên về Campus (Cisco vIOS Router)

```
!==========================================================================
! TechViet Innovations (TVI) -- DC-LEAF1
! Platform: vios   Role: leaf   Site: HCM
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname DC-LEAF1
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
! ---------------- Tenant VRFs (one per tenant, imported/exported by route-target) ----------------
vrf definition TENANT-PROD
 description production applications, reachable from the campus
 rd 10.10.191.11:100
 address-family ipv4
  route-target export 65011:100
  route-target import 65011:100
 exit-address-family
!
vrf definition TENANT-DEV
 description development, isolated from PROD and the campus
 rd 10.10.191.11:200
 address-family ipv4
  route-target export 65011:200
  route-target import 65011:200
 exit-address-family
!
mpls label protocol ldp
mpls ldp router-id Loopback0 force
!
interface Loopback0
 description Router-ID / LDP / VPNv4 next hop
 ip address 10.10.191.11 255.255.255.255
 ip ospf 1 area 0
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.43 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet0/1
 description Fabric -> DC-SPINE1 Gi0/1
 ip address 10.10.190.2 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 mpls ip
 no shutdown
!
interface GigabitEthernet0/2
 description Fabric -> DC-SPINE2 Gi0/1
 ip address 10.10.190.10 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 mpls ip
 no shutdown
!
interface GigabitEthernet0/3
 description Tenant TENANT-PROD gateway -> DC-H1 (10.10.128.11)
 vrf forwarding TENANT-PROD
 ip address 10.10.128.1 255.255.255.0
 no shutdown
!
interface GigabitEthernet0/4
 description Tenant TENANT-DEV gateway -> DC-H3 (10.10.130.13)
 vrf forwarding TENANT-DEV
 ip address 10.10.130.1 255.255.255.0
 no shutdown
!
interface GigabitEthernet0/5
 description DC border -> HCM-CORE1 Gi1/2 (campus OSPF 10, VRF TENANT-PROD)
 vrf forwarding TENANT-PROD
 ip address 10.10.189.2 255.255.255.252
 ip ospf network point-to-point
 ip ospf 11 area 0
 no shutdown
!
router ospf 1
 router-id 10.10.191.11
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/1
 no passive-interface GigabitEthernet0/2
!
router ospf 11 vrf TENANT-PROD
 router-id 10.10.189.2
 auto-cost reference-bandwidth 100000
 redistribute connected subnets
 redistribute bgp 65011 subnets metric 100
!
router bgp 65011
 bgp router-id 10.10.191.11
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 neighbor 10.10.191.1 remote-as 65011
 neighbor 10.10.191.1 description iBGP VPNv4 DC-SPINE1
 neighbor 10.10.191.1 update-source Loopback0
 neighbor 10.10.191.2 remote-as 65011
 neighbor 10.10.191.2 description iBGP VPNv4 DC-SPINE2
 neighbor 10.10.191.2 update-source Loopback0
 !
 address-family vpnv4
  neighbor 10.10.191.1 activate
  neighbor 10.10.191.1 send-community extended
  neighbor 10.10.191.2 activate
  neighbor 10.10.191.2 send-community extended
 exit-address-family
 !
 address-family ipv4 vrf TENANT-PROD
  redistribute connected
  maximum-paths ibgp 2
  distance bgp 20 100 200
 exit-address-family
 !
 address-family ipv4 vrf TENANT-DEV
  redistribute connected
  maximum-paths ibgp 2
 exit-address-family
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

#### 9.3.4. `DC-LEAF2` — Leaf: router PE, gateway cho các tenant, cổng biên về Campus (Cisco vIOS Router)

```
!==========================================================================
! TechViet Innovations (TVI) -- DC-LEAF2
! Platform: vios   Role: leaf   Site: HCM
! Generated from tools/sot.py by tools/build_configs.py -- edit the SoT, not this file.
! Paste into the device in global configuration mode (conf t).
!==========================================================================
hostname DC-LEAF2
!
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
service password-encryption
clock timezone ICT 7 0
!
ip domain name tvi.lab
no ip domain lookup
ip cef
!
username tviadmin privilege 15 secret Tvi@Lab2026
enable secret Tvi@Lab2026
aaa new-model
aaa authentication login default local
aaa authentication login CONSOLE none
aaa authorization exec default local
!
crypto key generate rsa modulus 2048
ip ssh version 2
ip ssh time-out 60
ip ssh authentication-retries 3
!
! ---------------- Tenant VRFs (one per tenant, imported/exported by route-target) ----------------
vrf definition TENANT-PROD
 description production applications, reachable from the campus
 rd 10.10.191.12:100
 address-family ipv4
  route-target export 65011:100
  route-target import 65011:100
 exit-address-family
!
vrf definition TENANT-DEV
 description development, isolated from PROD and the campus
 rd 10.10.191.12:200
 address-family ipv4
  route-target export 65011:200
  route-target import 65011:200
 exit-address-family
!
mpls label protocol ldp
mpls ldp router-id Loopback0 force
!
interface Loopback0
 description Router-ID / LDP / VPNv4 next hop
 ip address 10.10.191.12 255.255.255.255
 ip ospf 1 area 0
!
interface GigabitEthernet0/0
 description OOB-MGMT -> EVE-NG Cloud0 (172.16.99.0/24)
 ip address 172.16.99.44 255.255.255.0
 no cdp enable
 no shutdown
!
interface GigabitEthernet0/1
 description Fabric -> DC-SPINE1 Gi0/2
 ip address 10.10.190.6 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 mpls ip
 no shutdown
!
interface GigabitEthernet0/2
 description Fabric -> DC-SPINE2 Gi0/2
 ip address 10.10.190.14 255.255.255.252
 ip ospf network point-to-point
 ip ospf 1 area 0
 mpls ip
 no shutdown
!
interface GigabitEthernet0/3
 description Tenant TENANT-PROD gateway -> DC-H2 (10.10.129.12)
 vrf forwarding TENANT-PROD
 ip address 10.10.129.1 255.255.255.0
 no shutdown
!
interface GigabitEthernet0/4
 description Tenant TENANT-DEV gateway -> DC-H4 (10.10.131.14)
 vrf forwarding TENANT-DEV
 ip address 10.10.131.1 255.255.255.0
 no shutdown
!
interface GigabitEthernet0/5
 description DC border -> HCM-CORE2 Gi1/2 (campus OSPF 10, VRF TENANT-PROD)
 vrf forwarding TENANT-PROD
 ip address 10.10.189.6 255.255.255.252
 ip ospf network point-to-point
 ip ospf 11 area 0
 no shutdown
!
router ospf 1
 router-id 10.10.191.12
 auto-cost reference-bandwidth 100000
 passive-interface default
 no passive-interface GigabitEthernet0/1
 no passive-interface GigabitEthernet0/2
!
router ospf 11 vrf TENANT-PROD
 router-id 10.10.189.6
 auto-cost reference-bandwidth 100000
 redistribute connected subnets
 redistribute bgp 65011 subnets metric 100
!
router bgp 65011
 bgp router-id 10.10.191.12
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 neighbor 10.10.191.1 remote-as 65011
 neighbor 10.10.191.1 description iBGP VPNv4 DC-SPINE1
 neighbor 10.10.191.1 update-source Loopback0
 neighbor 10.10.191.2 remote-as 65011
 neighbor 10.10.191.2 description iBGP VPNv4 DC-SPINE2
 neighbor 10.10.191.2 update-source Loopback0
 !
 address-family vpnv4
  neighbor 10.10.191.1 activate
  neighbor 10.10.191.1 send-community extended
  neighbor 10.10.191.2 activate
  neighbor 10.10.191.2 send-community extended
 exit-address-family
 !
 address-family ipv4 vrf TENANT-PROD
  redistribute connected
  maximum-paths ibgp 2
  distance bgp 20 100 200
 exit-address-family
 !
 address-family ipv4 vrf TENANT-DEV
  redistribute connected
  maximum-paths ibgp 2
 exit-address-family
!
ip access-list standard ACL-MGMT-VTY
 remark SSH only from OOB network and the three in-band MGMT VLANs
 permit 172.16.99.0 0.0.0.255
 permit 10.10.44.0 0.0.0.255
 permit 10.20.31.0 0.0.0.255
 permit 10.30.144.0 0.0.0.255
 deny   any log
!
line con 0
 login authentication CONSOLE
 logging synchronous
 exec-timeout 0 0
 transport preferred none
line vty 0 4
 access-class ACL-MGMT-VTY in
 transport input ssh
 transport preferred none
 exec-timeout 15 0
 logging synchronous
!
end
write memory

```

### 9.4. Cấu hình 4 máy chủ ảo DC (VPCS, IP tĩnh)

#### Máy chủ ảo `DC-H1` (VPCS):

```
# DC-H1 -- DC host on DC-LEAF1 Gi0/3 (VRF TENANT-PROD)
set pcname DC-H1
ip 10.10.128.11/24 10.10.128.1
save

```

#### Máy chủ ảo `DC-H2` (VPCS):

```
# DC-H2 -- DC host on DC-LEAF2 Gi0/3 (VRF TENANT-PROD)
set pcname DC-H2
ip 10.10.129.12/24 10.10.129.1
save

```

#### Máy chủ ảo `DC-H3` (VPCS):

```
# DC-H3 -- DC host on DC-LEAF1 Gi0/4 (VRF TENANT-DEV)
set pcname DC-H3
ip 10.10.130.13/24 10.10.130.1
save

```

#### Máy chủ ảo `DC-H4` (VPCS):

```
# DC-H4 -- DC host on DC-LEAF2 Gi0/4 (VRF TENANT-DEV)
set pcname DC-H4
ip 10.10.131.14/24 10.10.131.1
save

```

### 9.5. Kiểm tra cụm Data Center (Test T24, Evidence E8)

* Trên **`DC-LEAF1`**, gõ:

  ```
  show mpls ldp neighbor
  show bgp vpnv4 unicast all summary
  show ip route vrf TENANT-PROD
  ```

  * **Kết quả chuẩn:** 2 láng giềng LDP (2 Spine); 2 phiên VPNv4 tới `10.10.191.1` và `10.10.191.2` đều có số ở cột `State/PfxRcd`; bảng định tuyến VRF có `10.10.129.0/24` học qua BGP (`B`) từ `10.10.191.12`, và tuyến mặc định `O*E2 0.0.0.0/0` học từ `HCM-CORE1`.

* Trên **`DC-H1`**, gõ:

  ```
  ping 10.10.129.12
  ping 10.20.0.21
  ping 10.10.130.13
  ```

  * **Kết quả chuẩn:** Ping `DC-H2` (cùng tenant PROD, khác Leaf) **thành công**; ping máy kỹ sư Hà Nội (thay bằng IP thật của `PC-HAN-ENG`) **thành công** qua cổng biên và đường hầm WAN; ping `DC-H3` (tenant DEV) **thất bại**, chứng minh hai tenant bị cách ly hoàn toàn.

* Trên **`HCM-CORE1`**, gõ `show ip route ospf | include 10.10.12` → thấy `10.10.128.0/24` và `10.10.129.0/24` dạng `O E2`, nghĩa là Campus đã học được mạng máy chủ của Data Center.

