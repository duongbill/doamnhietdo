import streamlit as st
import requests
import pandas as pd
import json
import time
import pytz
import os 
from urllib.request import Request, urlopen 

# --- CẤU HÌNH TIMEZONE ---
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')

# ===================================================================
# --- THÔNG SỐ CẤU HÌNH THINGSPEAK (CHO DỮ LIỆU LỊCH SỬ) ---
# ===================================================================
# Vui lòng cập nhật lại KEY và ID của bạn nếu cần
TS_CHANNEL_ID = "3096685"
TS_READ_API_KEY = "XS2B689LXUN4I8LF"
THING_SPEAK_URL = f"https://api.thingspeak.com/channels/{TS_CHANNEL_ID}/feeds.json?api_key={TS_READ_API_KEY}&results=20"


# ===================================================================
# --- THÔNG SỐ CẤU HÌNH BLYNK (CHO DỮ LIỆU MỚI NHẤT) ---
# ===================================================================
# Vui lòng cập nhật Auth Token Blynk của bạn
BLYNK_AUTH_TOKEN = "66-qE5GDloyBqC053tlkW08eJ4E036fp"
# ĐÃ SỬA: Chuyển sang URL chính thức của Blynk IoT (nền tảng mới) và dùng HTTPS
BLYNK_CLOUD_URL = "https://blynk.cloud" 

# Thời gian làm mới Dashboard (giữ nguyên)
REFRESH_INTERVAL_SECONDS = 5

# ===================================================================
# --- CẤU HÌNH GEMINI AI ---
# ===================================================================
# LƯU Ý: VUI LÒNG ĐẢM BẢO KHÓA API NÀY LÀ HỢP LỆ VÀ ĐƯỢC KÍCH HOẠT
GEMINI_API_KEY = "AIzaSyDSDmcWUfWahlgtzFv5LVyUTKpHr7hZxbk"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"
SYSTEM_PROMPT = """Bạn là một chuyên gia về nuôi trồng nấm (Mycologist) với kiến thức chuyên sâu về nấm .
QUY TẮC VÀNG TỔNG HỢP cho nấm (Mọi giai đoạn):
1. Môi trường Lý tưởng Tổng thể: Nhiệt độ 25°C - 30°C, Độ ẩm 80% - 85%.
2. Nguy hiểm: T > 30°C (Quá nóng) hoặc H < 65% (Quá khô).

Nhiệm vụ của bạn là phân tích dữ liệu hiện tại, đối chiếu với Quy tắc Vàng Tổng hợp và đưa ra các gợi ý hành động để tối ưu hóa sự phát triển. Khi trò chuyện, hãy trả lời ngắn gọn, thân thiện và sử dụng dữ liệu thực tế được cung cấp."""

# Khởi tạo Session State (giữ nguyên)
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "model", "parts": [{"text": "Chào mừng đến với hệ thống cố vấn nấm học AI. Bạn có thể hỏi tôi về môi trường hiện tại hoặc các vấn đề của nấm!"}]}]
if "latest_climate_data" not in st.session_state:
    st.session_state["latest_climate_data"] = {}
if "last_refresh_time" not in st.session_state:
    st.session_state["last_refresh_time"] = time.time()
# Biến lưu trữ log debug
if "debug_log" not in st.session_state:
    st.session_state["debug_log"] = []


# --- LOGIC VÀ XỬ LÝ DỮ LIỆU CHUNG ---

def calculate_mushroom_health_index(temp, hum_percent):
    """Tính toán Chỉ số Sức khỏe Nấm (MHI)."""
    try:
        temp_ideal = 24.0
        hum_ideal = 85.0
        temp_penalty = abs(temp - temp_ideal)
        
        if hum_percent < 70.0:
            hum_penalty = (70.0 - hum_percent) * 2
        else:
            hum_penalty = abs(hum_percent - hum_ideal) / 5
            
        MHI = (temp_penalty * 0.6) + (hum_penalty * 0.4)
        return MHI
    except Exception:
        return None

def generate_ai_suggestion(temp, hum, mhi_index):
    """Gọi Gemini API cho GỢI Ý TỰ ĐỘNG."""
    # (Hàm giữ nguyên)
    if not GEMINI_API_KEY or GEMINI_API_KEY == "ĐẶT KHÓA API CỦA BẠN VÀO ĐÂY":
        return "⚠️ Cảnh báo: Vui lòng cung cấp khóa API thực tế để kích hoạt AI."

    prompt_for_suggestion = (
        f"Dữ liệu môi trường hiện tại trong trại nấm: Nhiệt độ {temp:.1f}°C, Độ ẩm {hum:.1f}%, Chỉ số MHI {mhi_index:.2f}. "
        f"Hãy phân tích và đưa ra một lời khuyên ngắn gọn (tối đa 2 câu) và trực tiếp về hành động nên làm (ví dụ: 'Bật quạt thông gió' hoặc 'Phun sương ngay')."
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt_for_suggestion}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
    }
    
    try:
        headers = {'Content-Type': 'application/json'}
        full_url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}" 
        
        response = requests.post(full_url, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status()
        
        result = response.json()
        suggestion = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Không nhận được gợi ý từ AI.')
        return suggestion
    
    except requests.exceptions.RequestException as e:
        return f"Lỗi gọi Gemini API: {e}. Kiểm tra API Key và kết nối mạng."
    except Exception as e:
        return f"Lỗi xử lý phản hồi AI: {e}"

def chat_with_gemini(user_prompt):
    """Gọi Gemini API cho CHẾ ĐỘ TRÒ CHUYỆN (sử dụng lịch sử chat)."""
    # (Hàm giữ nguyên)
    if not GEMINI_API_KEY or GEMINI_API_KEY == "ĐẶT KHÓA API CỦA BẠN VÀO ĐÂY":
        return "Vui lòng cấu hình API Key để trò chuyện."
    
    mhi_index = st.session_state.latest_climate_data.get('mhi', 'N/A')
    
    latest_data_context = (
        f"Ngữ cảnh hiện tại (Trại Nấm): "
        f"Nhiệt độ {st.session_state.latest_climate_data.get('temp', 'N/A')}°C, "
        f"Độ ẩm {st.session_state.latest_climate_data.get('hum', 'N/A')}%, "
        f"Trạng thái Bơm {st.session_state.latest_climate_data.get('pump', 'N/A')}, "
        f"Trạng thái Quạt {st.session_state.latest_climate_data.get('fan', 'N/A')}, "
        f"Chỉ số MHI {mhi_index:.2f}. "
    )
    
    chat_history = [{"role": m["role"], "parts": [{"text": m["parts"][0]["text"]}]} for m in st.session_state.messages]
    
    if chat_history and chat_history[-1]["role"] == "user":
        current_prompt = chat_history[-1]["parts"][0]["text"]
        chat_history[-1]["parts"][0]["text"] = f"{latest_data_context} Người dùng hỏi: {current_prompt}"
    
    payload = {
        "contents": chat_history,
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
    }

    try:
        headers = {'Content-Type': 'application/json'}
        full_url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}" 
        
        response = requests.post(full_url, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status()
        
        result = response.json()
        return result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Lỗi phản hồi.')
        
    except requests.exceptions.RequestException as e:
        return f"Lỗi gọi API: {e}. Vui lòng kiểm tra lại."
    except Exception as e:
        return "Lỗi xử lý phản hồi chat."

# --- CHỨC NĂNG LẤY DỮ LIỆU BLYNK (MỚI NHẤT) ---

def fetch_blynk_pin(pin):
    """Lấy giá trị hiện tại của một Virtual Pin từ Blynk Cloud API và in log."""
    # SỬA LỖI: Đổi tham số vPin thành pin để tương thích với Blynk IoT Cloud
    url = f"{BLYNK_CLOUD_URL}/external/api/get?token={BLYNK_AUTH_TOKEN}&pin={pin}" 
    st.session_state.debug_log.append(f"DEBUG: Gọi API cho {pin}: {url}")
    
    try:
        response = requests.get(url, timeout=5)
        st.session_state.debug_log.append(f"DEBUG: Pin {pin} - Mã trạng thái HTTP: {response.status_code}")
        
        # Nếu mã lỗi là 401, 404 (Auth Token sai, thiết bị offline, Pin sai)
        if response.status_code >= 400:
            error_text = response.text.strip()
            st.session_state.debug_log.append(f"LỖI HTTP Pin {pin}: Status {response.status_code}. Phản hồi: {error_text}")
            return None
            
        value_str = response.text.strip()
        st.session_state.debug_log.append(f"DEBUG: Pin {pin} - Phản hồi thô: '{value_str}'")

        # API mới của Blynk IoT trả về giá trị thô, không cần cố gắng parse JSON
        return value_str
    
    except requests.exceptions.RequestException as e:
        error_msg = f"LỖI KẾT NỐI Pin {pin}: {e}. Kiểm tra URL/Mạng."
        st.session_state.debug_log.append(error_msg)
        return None
    except Exception as e:
        st.session_state.debug_log.append(f"LỖI XỬ LÝ Pin {pin}: {e}")
        return None


def fetch_latest_blynk_metrics():
    """Lấy và xử lý dữ liệu mới nhất từ Blynk (cho metrics)."""
    # XÓA LOG CŨ
    st.session_state.debug_log = [f"--- Bắt đầu làm mới lúc {pd.Timestamp.now(tz=VN_TIMEZONE).strftime('%H:%M:%S')} ---"]
    
    raw_data = {}
    raw_data['temp'] = fetch_blynk_pin("V0")
    raw_data['hum'] = fetch_blynk_pin("V1")
    raw_data['pump'] = fetch_blynk_pin("V2")
    raw_data['fan'] = fetch_blynk_pin("V3")
    
    latest_metrics = {}
    
    # Hàm helper để chuyển đổi các giá trị thô thành 0 (OFF) hoặc 1 (ON)
    def to_on_off_status(raw_val):
        if raw_val is None or str(raw_val).strip() == '':
            return 0 # Giả định là OFF nếu thiếu
        
        normalized_val = str(raw_val).strip().upper()
        # Chấp nhận: "1", "1.0", "ON", "BẬT"
        if normalized_val in ["1", "1.0", "ON", "BẬT"]:
            return 1
        return 0 # Trả về 0 cho các giá trị khác ("0", "OFF", "TẮT", v.v...)

    # KHI CẢ 4 PIN ĐỀU CÓ DỮ LIỆU THÔ (chỉ cần không phải None)
    if all(v is not None for v in raw_data.values()):
        try:
            # V0, V1 là nhiệt độ/độ ẩm (số). 
            # pd.to_numeric trả về scalar float cho đầu vào string đơn.
            temp_value = pd.to_numeric(raw_data['temp'], errors='coerce')
            hum_value = pd.to_numeric(raw_data['hum'], errors='coerce')

            # Đã SỬA LỖI: Loại bỏ .iloc[0] và .empty vì kết quả là scalar float (numpy.float64), 
            # không phải Series, và lỗi "numpy.float64' object has no attribute 'empty'" đã được sửa.
            latest_metrics['Nhiệt độ (°C)'] = temp_value
            latest_metrics['Độ ẩm (%)'] = hum_value
            
            # V2 và V3 là trạng thái (0/1)
            latest_metrics['Trạng thái Bơm'] = to_on_off_status(raw_data['pump'])
            latest_metrics['Trạng thái Quạt'] = to_on_off_status(raw_data['fan'])
            
            latest_metrics['Thời gian'] = pd.Timestamp.now(tz=VN_TIMEZONE)
            
            st.session_state.debug_log.append("DEBUG: Phân tích dữ liệu Blynk THÀNH CÔNG.")
            return latest_metrics, True
        except Exception as e:
            st.session_state.debug_log.append(f"LỖI PHÂN TÍCH DỮ LIỆU: {e}. Dữ liệu thô: {raw_data}")
            return None, False
    
    st.session_state.debug_log.append("DEBUG: Thiếu dữ liệu từ một hoặc nhiều pins Blynk.")
    return None, False

# --- CHỨC NĂNG LẤY DỮ LIỆU THINGSPEAK (LỊCH SỬ) ---

def fetch_thingspeak_history():
    """Lấy và xử lý dữ liệu lịch sử từ ThingSpeak (cho biểu đồ)."""
    try:
        response = requests.get(THING_SPEAK_URL, timeout=10)
        response.raise_for_status()
        json_data = response.json()
    except requests.exceptions.RequestException as e:
        return None
    except Exception:
        return None

    if not json_data or 'feeds' not in json_data:
        return None

    feeds = json_data['feeds']
    df = pd.DataFrame(feeds)
    
    df = df.rename(columns={
        'created_at': 'Thời gian',
        'field1': 'Nhiệt độ (°C)', 
        'field2': 'Độ ẩm (%)', 
    })
    
    df['Thời gian'] = pd.to_datetime(df['Thời gian'])
    df['Thời gian'] = df['Thời gian'].dt.tz_convert(VN_TIMEZONE)
    
    # Đảm bảo chuyển đổi số, các giá trị lỗi sẽ là NaN
    df['Độ ẩm (%)'] = pd.to_numeric(df['Độ ẩm (%)'], errors='coerce')
    df['Nhiệt độ (°C)'] = pd.to_numeric(df['Nhiệt độ (°C)'], errors='coerce')
    
    df = df.sort_values('Thời gian', ascending=True).reset_index(drop=True)
    
    return df

# --- HÀM TỔNG HỢP (HYBRID) ---

def fetch_hybrid_data():
    """Lấy dữ liệu metrics từ Blynk và lịch sử từ ThingSpeak."""
    
    # 1. Lấy dữ liệu mới nhất (Metrics) từ Blynk
    latest_metrics, is_blynk_success = fetch_latest_blynk_metrics()
    
    # 2. Lấy dữ liệu lịch sử (Chart) từ ThingSpeak
    df_history = fetch_thingspeak_history()
    
    return df_history, latest_metrics, is_blynk_success

# --- CHỨC NĂNG STREAMLIT ---

def check_and_rerun():
    """Kiểm tra thời gian và tự động làm mới Streamlit."""
    current_time = time.time()
    if current_time - st.session_state["last_refresh_time"] >= REFRESH_INTERVAL_SECONDS:
        st.session_state["last_refresh_time"] = current_time 
        st.rerun() 

def display_alerts(temp, hum):
    """Kiểm tra các ngưỡng nguy hiểm và hiển thị cảnh báo."""
    alerts = []
    
    # Kiểm tra NaN/None trước khi so sánh
    if pd.isna(temp) or pd.isna(hum):
        alerts.append("❌ DỮ LIỆU LỖI: Không đọc được Nhiệt độ/Độ ẩm từ Blynk. Kiểm tra kết nối.")
    
    if pd.notna(temp) and temp > 30.0:
        alerts.append(f"🔥 NGUY HIỂM: Nhiệt độ quá cao ({temp:.1f}°C). Nguy cơ chết sợi nấm!")
    if pd.notna(hum) and hum < 75.0:
        alerts.append(f"💧 CẢNH BÁO: Độ ẩm quá thấp ({hum:.1f}%). Cần phun sương gấp.")
    if pd.notna(hum) and hum > 95.0:
        alerts.append(f"💧 CẢNH BÁO: Độ ẩm quá cao ({hum:.1f}%). Nguy cơ nấm mốc bùng phát.")

    if alerts:
        for alert in alerts:
            st.error(alert) 
        return True
    return False


# --- GIAO DIỆN STREAMLIT ---
st.set_page_config(
    page_title="Cố vấn Khí hậu Trại Nấm",
    layout="wide"
)

st.title("🍄 Hệ thống Cố vấn & Phân tích Khí hậu Trại Nấm (AI)")

# --- Sidebar Chatbot ---
with st.sidebar:
    st.header("Trợ lý AI Nấm học")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["parts"][0]["text"])

    if prompt := st.chat_input("Hỏi tôi về môi trường nấm..."):
        st.session_state.messages.append({"role": "user", "parts": [{"text": prompt}]})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("model"):
            with st.spinner("AI đang phân tích..."):
                response = chat_with_gemini(prompt)
                st.markdown(response)
        st.session_state.messages.append({"role": "model", "parts": [{"text": response}]})


# --- THỰC THI CHÍNH ---
df_history, latest_metrics, is_blynk_success = fetch_hybrid_data()

# Khởi tạo các biến để tránh lỗi
temp = None
hum = None
mhi_index = None
pump = None
fan = None

# Xử lý dữ liệu Metrics từ Blynk
if latest_metrics is not None and is_blynk_success:
    temp = latest_metrics['Nhiệt độ (°C)']
    hum = latest_metrics['Độ ẩm (%)']
    pump = latest_metrics.get('Trạng thái Bơm', 0)
    fan = latest_metrics.get('Trạng thái Quạt', 0)
    
    # Chỉ tính MHI nếu nhiệt độ và độ ẩm không phải NaN
    if pd.notna(temp) and pd.notna(hum):
        mhi_index = calculate_mushroom_health_index(temp, hum)
        # LƯU TRỮ TRẠNG THÁI MỚI NHẤT CHO AI TRÒ CHUYỆN
        st.session_state.latest_climate_data = {"temp": temp, "hum": hum, "mhi": mhi_index, "pump": pump, "fan": fan}
    else:
        # Cập nhật trạng thái lỗi để AI biết
        st.session_state.latest_climate_data = {"temp": "Lỗi", "hum": "Lỗi", "mhi": 99.99, "pump": pump, "fan": fan}


# --- 0. HIỂN THỊ CẢNH BÁO NỔI BẬT ---
if temp is not None and hum is not None and (pd.notna(temp) or pd.notna(hum)): 
    display_alerts(temp, hum)


# --- 1. HIỂN THỊ DỮ LIỆU METRICS (TỪ BLYNK) ---
with st.container(border=True):
    st.subheader("📊 Dữ liệu Cập nhật Mới nhất (Nguồn Blynk)")
    
    if not is_blynk_success or latest_metrics is None or (pd.isna(temp) and pd.isna(hum)):
        st.warning("⚠️ Không thể tải hoặc phân tích dữ liệu mới nhất từ Blynk. Vui lòng kiểm tra Auth Token và kết nối thiết bị. Xem Log bên dưới để biết chi tiết.")
    else:
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        # Cột 1: Thời gian
        col1.metric(label="⏰ Giờ Cập nhật", value=latest_metrics['Thời gian'].strftime("%H:%M:%S"))
        
        # Cột 2: Nhiệt độ
        temp_display = f"{temp:.1f} °C" if pd.notna(temp) else "---"
        col2.metric(label="🌡 Nhiệt độ", value=temp_display, delta_color="off")
        
        # Cột 3: Độ ẩm
        hum_display = f"{hum:.1f} %" if pd.notna(hum) else "---"
        col3.metric(label="💧 Độ ẩm", value=hum_display, delta_color="off")
        
        # Cột 4: Trạng thái Bơm
        pump_text = "ON" if pump == 1 else "OFF"
        pump_color = "inverse" if pump == 1 else "off"
        col4.metric(label="💦 Phun Sương", value=pump_text, delta_color=pump_color)
        
        # Cột 5: Trạng thái Quạt
        fan_text = "ON" if fan == 1 else "OFF"
        fan_color = "inverse" if fan == 1 else "off"
        col5.metric(label="💨 Thông gió", value=fan_text, delta_color=fan_color)

        # Cột 6: Chỉ số MHI
        if mhi_index is not None and pd.notna(mhi_index):
            mhi_color = "inverse" if mhi_index > 2.0 else "off"
            col6.metric(label="💚 Sức khỏe Nấm", value=f"{mhi_index:.2f}", delta_color=mhi_color)
        else:
            col6.metric(label="💚 Sức khỏe Nấm", value="---", delta_color="off")


# --- 2. KHU VỰC HIỂN THỊ GỢI Ý AI TỰ ĐỘNG ---
with st.container(border=True):
    st.subheader("💡 Gợi ý Tối ưu Môi trường Tự động")
    
    if temp is not None and hum is not None and mhi_index is not None and pd.notna(temp) and pd.notna(hum):
        ai_suggestion = generate_ai_suggestion(temp, hum, mhi_index)
        
        st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #2e7d32; color: #1f1f1f;">
                <p style="font-size: 16px; margin: 0; font-weight: bold; color: #2e7d32;">Lời khuyên từ Cố vấn AI:</p>
                <p style="font-size: 18px; margin: 5px 0 0 0; color: #1f1f1f;">{ai_suggestion}</p>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Đang chờ dữ liệu Blynk hợp lệ để tạo gợi ý AI...")


# --- 3. KHU VỰC HIỂN THỊ BIỂU ĐỒ (TỪ THINGSPEAK) ---
with st.container(border=True):
    st.subheader("📈 Biểu đồ Lịch sử 20 lần đọc (Nguồn ThingSpeak)")
    if df_history is not None and not df_history.empty:
        # Chỉ vẽ Nhiệt độ và Độ ẩm cho biểu đồ line
        chart_data = df_history[['Thời gian', 'Nhiệt độ (°C)', 'Độ ẩm (%)']].set_index('Thời gian').sort_index()
        st.line_chart(chart_data, height=300) 
    else:
        st.info("Không có dữ liệu lịch sử từ ThingSpeak để hiển thị biểu đồ.")
    
    # Giữ expander cho dữ liệu thô, không phải log debug
    with st.expander("Xem dữ liệu lịch sử cụ thể (ThingSpeak)"):
        st.dataframe(df_history if df_history is not None else pd.DataFrame(), use_container_width=True)


# # --- 4. DEBUG LOG TRỰC TIẾP ---
# st.subheader("🛠 DEBUG LOG TRỰC TIẾP (QUAN TRỌNG NHẤT)")
# st.caption("Dùng thông tin này để kiểm tra mã lỗi (Status Code) và Auth Token Blynk.")

# if st.session_state.debug_log:
#     st.code('\n'.join(st.session_state.debug_log), language='text')
# else:
#     st.info("Log sẽ xuất hiện sau lần làm mới đầu tiên.")

# GỌI HÀM LÀM MỚI AN TOÀN
check_and_rerun()
