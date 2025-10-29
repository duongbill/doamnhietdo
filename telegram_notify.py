import requests
import time
from datetime import datetime
import pytz

# --- Cấu hình ---
BOT_TOKEN = "8363385617:AAH2_YIqxRYJ8JtrV3Uznr-WFXLExHeYBlE"  # ⚠️ Token bot của bạn
CHAT_ID = "-4803840634"  # ⚠️ ID nhóm Telegram
THINGSPEAK_URL = "https://api.thingspeak.com/channels/3096685/feeds/last.json?api_key=XS2B689LXUN4I8LF"
TIMEZONE = "Asia/Ho_Chi_Minh"

# --- Giới hạn cảnh báo ---
TEMP_HIGH = 35
HUM_LOW = 40

# --- Hàm lấy thời gian hiện tại ---
def current_time_str():
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz).strftime("%H:%M:%S %d/%m/%Y")

# --- Hàm gửi tin nhắn Telegram ---
def send_telegram_message(message, temp=None, hum=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    text_lines = [
        "📢 *THÔNG BÁO TỪ HỆ THỐNG ESP32*",
        f"🕒 `{current_time_str()}`",
        "",
        message
    ]

    if temp is not None and hum is not None:
        text_lines.append(f"\n🌡 Nhiệt độ: *{temp:.1f}°C*")
        text_lines.append(f"💧 Độ ẩm: *{hum:.1f}%*")

    payload = {
        "chat_id": CHAT_ID,
        "text": "\n".join(text_lines),
        "parse_mode": "Markdown"
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print(f"✅ [Telegram] Đã gửi: {message.splitlines()[0]}") # Chỉ in dòng đầu của tin nhắn
        else:
            print(f"❌ [Telegram] Lỗi gửi: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"⚠️ [Telegram] Lỗi kết nối: {e}")

# --- Hàm lấy dữ liệu mới nhất từ ThingSpeak ---
def fetch_latest_data():
    try:
        r = requests.get(THINGSPEAK_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        temp = float(data.get("field1", 0))
        hum = float(data.get("field2", 0))
        return temp, hum
    except Exception as e:
        print(f"⚠️ [ThingSpeak] Lỗi đọc dữ liệu: {e}")
        return None, None

# --- Hàm lấy tin nhắn từ nhóm (để lắng nghe /status) ---
def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 10, "offset": offset}
    try:
        r = requests.get(url, params=params, timeout=15)
        return r.json()
    except Exception as e:
        print(f"⚠️ [Telegram] Lỗi lấy update: {e}")
        return None

# --- Chương trình chính ---
if __name__ == "__main__":
    print("🚀 Bot Telegram ESP32 đang chạy (Cập nhật 15 giây)...")
    last_temp, last_hum = None, None
    last_update_id = None
    last_sent_alert = 0 # Đổi tên biến cho rõ ràng

    while True:
        # 1️⃣ Lấy dữ liệu MỘT LẦN DUY NHẤT khi bắt đầu vòng lặp
        print("\n--- Bắt đầu vòng lặp mới ---")
        temp, hum = fetch_latest_data()

        # 2️⃣ Kiểm tra lệnh từ nhóm (Dùng dữ liệu đã lấy)
        updates = get_updates(last_update_id)
        if updates and "result" in updates:
            for item in updates["result"]:
                last_update_id = item["update_id"] + 1
                msg = item.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")

                if text.lower() == "/status" and str(chat_id) == CHAT_ID:
                    print("[Command] Nhận lệnh /status...")
                    if temp is not None:
                        di = temp - (0.55 - 0.55 * (hum / 100)) * (temp - 14.5)
                        send_telegram_message(
                            f"📡 Trạng thái theo yêu cầu:\n• Chỉ số khó chịu (DI): {di:.2f}",
                            temp, hum
                        )
                    else:
                        send_telegram_message("⚠️ Không lấy được dữ liệu từ ThingSpeak.")

        # 3️⃣ Kiểm tra dữ liệu để cảnh báo tự động (Dùng dữ liệu đã lấy)
        if temp is not None and hum is not None:
            now = time.time()
            # Chỉ gửi cảnh báo nếu vượt ngưỡng VÀ đã hơn 5 phút kể từ cảnh báo trước
            if (temp > TEMP_HIGH or hum < HUM_LOW) and (now - last_sent_alert > 300):
                print("[Alert] Phát hiện ngưỡng bất thường!")
                msg = ""
                if temp > TEMP_HIGH:
                    msg += "🔥 *Cảnh báo:* Nhiệt độ cao bất thường!\n"
                if hum < HUM_LOW:
                    msg += "💧 *Cảnh báo:* Độ ẩm thấp hơn ngưỡng!"
                send_telegram_message(msg, temp, hum)
                last_sent_alert = now # Cập nhật thời gian gửi cảnh báo
            
            # 4️⃣ GỬI BÁO CÁO ĐỊNH KỲ (MỚI)
            # Luôn gửi báo cáo này mỗi khi vòng lặp chạy
            print("[Status] Gửi báo cáo định kỳ...")
            di = temp - (0.55 - 0.55 * (hum / 100)) * (temp - 14.5)
            send_telegram_message(
                f"📡 Báo cáo định kỳ:\n• Chỉ số khó chịu (DI): {di:.2f}",
                temp, hum
            )

        elif temp is None:
            # Gửi thông báo lỗi nếu không lấy được dữ liệu
            send_telegram_message("⚠️ Không lấy được dữ liệu từ ThingSpeak cho báo cáo định kỳ.")


        # 5️⃣ Ngủ 15 giây
        print(f"--- Hoàn tất vòng lặp, ngủ 15 giây ---")
        time.sleep(15)