import streamlit as st
import requests
import pandas as pd
import json
import time
import pytz
import os 
from urllib.request import Request, urlopen # Dùng để gọi API

# --- CẤU HÌNH TIMEZONE ---
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')

# --- THÔNG SỐ CẤU HÌNH THINGSPEAK ---
# LƯU Ý: ĐÂY LÀ READ API KEY, KHÔNG PHẢI WRITE API KEY
CHANNEL_ID = "3096685"
READ_API_KEY = "XS2B689LXUN4I8LF"
THING_SPEAK_URL = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json?api_key={READ_API_KEY}&results=20"

# --- CẤU HÌNH GEMINI AI ---
# VUI LÒNG THAY THẾ CHUỖI NÀY BẰNG API KEY THỰC TẾ CỦA BẠN
GEMINI_API_KEY = "AIzaSyD39L0UrCXvMucZSJyd-MoyyZWLGWyVrJg"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"
SYSTEM_PROMPT = "Bạn là một chuyên gia về kiểm soát khí hậu. Nhiệm vụ của bạn là phân tích dữ liệu môi trường hiện tại và đưa ra các gợi ý hành động để tối ưu hóa sự thoải mái. Khi trò chuyện, hãy trả lời ngắn gọn, thân thiện và sử dụng dữ liệu thực tế được cung cấp."

# Kiểm tra và khởi tạo lịch sử chat (cho tính năng Chatbot)
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "model", "parts": [{"text": "Chào bạn! Tôi là trợ lý AI Khí hậu. Bạn có thể hỏi tôi bất cứ điều gì về nhiệt độ, độ ẩm hiện tại, hoặc các cách cải thiện môi trường phòng."}]}]
if "latest_climate_data" not in st.session_state:
    st.session_state["latest_climate_data"] = {}

st.set_page_config(
    page_title="Giám sát ESP32 & DHT22 (ThingSpeak)",
    layout="wide"
)

def calculate_discomfort_index(temp, hum_percent):
    """Tính toán Chỉ số Khó chịu (DI) dựa trên nhiệt độ và độ ẩm."""
    try:
        H_ratio = hum_percent / 100.0 
        DI = temp - (0.55 - 0.55 * H_ratio) * (temp - 14.5)
        return DI
    except Exception:
        return None

def generate_ai_suggestion(temp, hum, di_index):
    """Gọi Gemini API cho GỢI Ý TỰ ĐỘNG."""
    if GEMINI_API_KEY == "ĐẶT KHÓA API CỦA BẠN VÀO ĐÂY":
        return "⚠️ Cảnh báo: Vui lòng cung cấp khóa API thực tế để kích hoạt AI."

    prompt_for_suggestion = f"{SYSTEM_PROMPT} Dữ liệu môi trường hiện tại: Nhiệt độ {temp:.1f}°C, Độ ẩm {hum:.1f}%, DI {di_index:.2f}. Hãy đưa ra một lời khuyên ngắn gọn (tối đa 2 câu) và trực tiếp về hành động nên làm."
    
    payload = {
        "contents": [{"parts": [{"text": prompt_for_suggestion}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
    }
    
    try:
        headers = {'Content-Type': 'application/json'}
        full_url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}" 
        
        response = requests.post(full_url, headers=headers, data=json.dumps(payload))
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
    if GEMINI_API_KEY == "ĐẶT KHÓA API CỦA BẠN VÀO ĐÂY":
        return "Vui lòng cấu hình API Key để trò chuyện."
    
    # Thêm dữ liệu môi trường mới nhất vào ngữ cảnh trò chuyện
    latest_data_context = (
        f"Ngữ cảnh hiện tại (thông tin mới nhất): "
        f"Nhiệt độ {st.session_state.latest_climate_data.get('temp', 'N/A')}°C, "
        f"Độ ẩm {st.session_state.latest_climate_data.get('hum', 'N/A')}%, "
        f"DI {st.session_state.latest_climate_data.get('di', 'N/A'):.2f}. "
    )
    
    # Tạo lịch sử chat để gửi lên API (bao gồm ngữ cảnh môi trường)
    chat_history = [{"role": m["role"], "parts": m["parts"]} for m in st.session_state.messages]
    
    # Thêm ngữ cảnh môi trường vào phần tử đầu tiên của user prompt
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
        
        response = requests.post(full_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        result = response.json()
        return result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Lỗi phản hồi.')
        
    except requests.exceptions.RequestException as e:
        return f"Lỗi gọi API: {e}. Vui lòng kiểm tra lại."
    except Exception as e:
        return "Lỗi xử lý phản hồi chat."


def fetch_data():
    """Lấy dữ liệu JSON từ ThingSpeak API."""
    try:
        response = requests.get(THING_SPEAK_URL)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Lỗi khi kết nối đến ThingSpeak: {e}")
        return None

def process_data(json_data):
    """Xử lý dữ liệu JSON thành DataFrame và trích xuất dữ liệu mới nhất."""
    if not json_data or 'feeds' not in json_data:
        return None, None

    feeds = json_data['feeds']
    df = pd.DataFrame(feeds)
    
    df = df.rename(columns={
        'created_at': 'Thời gian',
        'field1': 'Độ ẩm (%)',
        'field2': 'Nhiệt độ (°C)',
        'field3': 'Trạng thái Bơm'
    })
    
    df['Thời gian'] = pd.to_datetime(df['Thời gian'])
    df['Thời gian'] = df['Thời gian'].dt.tz_convert(VN_TIMEZONE)
    
    df['Độ ẩm (%)'] = pd.to_numeric(df['Độ ẩm (%)'], errors='coerce')
    df['Nhiệt độ (°C)'] = pd.to_numeric(df['Nhiệt độ (°C)'], errors='coerce')
    df['Trạng thái Bơm'] = pd.to_numeric(df['Trạng thái Bơm'], errors='coerce')
    
    df = df.sort_values('Thời gian', ascending=False).reset_index(drop=True)
    latest_data = df.iloc[0] if not df.empty else None
    
    return df, latest_data

# --- GIAO DIỆN STREAMLIT ---

st.title("💡 Hệ thống Phân tích & Gợi ý Khí hậu Dựa trên AI")

# Thiết lập Chatbot ở Sidebar
with st.sidebar:
    st.header("Trợ lý AI Tư vấn Khí hậu")
    
    # Hiển thị lịch sử chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["parts"][0]["text"])

    # Xử lý input từ người dùng
    if prompt := st.chat_input("Hỏi tôi về nhiệt độ, độ ẩm..."):
        # Thêm prompt của user vào lịch sử
        st.session_state.messages.append({"role": "user", "parts": [{"text": prompt}]})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Tạo không gian chờ phản hồi
        with st.chat_message("model"):
            with st.spinner("AI đang phân tích..."):
                # Gọi hàm chat với Gemini
                response = chat_with_gemini(prompt)
                st.markdown(response)
        # Thêm phản hồi của AI vào lịch sử
        st.session_state.messages.append({"role": "model", "parts": [{"text": response}]})


# Tạo vùng chứa cho dữ liệu cập nhật
data_placeholder = st.empty()
ai_placeholder = st.empty()
chart_placeholder = st.empty()


# Vòng lặp cập nhật dữ liệu tự động
while True:
    json_data = fetch_data()
    df, latest_data = process_data(json_data)

    # --- KHU VỰC HIỂN THỊ DỮ LIỆU THÔ VÀ TÍNH TOÁN DI ---
    di_index = None
    with data_placeholder.container():
        st.subheader("📊 Dữ liệu Cập nhật Mới nhất")
        
        if latest_data is None:
            st.warning("Không thể tải hoặc không có dữ liệu để hiển thị.")
        else:
            temp = latest_data['Nhiệt độ (°C)']
            hum = latest_data['Độ ẩm (%)']
            pump_status = latest_data['Trạng thái Bơm']
            
            di_index = calculate_discomfort_index(temp, hum)
            
            # Cập nhật dữ liệu khí hậu mới nhất vào session state
            st.session_state.latest_climate_data = {"temp": temp, "hum": hum, "di": di_index}

            col1, col2, col3, col4, col5 = st.columns(5)
            
            col1.metric(label="Thời gian", value=latest_data['Thời gian'].strftime("%H:%M:%S"))
            col2.metric(label="Nhiệt độ (°C)", value=f"{temp:.1f} °C", delta_color="off")
            col3.metric(label="Độ ẩm (%)", value=f"{hum:.1f} %", delta_color="off")
            
            status_text = "ON (Hành động)" if pump_status == 1 else "OFF (Tạm dừng)"
            status_color = "inverse" if pump_status == 1 else "off"
            col4.metric(label="Trạng thái Relay", value=status_text, delta_color=status_color)
            
            if di_index is not None:
                di_color = "inverse" if di_index > 26.5 else "off"
                col5.metric(label="Chỉ số Khó chịu (DI)", value=f"{di_index:.2f}", delta_color=di_color)


    # --- KHU VỰC HIỂN THỊ GỢI Ý AI TỰ ĐỘNG ---
    with ai_placeholder.container():
        st.subheader("💡 Gợi ý Tối ưu Khí hậu Tự động")
        
        if latest_data is not None and di_index is not None:
            ai_suggestion = generate_ai_suggestion(temp, hum, di_index)
            
            st.markdown(f"""
                <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #4CAF50;">
                    <p style="font-size: 16px; margin: 0; font-weight: bold;">Lời khuyên AI:</p>
                    <p style="font-size: 18px; margin: 5px 0 0 0;">{ai_suggestion}</p>
                </div>
            """, unsafe_allow_html=True)
        else:
             st.info("Đang chờ dữ liệu ThingSpeak hợp lệ để tạo gợi ý AI...")


    # --- KHU VỰC HIỂN THỊ BIỂU ĐỒ ---
    with chart_placeholder.container():
        st.subheader("📈 Biểu đồ 20 lần đọc gần nhất")
        if df is not None:
            chart_data = df[['Thời gian', 'Nhiệt độ (°C)', 'Độ ẩm (%)']].set_index('Thời gian').sort_index()
            st.line_chart(chart_data)
        
        with st.expander("Xem dữ liệu thay đổi cụ thể"):
            st.dataframe(df)

    # Chờ 5 giây trước khi cập nhật lại dữ liệu
    time.sleep(5)
