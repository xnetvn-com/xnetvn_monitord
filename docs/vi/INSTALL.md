---
post_title: "Cài đặt"
author1: "xNetVN Inc."
post_slug: "docs-vi-install"
microsoft_alias: ""
featured_image: ""
categories:
	- monitoring
tags:
	- install
	- systemd
ai_note: "AI-assisted"
summary: "Hướng dẫn cài đặt và khởi chạy xnetvn_monitord trên Linux."
post_date: "2026-02-03"
---

## Hướng dẫn cài đặt

## 1. Yêu cầu hệ thống

- Linux (ưu tiên Ubuntu/Debian/CentOS/RHEL/Rocky/Alma/Fedora/Arch/openSUSE/SLES/Alpine).
- Python 3.8+ (khuyến nghị 3.10+).
- Quyền root hoặc sudo khi cài đặt systemd service và ghi log hệ thống.

## 2. Cài đặt production bằng script

Script scripts/install.sh sẽ:

- Cài python3 và pip3 (nếu thiếu).
- Tạo virtual environment tại /opt/xnetvn_monitord/.venv.
- Cài PyYAML và psutil trong virtual environment.
- Copy mã nguồn vào /opt/xnetvn_monitord.
- Copy cấu hình vào /opt/xnetvn_monitord/config/main.yaml.
- Luôn làm mới /opt/xnetvn_monitord/config/main.example.yaml và
	/opt/xnetvn_monitord/config/.env.example (ghi đè file mẫu).
- Cài systemd unit vào /etc/systemd/system/xnetvn_monitord.service.

Lưu ý: script không ghi đè /opt/xnetvn_monitord/config/main.yaml hoặc
/opt/xnetvn_monitord/config/.env nếu đã tồn tại.

Lưu ý (Ubuntu 24 LTS / PEP 668): script luôn dùng virtual environment để
tránh lỗi externally-managed-environment khi cài package Python.

Lưu ý: script mặc định tối ưu cho systemd. Với OpenRC (Alpine), hãy chạy thủ công
hoặc tự tạo service theo chuẩn OpenRC của hệ điều hành.

Thực hiện:

```
sudo bash scripts/install.sh
```

Sau khi cài đặt, chỉnh sửa cấu hình:

```
sudo vi /opt/xnetvn_monitord/config/main.yaml
```

Thiết lập secret qua EnvironmentFile (khuyến nghị):

```
sudo mkdir -p /etc/xnetvn_monitord
sudo vi /etc/xnetvn_monitord/xnetvn_monitord.env
sudo chmod 600 /etc/xnetvn_monitord/xnetvn_monitord.env
```

Khởi động dịch vụ:

```
sudo systemctl start xnetvn_monitord
sudo systemctl status xnetvn_monitord
```

## 3. Cài đặt cho môi trường phát triển

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Chạy daemon thủ công:

```
python3 -m xnetvn_monitord.daemon config/main.yaml
```

## 4. Ghi log và PID file

- Log mặc định: /var/log/xnetvn_monitord/monitor.log.
- PID file mặc định: /var/run/xnetvn_monitord.pid.

## 5. Gỡ cài đặt (thủ công)

```
sudo systemctl stop xnetvn_monitord
sudo systemctl disable xnetvn_monitord
sudo rm -f /etc/systemd/system/xnetvn_monitord.service
sudo rm -rf /opt/xnetvn_monitord
sudo rm -rf /var/log/xnetvn_monitord
```