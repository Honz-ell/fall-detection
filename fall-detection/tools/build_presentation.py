#!/usr/bin/env python3
"""Build the 14-slide Vietnamese FallAllD deck and PNG previews from one visual source."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.util import Inches

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "slides_preview"
PPTX_PATH = ROOT / "docs" / "FallAllD_BigData_Demo.pptx"
W, H = 1600, 900
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BG = "#0B1222"
PANEL = "#131F32"
PANEL2 = "#101A2B"
LINE = "#2A3A50"
WHITE = "#F1F6FC"
MUTED = "#A4B3C6"
TEAL = "#55D6B4"
BLUE = "#79A9FF"
RED = "#FF7185"
GOLD = "#F2C16D"


def font(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def rounded(draw, box, fill=PANEL, outline=LINE, radius=18, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def wrap_lines(draw, text: str, fnt, max_width: int):
    lines = []
    for para in str(text).split("\n"):
        if not para:
            lines.append("")
            continue
        words = para.split()
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width or not line:
                line = test
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines


def text_box(draw, x, y, text, size=26, color=WHITE, max_width=600, max_height=400, bold=False, spacing=1.28):
    start_size = size
    while size >= max(13, start_size - 8):
        fnt = font(size, bold)
        lines = wrap_lines(draw, text, fnt, max_width)
        line_h = int(size * spacing)
        if len(lines) * line_h <= max_height:
            break
        size -= 1
    if len(lines) * line_h > max_height:
        raise ValueError(f"Text overflow: {text[:50]!r}; box={max_width}x{max_height}")
    for i, line in enumerate(lines):
        draw.text((x, y + i * line_h), line, font=fnt, fill=color)
    return y + len(lines) * line_h


def base(title: str, subtitle: str, number: int, section="ĐỒ ÁN DỮ LIỆU LỚN"):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 9), fill=TEAL)
    d.text((78, 43), section.upper(), font=font(16, True), fill=TEAL)
    text_box(d, 78, 76, title, 38, WHITE, 1380, 70, True)
    text_box(d, 80, 135, subtitle, 19, MUTED, 1400, 40)
    d.line((78, 194, 1522, 194), fill=LINE, width=2)
    d.text((78, 856), "FallAllD-Wrist  •  Prototype học thuật  •  Không phải thiết bị y tế", font=font(13), fill="#74849B")
    d.text((1480, 852), f"{number:02d} / 14", font=font(14, True), fill="#91A3BA")
    return im, d


def card(draw, x, y, w, h, title, body, accent=TEAL, body_size=21):
    rounded(draw, (x, y, x+w, y+h))
    draw.rounded_rectangle((x, y, x+7, y+h), radius=4, fill=accent)
    text_box(draw, x+25, y+20, title, 23, WHITE, w-48, 60, True)
    text_box(draw, x+25, y+78, body, body_size, MUTED, w-50, h-91, False)


def slide_cover():
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.ellipse((1060, -270, 1770, 440), fill="#102D3B")
    d.ellipse((1190, -190, 1640, 250), outline="#1F5C5A", width=3)
    d.rectangle((0, 0, W, 10), fill=TEAL)
    d.text((92, 87), "ĐỒ ÁN MÔN DỮ LIỆU LỚN", font=font(19, True), fill=TEAL)
    text_box(d, 92, 175, "PHÁT HIỆN TÉ NGÃ\nTHỜI GIAN THỰC", 60, WHITE, 1100, 170, True, 1.18)
    text_box(d, 96, 375, "Phân tích cảm biến đeo cổ tay cho người cao tuổi", 27, MUTED, 1110, 54)
    d.line((96, 465, 700, 465), fill=TEAL, width=4)
    fields = [("Nhóm", "[Tên nhóm]"), ("Thành viên", "[Họ tên – MSSV]"), ("Giảng viên", "[Tên giảng viên]")]
    y = 520
    for label, placeholder in fields:
        d.text((98, y), label.upper(), font=font(13, True), fill="#8496AD")
        d.text((300, y-2), placeholder, font=font(19), fill=WHITE)
        d.line((300, y+35, 750, y+35), fill="#38506A", width=1)
        y += 72
    d.text((96, 818), "Kafka  •  Spark Structured Streaming  •  PostgreSQL  •  Random Forest  •  Grafana", font=font(15, True), fill="#9CB1C8")
    d.text((1450, 838), "01 / 14", font=font(14, True), fill="#91A3BA")
    note = "Mở đầu bằng mục tiêu của đồ án: xây dựng pipeline dữ liệu lớn minh họa phát hiện té ngã từ cảm biến cổ tay. Điền tên nhóm, thành viên và giảng viên trước khi trình bày. Nhấn mạnh đây là prototype học thuật, không phải thiết bị y tế."
    return im, note


def slide2():
    im,d=base("Vấn đề & ý nghĩa thực tế","Khi một người cao tuổi ở một mình, sự kiện té ngã có thể khó được người chăm sóc biết kịp thời.",2,"01 · BỐI CẢNH")
    card(d,78,235,450,245,"Tín hiệu liên tục","Cảm biến gia tốc và con quay hồi chuyển ghi lại chuyển động cổ tay theo thời gian.",BLUE,21)
    card(d,575,235,450,245,"Cần xử lý nhanh","Dữ liệu cần được gom, phân tích và chuyển thành thông tin dễ hiểu thay vì chỉ lưu thành hàng triệu mẫu.",GOLD,21)
    card(d,1072,235,450,245,"Hỗ trợ người chăm sóc","Cảnh báo là tín hiệu để con người kiểm tra tình trạng người đeo; không thay thế đánh giá y tế.",TEAL,21)
    rounded(d,(78,535,1522,760),fill="#132638",outline="#24515A")
    d.text((112,566),"Ý NGHĨA CỦA ĐỒ ÁN",font=font(15,True),fill=TEAL)
    text_box(d,112,612,"Kết nối dữ liệu cảm biến với một quy trình phản hồi có thể quan sát được: ingest → stream processing → dự đoán → cảnh báo.",30,WHITE,1320,110,True)
    note="Nêu bài toán ở góc độ kỹ thuật và vận hành, không đưa số liệu y tế không có nguồn. Hệ thống chỉ phát hiện mẫu chuyển động có khả năng là té ngã; quyết định tiếp theo thuộc về người chăm sóc."
    return im,note


def slide3():
    im,d=base("Mục tiêu & phạm vi","Tập trung chứng minh pipeline end-to-end và tính nhất quán của đặc trưng.",3,"02 · PHẠM VI")
    card(d,78,235,690,500,"Trong phạm vi","• Đọc CSV lớn theo chunk bội số 476 mẫu\n• Tạo timestamp sự kiện theo thứ tự mẫu\n• Kafka → Spark window 2 giây\n• Random Forest với chia tập theo thời gian\n• PostgreSQL, cảnh báo có cooldown\n• Grafana + dashboard mô phỏng tương tác",TEAL,22)
    card(d,812,235,710,500,"Ngoài phạm vi / chưa khẳng định","• Không có mã định danh người tham gia\n• Không kết nối vòng đeo tay thật\n• Không gọi điện / gửi SMS thật\n• Không phải công cụ chẩn đoán y tế\n• Chưa báo cáo metric trên full CSV trong môi trường này\n• Chưa kiểm chứng độ trễ trên cụm triển khai thật",RED,21)
    note="Giải thích vì sao cần phân biệt phạm vi demo với triển khai thực tế. Dữ liệu không có subject ID nên không thể làm đánh giá train/test theo người."
    return im,note


def slide4():
    im,d=base("Dữ liệu FallAllD-Wrist","CSV một nguồn, 7 cột cảm biến/nhãn; không có timestamp và không có user ID.",4,"03 · DỮ LIỆU")
    rounded(d,(78,225,980,740))
    d.text((108,252),"SCHEMA 7 CỘT",font=font(15,True),fill=TEAL)
    cols=["acc_x","acc_y","acc_z","label","gyro_x","gyro_y","gyro_z"]
    x=108;y=300
    for i,c in enumerate(cols):
        ww=106 if c!="label" else 92
        rounded(d,(x,y,x+ww,y+52),fill="#1A2A40",outline="#32465F",radius=12,width=1)
        d.text((x+10,y+14),c,font=font(15,True),fill=WHITE)
        x+=ww+8
    card(d,108,390,390,125,"Nhãn","0 = ADL  ·  1 = FALL",BLUE,20)
    card(d,520,390,400,125,"Nguồn thời gian","Gán theo thứ tự mẫu; 238 Hz là giả định theo đề bài.",GOLD,18)
    rounded(d,(108,552,920,688),fill="#10283A",outline="#24515A")
    d.text((138,574),"11.971.400 ÷ 476 = 25.150 cửa sổ",font=font(25,True),fill=TEAL)
    d.text((138,623),"476 mẫu = 238 Hz × 2 giây  ·  phép chia hết đã kiểm tra",font=font(16),fill=MUTED)
    rounded(d,(1015,225,1522,740),fill="#151F31")
    d.text((1050,256),"GIẢ ĐỊNH VÀ KIỂM CHỨNG",font=font(15,True),fill=GOLD)
    text_box(d,1050,305,"• CSV thật chưa có trong workspace.\n\n• Tần số 238 Hz được dùng theo yêu cầu đề bài; cần đối chiếu README/source dataset trước báo cáo cuối.\n\n• `data/fallalld_demo_synthetic.csv` là dữ liệu giả lập để test pipeline, không phải quan sát thật.",19,MUTED,420,390)
    note="Nêu rõ 25.150 cửa sổ là phép tính từ hai con số trong đề: 11.971.400 mẫu và 476 mẫu/cửa sổ. Chúng tôi đã xác minh phép chia, nhưng chưa xác minh nguồn CSV vì chưa tải file 1,37 GB. CSV tổng 11.971.400 chia hết 476 nên không có phần lẻ nếu đúng số dòng."
    return im,note


def slide5():
    im,d=base("Kiến trúc pipeline end-to-end","Từ mẫu cảm biến đến dashboard; mỗi thành phần có vai trò riêng.",5,"04 · KIẾN TRÚC")
    nodes=[("01","Producer","238 mẫu/giây\nper device",BLUE),("02","Kafka","Topic\nwearable.fall.v1",GOLD),("03","Spark","Window 2s\nwatermark 4s",TEAL),("04","PostgreSQL","window_features\npredictions\nalerts",BLUE),("05","Random Forest","300 cây\nP(FALL) ≥ 0,70",GOLD),("06","Grafana","giám sát\n+ phản hồi",TEAL)]
    xs=[78,324,570,816,1062,1308]; y=345; w=205; h=245
    for i,(num,title,body,color) in enumerate(nodes):
        rounded(d,(xs[i],y,xs[i]+w,y+h),fill=PANEL,outline=color,width=2)
        d.ellipse((xs[i]+18,y+18,xs[i]+58,y+58),fill=color)
        d.text((xs[i]+29,y+28),num,font=font(12,True),fill=BG)
        text_box(d,xs[i]+18,y+82,title,19,WHITE,w-36,48,True)
        text_box(d,xs[i]+18,y+135,body,15,MUTED,w-34,92)
        if i<5:
            d.line((xs[i]+w+4,y+122,xs[i+1]-12,y+122),fill="#6E819A",width=3)
            d.polygon([(xs[i+1]-12,y+115),(xs[i+1]-2,y+122),(xs[i+1]-12,y+129)],fill="#6E819A")
    rounded(d,(78,650,1522,750),fill="#10283A",outline="#24515A")
    text_box(d,107,679,"Timestamp = aligned_start + sample_index / 238.  Label được giữ để đối chiếu, không đưa vào vector mô hình.",19,WHITE,1380,50,True)
    note="Đi theo từng thành phần. Producer thêm device ID tổng hợp vì dataset không có, Kafka làm lớp đệm, Spark gom cửa sổ có event-time, PostgreSQL lưu đặc trưng, scorer đọc feature columns và Grafana hiển thị."
    return im,note


def slide6():
    im,d=base("Vai trò của từng công nghệ","Mỗi thành phần giải quyết một phần khác nhau của bài toán dữ liệu lớn.",6,"05 · CÔNG NGHỆ")
    x0,y0=78,232; widths=[300,1110]; rowh=78
    for x,w,t in [(x0,widths[0],"CÔNG NGHỆ"),(x0+widths[0],widths[1],"VAI TRÒ TRONG ĐỒ ÁN")]:
        rounded(d,(x,y0,x+w-10,y0+50),fill="#183247",outline="#285464",radius=10,width=1);d.text((x+15,y0+14),t,font=font(15,True),fill=TEAL)
    rows=[("Producer / Python","Đọc CSV chunked, gán event-time và gửi JSON từng mẫu."),("Kafka · KRaft","Tiếp nhận luồng mẫu, tách producer khỏi consumer."),("Spark Structured Streaming","Watermark 4 giây, aggregate window 2 giây, lọc cửa sổ thiếu."),("PostgreSQL 16","Lưu feature windows, prediction, alert và view giám sát."),("Random Forest / scikit-learn","Phân loại FALL/ADL từ 11 feature, class_weight cân bằng."),("Grafana + HTML demo","Grafana xem dữ liệu DB; HTML tự chứa minh họa thao tác cảnh báo.")]
    for i,(tech,role) in enumerate(rows):
        y=y0+62+i*rowh
        rounded(d,(x0,y,x0+widths[0]-10,y+65),fill=PANEL2,outline=LINE,radius=9,width=1)
        rounded(d,(x0+widths[0],y,x0+sum(widths)-10,y+65),fill=PANEL2,outline=LINE,radius=9,width=1)
        text_box(d,x0+14,y+16,tech,16,WHITE,widths[0]-40,38,True)
        text_box(d,x0+widths[0]+14,y+16,role,16,MUTED,widths[1]-38,42)
    note="Không mô tả công nghệ như một danh sách tên gọi; gắn từng công nghệ với chức năng và dữ liệu nó xử lý."
    return im,note


def slide7():
    im,d=base("Cửa sổ 2 giây & 11 đặc trưng","Mọi feature được tính từ cùng một cửa sổ; độ lệch chuẩn mẫu dùng ddof=1.",7,"06 · FEATURE ENGINEERING")
    rounded(d,(78,230,1522,390))
    d.text((112,256),"476 MẪU THEO THỨ TỰ THỜI GIAN",font=font(15,True),fill=TEAL)
    start,end=125,1465; yy=337
    d.line((start,yy,end,yy),fill="#50647C",width=6)
    for i in range(0,476,17):
        xx=start+(end-start)*i/475
        d.ellipse((xx-3,yy-3,xx+3,yy+3),fill=BLUE if i%34 else GOLD)
    d.line((start,yy+35,end,yy+35),fill=TEAL,width=2)
    d.line((start,yy+25,start,yy+45),fill=TEAL,width=2);d.line((end,yy+25,end,yy+45),fill=TEAL,width=2)
    d.text((start,yy+52),"0.000 s",font=font(13),fill=MUTED);d.text((end-90,yy+52),"2.000 s",font=font(13),fill=MUTED)
    cards=[("ACC magnitude","mean · std(ddof=1)\nmin · max · range",BLUE),("ACC axes","std(acc_x)\nstd(acc_y) · std(acc_z)",GOLD),("Gyroscope magnitude","mean · std(ddof=1)\nmax",TEAL)]
    for i,(head,body,col) in enumerate(cards):card(d,78+i*488,460,455,235,head,body,col,23)
    rounded(d,(78,724,1522,785),fill="#17263A",outline="#2A4259",radius=12,width=1)
    text_box(d,103,741,"Label cửa sổ = FALL nếu mean(label) ≥ 0,5  ·  label không nằm trong 11 feature columns",17,WHITE,1370,36,True)
    note="Giải thích công thức acc_mag = căn bậc hai của tổng bình phương ba trục. Spark stddev_samp tương đương numpy std với ddof=1. Cửa sổ thiếu dưới 90% tức dưới 429 mẫu sẽ bị bỏ qua trong streaming."
    return im,note


def slide8():
    im,d=base("Random Forest & đánh giá trung thực","Chia tập theo thứ tự thời gian; không xáo trộn các cửa sổ liền kề.",8,"07 · MÔ HÌNH")
    card(d,78,235,580,220,"Cấu hình mô hình","300 cây · class_weight=balanced_subsample\nĐầu vào: đúng 11 sensor features\nNhãn: chỉ dùng train / đối chiếu",TEAL,20)
    card(d,688,235,400,220,"Chia dữ liệu","80% cửa sổ đầu → train\n20% cuối → test\nshuffle = False",BLUE,20)
    card(d,1118,235,404,220,"Ngưỡng cảnh báo","P(FALL) ≥ 0,70\nCooldown 10 giây / thiết bị\nCó thể đổi bằng ENV",GOLD,20)
    rounded(d,(78,500,1522,770),fill="#151E30",outline="#4A3941")
    d.text((110,531),"KẾT QUẢ TRÊN CSV THẬT",font=font(16,True),fill=RED)
    items=[("Precision FALL","—"),("Recall FALL","—"),("F1 FALL","—"),("TN / FP / FN / TP","—")]
    x=110
    for label,value in items:
        rounded(d,(x,585,x+330,690),fill="#0E1727",outline="#394153",radius=12,width=1)
        d.text((x+18,604),label,font=font(14),fill=MUTED);d.text((x+18,638),value,font=font(26,True),fill=WHITE)
        x+=350
    text_box(d,110,715,"Chưa chạy trên full dataset. Điền các chỉ số từ models/metrics.json sau khi train với CSV thật.",17,GOLD,1320,35,True)
    note="Tuyệt đối không đọc các con số tổng hợp cũ hoặc synthetic như kết quả thật. Sau khi có CSV đầy đủ, chạy train.py; metrics.json tạo từ dữ liệu đó mới dùng để điền slide."
    return im,note


def slide9():
    im,d=base("Lưu trữ & logic cảnh báo","Ground-truth được lưu tách biệt khỏi prediction để tránh leakage.",9,"08 · DATABASE & ALERTS")
    schemas=[("window_features","window_start · device_id\n11 features · sample_count\nlabel_fraction (đối chiếu)",BLUE),("predictions","prediction · probability\nmodel_version · created_at",TEAL),("alerts","OPEN / FALL_CONFIRMED\n/ FALSE_ALARM · acknowledged",RED)]
    for i,(name,body,col) in enumerate(schemas):
        x=78+i*488
        rounded(d,(x,250,x+455,455),fill=PANEL,outline=col,width=2)
        d.text((x+22,274),name,font=font(20,True),fill=col)
        text_box(d,x+22,324,body,18,MUTED,400,100)
        if i<2:
            d.line((x+458,350,x+480,350),fill="#7791AA",width=3);d.polygon([(x+480,344),(x+490,350),(x+480,356)],fill="#7791AA")
    rounded(d,(78,515,1522,745),fill="#142437",outline="#2D475C")
    d.text((108,545),"LUẬT CẢNH BÁO",font=font(15,True),fill=GOLD)
    text_box(d,108,592,"1  Giữ cửa sổ nếu sample_count ≥ ceil(476 × 0,90) = 429.\n2  Nếu P(FALL) ≥ 0,70 → tạo alert.\n3  Sau alert, im lặng 10 giây cho đúng thiết bị; ngưỡng/cooldown cấu hình qua ENV.\n4  Người theo dõi xác minh, cập nhật disposition và acknowledged.",19,WHITE,1330,137)
    note="Label_fraction được lưu để phân tích offline, nhưng scorer chỉ truy vấn FEATURE_COLUMNS. Cooldown tính trên thời điểm tạo alert ở hệ thống, không dựa vào timestamp giả lập trong tương lai."
    return im,note


def slide10():
    im,d=base("Dashboard: đọc nhanh, hành động rõ","Grafana hiển thị kết quả từ PostgreSQL; HTML demo mô phỏng tương tác.",10,"09 · GIAO DIỆN")
    rounded(d,(78,230,1522,760),fill="#F2F5FA",outline="#60728B",radius=18,width=2)
    d.rounded_rectangle((78,230,1522,300),radius=18,fill="#172338")
    d.text((110,254),"FallAllD · Giám sát té ngã",font=font(22,True),fill="#F3F7FF")
    d.text((1235,260),"DEMO MÔ PHỎNG",font=font(13,True),fill="#FF8799")
    kpis=[("Cửa sổ phân tích","—"),("Cảnh báo mở","—"),("Ngã xác nhận","—"),("Báo nhầm","—")]
    for i,(lab,val) in enumerate(kpis):
        x=108+i*345
        rounded(d,(x,322,x+320,405),fill="#FFFFFF",outline="#D7E0EA",radius=12,width=1)
        d.text((x+16,337),lab,font=font(13),fill="#65758B");d.text((x+16,364),val,font=font(22,True),fill="#1C2A3C")
    rounded(d,(108,430,1008,701),fill="#FFFFFF",outline="#D7E0EA",radius=12,width=1)
    d.text((132,449),"Chuyển động & xác suất FALL",font=font(16,True),fill="#1E2A3B")
    gx,gy,gw,gh=145,495,820,160
    for i in range(5):
        yy=gy+i*gh/4;d.line((gx,yy,gx+gw,yy),fill="#E0E7F0",width=1)
    pts=[]
    for i in range(36):
        xx=gx+i*gw/35;v=0.20+0.11*((i*13)%7)/7+(0.65 if i in (21,22) else 0.0);yy=gy+gh-((min(v,1))*gh)
        if i%2==0:d.rectangle((xx-4,gy+gh-36,xx+4,gy+gh),fill="#9CB8E6")
        pts.append((xx,yy))
    d.line(pts,fill="#3478F6",width=3)
    for i in (21,22):d.ellipse((pts[i][0]-6,pts[i][1]-6,pts[i][0]+6,pts[i][1]+6),fill="#D92842")
    rounded(d,(1030,430,1490,701),fill="#FFFFFF",outline="#D7E0EA",radius=12,width=1)
    d.text((1054,450),"Cảnh báo gần đây",font=font(16,True),fill="#1E2A3B")
    for i,(txt,col) in enumerate([("WRIST-01 · FALL","#D92842"),("Xác nhận & gọi người thân","#D92842"),("Báo nhầm","#65758B")]):
        yy=494+i*61;rounded(d,(1054,yy,1465,yy+46),fill="#F8FAFC",outline="#E0E7EF",radius=9,width=1)
        d.text((1070,yy+13),txt,font=font(12,True),fill=col)
    text_box(d,110,720,"Xác suất trên HTML là giả lập minh họa. Grafana đọc các kết quả thật từ pipeline; thao tác gọi người thân không thực hiện thật.",14,"#5D6C80",1360,30)
    note="Phân biệt hai giao diện: Grafana đọc database thật; dashboard_demo.html chạy mô phỏng client-side, có thể mở file độc lập. Các ô metric được để trống vì chưa có kết quả trên CSV thật."
    return im,note


def slide11():
    im,d=base("Kịch bản demo 5 bước","Trình bày luồng dữ liệu và thao tác xác minh cảnh báo.",11,"10 · DEMO")
    steps=[("01","Chuẩn bị","Tạo synthetic CSV, train RF demo; khởi động Compose."),("02","Phát mẫu","Producer gửi dữ liệu 238 Hz/device vào Kafka."),("03","Gom cửa sổ","Spark tính feature mỗi 2 giây rồi ghi PostgreSQL."),("04","Tạo cảnh báo","Scorer phân loại; mở HTML và bấm “Giả lập té ngã”."),("05","Xác minh","Xác nhận ngã hoặc báo nhầm; xem thống kê trên Grafana.")]
    for i,(num,title,body) in enumerate(steps):
        y=238+i*112
        rounded(d,(128,y,1472,y+84),fill=PANEL,outline=LINE,radius=14)
        d.ellipse((153,y+19,199,y+65),fill=[BLUE,GOLD,TEAL,RED,TEAL][i])
        d.text((166,y+32),num,font=font(12,True),fill=BG)
        d.text((224,y+18),title,font=font(19,True),fill=WHITE)
        text_box(d,500,y+22,body,16,MUTED,900,45)
    note="Đây là kịch bản đề xuất; Compose/Kafka/Spark trên máy học viên chưa được chạy xác nhận trong sandbox. Phần HTML mô phỏng có thể chạy độc lập để trình bày UI."
    return im,note


def slide12():
    im,d=base("Kiểm thử & kết quả hiện có","Tách bạch test synthetic đã chạy và metric còn chờ dữ liệu thật.",12,"11 · KIỂM CHỨNG")
    rounded(d,(78,235,748,740),fill="#122C29",outline="#28664F")
    d.text((112,269),"ĐÃ CHẠY OFFLINE",font=font(17,True),fill=TEAL)
    text_box(d,112,323,"✓ 5/5 unittest pipeline\n✓ Chunk size bội số 476\n✓ Feature contract 11 cột / ddof=1\n✓ Producer dry-run, nhiều device, timestamp căn 2 giây\n✓ RF train/test chronological trên 40 synthetic windows\n✓ Python source biên dịch được",20,WHITE,580,330)
    rounded(d,(790,235,1522,740),fill="#2B2026",outline="#69404A")
    d.text((824,269),"CHƯA KIỂM CHỨNG TRÊN DỮ LIỆU THẬT",font=font(16,True),fill=RED)
    text_box(d,824,323,"• Không có CSV 1,37 GB trong workspace.\n• Precision / recall / F1 thật: để trống.\n• Spark + Kafka + PostgreSQL + Grafana Compose: chưa chạy ở môi trường này.\n• Độ trễ end-to-end: chưa đo.\n\nTrain trên dữ liệu thật rồi điền từ models/metrics.json.",19,WHITE,630,330)
    note="Các test offline đã được chạy với dữ liệu synthetic do make_demo_sample.py tạo ra. Chúng kiểm chứng logic, schema và huấn luyện cơ bản nhưng không cho biết hiệu năng trên FallAllD thật."
    return im,note


def slide13():
    im,d=base("Hạn chế & hướng phát triển","Prototype kỹ thuật không thay thế kiểm định trên người dùng và thiết bị thật.",13,"12 · HẠN CHẾ")
    card(d,78,235,690,420,"Hạn chế hiện tại","• Không có participant ID → không thể chia theo người\n• Timestamp do producer tái tạo từ thứ tự mẫu\n• Dữ liệu synthetic chỉ dùng smoke test\n• RF chưa hiệu chỉnh/calibrate xác suất\n• Alert không gọi dịch vụ bên ngoài",RED,20)
    card(d,812,235,710,420,"Bước tiếp theo","1  Tải full CSV, xác nhận sample rate/nhãn\n2  Chạy train theo thời gian, rà soát leakage\n3  Chạy Docker stack, đo latency và throughput\n4  Đánh giá false positives/negatives theo session nếu có metadata\n5  Tích hợp thiết bị thật và quy trình phản hồi có kiểm soát",TEAL,20)
    rounded(d,(78,688,1522,770),fill="#17263A",outline="#34465D",radius=12,width=1)
    text_box(d,104,706,"Không dùng kết quả demo làm kết luận y khoa hoặc cam kết độ an toàn.",18,GOLD,1360,36,True)
    note="Nhấn mạnh vấn đề thiếu định danh người dùng làm giới hạn đánh giá quan trọng. Ngay cả metric tốt trên random split cũng không đủ để kết luận tổng quát hóa; ở đây dùng chronological split nhưng vẫn cần đánh giá theo session nếu dữ liệu có metadata."
    return im,note


def slide14():
    im=Image.new("RGB",(W,H),BG);d=ImageDraw.Draw(im);d.rectangle((0,0,W,9),fill=TEAL)
    d.text((88,75),"KẾT LUẬN",font=font(17,True),fill=TEAL)
    text_box(d,88,130,"Pipeline lớn — một mục tiêu rõ ràng: đưa chuyển động thành tín hiệu để con người xem xét.",46,WHITE,1370,160,True,1.2)
    cards=[("Dữ liệu","476 mẫu / cửa sổ 2 giây",BLUE),("Streaming","Kafka + Spark + PostgreSQL",TEAL),("Phản hồi","Ngưỡng, cooldown, xác minh",GOLD)]
    for i,(a,b,c) in enumerate(cards):
        x=88+i*490;rounded(d,(x,400,x+450,535),fill=PANEL,outline=c,width=2)
        d.text((x+24,424),a,font=font(17,True),fill=c);text_box(d,x+24,468,b,20,WHITE,395,48,True)
    text_box(d,90,626,"Cảm ơn thầy/cô và các bạn",33,TEAL,1000,60,True)
    text_box(d,92,704,"Kết quả thật sẽ được cập nhật sau khi chạy trên CSV đầy đủ.",18,MUTED,1200,42)
    d.text((1450,838),"14 / 14",font=font(14,True),fill="#91A3BA")
    note="Kết luận ở mức đúng với bằng chứng: đã có pipeline code, demo và kiểm thử offline synthetic. Chưa có metric trên CSV thật hay phép đo runtime stack. Mời câu hỏi."
    return im,note


SLIDES = [slide_cover, slide2, slide3, slide4, slide5, slide6, slide7, slide8, slide9, slide10, slide11, slide12, slide13, slide14]


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    pres = Presentation()
    pres.slide_width = Inches(13.333333)
    pres.slide_height = Inches(7.5)
    rendered=[]
    for idx, maker in enumerate(SLIDES, 1):
        im, notes = maker()
        path = OUT / f"slide_{idx:02d}.png"
        im.save(path, format="PNG", optimize=True)
        slide = pres.slides.add_slide(pres.slide_layouts[6])
        slide.shapes.add_picture(str(path), 0, 0, width=pres.slide_width, height=pres.slide_height)
        slide.notes_slide.notes_text_frame.text = notes
        rendered.append(im)
    pres.save(PPTX_PATH)

    # contact sheet for quick visual inspection; the individual 16:9 PNGs remain available.
    thumb_w, thumb_h, pad = 400, 225, 18
    cols, rows = 4, 4
    sheet = Image.new("RGB", (cols*thumb_w+(cols+1)*pad, rows*(thumb_h+28)+(rows+1)*pad), "#E8EDF4")
    sd = ImageDraw.Draw(sheet)
    for i,im in enumerate(rendered):
        thumb = im.resize((thumb_w,thumb_h),Image.Resampling.LANCZOS)
        x=pad+(i%cols)*(thumb_w+pad); y=pad+(i//cols)*(thumb_h+28+pad)
        sheet.paste(thumb,(x,y));sd.text((x,y+thumb_h+4),f"Slide {i+1:02d}",font=font(12,True),fill="#26364A")
    sheet.save(OUT / "contact_sheet.png", optimize=True)
    (OUT / "render_check.json").write_text(json.dumps({
        "slide_count": len(SLIDES), "size_px": [W,H], "aspect_ratio": "16:9",
        "text_fitting": "Every rendered text box measured and fit within assigned bounds; PPTX slides use the checked full-slide render.",
        "speaker_notes": all(bool(s.notes_slide.notes_text_frame.text.strip()) for s in pres.slides),
        "pptx": str(PPTX_PATH.relative_to(ROOT)),
    }, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(f"Wrote {PPTX_PATH}")
    print(f"Rendered {len(SLIDES)} PNG slides under {OUT}")


if __name__ == "__main__":
    build()
