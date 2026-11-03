# Craw-video-bili

Nhap link video Bilibili, xem o chat luong cao, va tai ve neu ban co quyen.

## Tinh nang

- Nhap link `bilibili.com/video/BV...`, link `av...`, hoac BV id tran.
- Hien thi thong tin public: tieu de, tac gia, anh bia, thoi luong, cac part.
- Xem bang player chinh thuc cua Bilibili (iframe `player.bilibili.com`).
- Tai ve bang `yt-dlp`, mac dinh 1080p, tuc la chat luong cao nhung nhe hon
  4K. Co the chon `best` (cao nhat co san), `720` hoac `480`.

## Chay web

```bash
pip install -r requirements.txt
python app.py
```

Mo http://127.0.0.1:5000, nhap link, chon chat luong, bam Xem va tai.

## Chay CLI

```bash
pip install -r requirements.txt
python cli.py --url "https://www.bilibili.com/video/BV..." --info-only
python cli.py --url "https://www.bilibili.com/video/BV..." --quality 1080 --download
```

## Gioi han

- Khong dung login, khong dung cookie, khong vuot DRM. Video VIP, tra phi,
  gioi han vung hoac can dang nhap se khong tai duoc, day la hanh vi dung.
- Chi tai video ban so huu hoac duoc phep tai. Ton trong ban quyen cua tac
  gia va dieu khoan cua Bilibili. Dung cu nay khong phai de phat tan lai
  noi dung cua nguoi khac.

## Cau truc

- `bili.py` - tach BV/av id, goi API view public cua Bilibili, chon chat luong.
- `app.py` - web Flask: `/`, `/watch`, `/download`, `/api/info`.
- `cli.py` - dong lenh xem thong tin va tai ve.
- `downloads/` - thu muc file tai ve, da bi bo qua boi `.gitignore`.
