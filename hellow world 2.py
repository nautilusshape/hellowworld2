import streamlit as st
import json
import re
from google import genai
from google.genai import types


api_key = "AIzaSyC0mA0f_tGLbm38LAxIcwpiwEylLTEEG3U"
# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="تحلیلگر اخبار اقتصادی",
    page_icon="📊",
    layout="wide"
)

# ---------------- SESSION STATE ----------------
if "results" not in st.session_state:
    st.session_state["results"] = None

if "error" not in st.session_state:
    st.session_state["error"] = None

if "raw_response" not in st.session_state:
    st.session_state["raw_response"] = None

# --- Persistent state ---
if "url_input" not in st.session_state:
    st.session_state["url_input"] = ""

if "model_choice" not in st.session_state:
    st.session_state["model_choice"] = "gemini-2.5-flash"

st.markdown(
    """
    <style>
    @font-face {
        font-family: 'B Homa';
        src: url('https://cdn.font-shape.com/webfonts/B-Homa.eot');
        src: url('https://cdn.font-shape.com/webfonts/B-Homa.eot?#iefix') format('embedded-opentype'),
            url('https://cdn.font-shape.com/webfonts/B-Homa.woff2') format('woff2'),
            url('https://cdn.font-shape.com/webfonts/B-Homa.woff') format('woff'),
            url('https://cdn.font-shape.com/webfonts/B-Homa.ttf') format('truetype');
        font-weight: normal; /* تعریف وزن نرمال برای فونت لود شده */
        font-style: normal;
    }

    /* اعمال فونت روی کل اپ */
    html, body, [class*="st-"], .css-18e3th9, .css-1d391kg, .css-qri22k {
        direction: rtl;
        text-align: right;
        font-family: "B Homa", Tahoma, sans-serif !important;
        font-weight: normal !important; /* اضافه شد */
    }

    /* ورودی‌ها */
    .stTextInput > div > div > input {
        text-align: right;
        font-family: "B Homa", Tahoma, sans-serif !important;
        font-weight: normal !important; /* اضافه شد */
    }

    /* متن‌های markdown */
    .stMarkdown p, .stMarkdown li, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        text-align: right;
        font-family: "B Homa", Tahoma, sans-serif !important;
        font-weight: normal !important; /* اضافه شد تا تیترها هم بلد نباشند */
    }

    /* سایدبار هم شامل بشه */
    section[data-testid="stSidebar"] * {
        font-family: "B Homa", Tahoma, sans-serif !important;
        font-weight: normal !important; /* اضافه شد */
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------- APP TITLE ----------------
#st.title("📊 تحلیلگر اخبار اقتصادی")
st.markdown(
    """
    <h1 style='font-family: "B Homa", Tahoma, sans-serif; 
               direction: rtl; 
               text-align: right; 
               font-weight: normal;'>
        📊 تحلیلگر اخبار اقتصادی
    </h1>
    """,
    unsafe_allow_html=True
)
st.markdown("در این صفحه می‌توانید لینک یک خبر اقتصادی را وارد کنید و تحلیل آن را دریافت کنید.")

# ---------------- SIDEBAR ----------------
st.sidebar.header("📄 پارامترهای ورودی")
#api_key = st.sidebar.text_input("🔑 کلید API", type="password")
#url_input = st.sidebar.text_input("🌐 آدرس خبر")


url_input = st.sidebar.text_input(
    "🌐 آدرس خبر",
    value=st.session_state["url_input"]
)
if url_input != st.session_state["url_input"]:
    st.session_state["url_input"] = url_input

# هر بار که کاربر تغییر داد، در session_state ذخیره می‌کنیم
st.session_state["url_input"] = url_input

# انتخاب مدل
model_choice = st.sidebar.radio(
    " انتخاب مدل",
    options=["gemini-2.5-flash", "gemini-2.5-pro"],
    index=["gemini-2.5-flash", "gemini-2.5-pro"].index(st.session_state["model_choice"])
)

if model_choice != st.session_state["model_choice"]:
    st.session_state["model_choice"] = model_choice

run_button = st.sidebar.button("🚀 شروع تحلیل")

#----------------------
def sanitize_results(results: dict) -> dict:
    """
    بررسی و اصلاح خروجی مدل Gemini برای اطمینان از اینکه
    summary, related_news_sources, general_impact, market_impact
    همیشه ساختار مناسب داشته باشند.
    """
    if not isinstance(results, dict):
        return {}

    clean_results = results.copy()

    # --- ۱) بخش summary ---
    summary = clean_results.get("summary", "")
    if isinstance(summary, list):
        # لیست از پاراگراف‌ها → خوبه
        clean_results["summary"] = summary
    elif isinstance(summary, str):
        # یک رشته → تبدیل به لیست تک‌آیتمی برای هماهنگی
        clean_results["summary"] = [summary]
    else:
        clean_results["summary"] = []

    # --- ۲) بخش related_news_sources ---
    sources = clean_results.get("related_news_sources", [])
    if isinstance(sources, str):
        try:
            parsed = json.loads(sources)
            if isinstance(parsed, list):
                clean_results["related_news_sources"] = parsed
            else:
                clean_results["related_news_sources"] = []
        except json.JSONDecodeError:
            clean_results["related_news_sources"] = []
    elif isinstance(sources, list):
        fixed_list = []
        for item in sources:
            if isinstance(item, dict):
                fixed_list.append(item)
            elif isinstance(item, str):
                try:
                    parsed_item = json.loads(item)
                    if isinstance(parsed_item, dict):
                        fixed_list.append(parsed_item)
                except json.JSONDecodeError:
                    pass
        clean_results["related_news_sources"] = fixed_list
    else:
        clean_results["related_news_sources"] = []

    # --- ۳) بخش general_impact ---
    general_impacts = clean_results.get("general_impact", [])
    if isinstance(general_impacts, str):
        try:
            parsed = json.loads(general_impacts)
            if isinstance(parsed, list):
                clean_results["general_impact"] = parsed
            else:
                clean_results["general_impact"] = []
        except json.JSONDecodeError:
            clean_results["general_impact"] = [general_impacts] if general_impacts.strip() else []
    elif not isinstance(general_impacts, list):
        clean_results["general_impact"] = []

    # --- ۴) بخش market_impact ---
    market_impacts = clean_results.get("market_impact", [])
    if isinstance(market_impacts, str):
        try:
            parsed = json.loads(market_impacts)
            if isinstance(parsed, list):
                clean_results["market_impact"] = parsed
            else:
                clean_results["market_impact"] = []
        except json.JSONDecodeError:
            clean_results["market_impact"] = []
    elif isinstance(market_impacts, list):
        fixed_list = []
        for item in market_impacts:
            if isinstance(item, dict):
                fixed_list.append(item)
            elif isinstance(item, str):
                try:
                    parsed_item = json.loads(item)
                    if isinstance(parsed_item, dict):
                        fixed_list.append(parsed_item)
                except json.JSONDecodeError:
                    pass
        clean_results["market_impact"] = fixed_list
    else:
        clean_results["market_impact"] = []

    return clean_results


# ---------------- GEMINI CLIENT ----------------
def get_gemini_response(apikey: str, url: str, model_id: str):
    client = genai.Client(api_key=apikey)
    #model_id = "gemini-2.5-flash"

    system_instruction = """
        شما به عنوان یک تحلیلگر ارشد اقتصادی عمل خواهید کرد. وظیفه شما تحلیل دقیق و چندوجهی یک خبر اقتصادی است که در ادامه به شما ارائه می‌شود. لطفاً تحلیل خود را به صورت ساختارمند و در بخش‌های مجزا مطابق با الگوی زیر ارائه دهید.
        بخش ۱: Summary
        در این بخش، خلاصه‌ای دقیق و مختصر (در یک پاراگراف) از مهم‌ترین نکات و داده‌های کلیدی خبر ارائه دهید.
        بخش ۲: Related News & Sources
        با جستجو در منابع معتبر داخلی و بین‌المللی، بین ۴ تا ۱۰ منبع خبری یا گزارش معتبر بیابید که به موضوع اصلی خبر مرتبط هستند و از نظر استراتژیک بر آن تأثیر می‌گذارند یا از آن تأثیر می‌پذیرند. این منابع می‌توانند شامل اخبار تکمیلی، گزارش‌های تحلیلی از صنایع مرتبط، قوانین جدید یا تحولات سیاسی-اقتصادی باشند؛ توجه داشته باشید که این نتایج به عنوان پایه و اساس برای تحلیل‌های عمیق‌تر در مراحل بعدی استفاده خواهد شد.
        برای هر منبع، اطلاعات زیر را فهرست کنید:
        •	Original Title:
        •	Source Name:
        •	Publication Date: (تاریخ را به فرمت شمسی yyyy/mm/dd وارد کنید)
        •	Key Information Summary: (خلاصه‌ای یک یا دو جمله‌ای از مهم‌ترین اطلاعات این منبع و نحوه ارتباط استراتژیک آن با خبر اصلی را شرح دهید)
        بخش ۳: General Impact Analysis
        از لیست زیر، مشخص کنید که این خبر بر کدام یک از جنبه‌های عمومی جامعه تأثیر مستقیم یا غیرمستقیم دارد. فقط موارد مرتبط را نام ببرید.
        JSON
        "general_impact": [
        "سیاست خارجی",
        "بودجه و برنامه‌ریزی",
        "نیروی کار و اشتغال",
        "فرهنگ و جامعه",
        "سلامت و بهداشت",
        "آموزش و پژوهش",
        "زیرساخت و توسعه",
        "محیط زیست و منابع طبیعی",
        "فناوری و نوآوری",
        "امنیت و دفاع",
        "حمل‌ونقل و لجستیک",
        "عدالت اجتماعی و رفاه",
        "مالیات و نظام مالی",
        "تجارت داخلی و خارجی",
        "قوانین و مقررات"
        ]
        بخش ۴: Market Impact Analysis
        از لیست زیر، مشخص کنید که این خبر بر کدام یک از بازارها تأثیرگذار است.
        JSON
        "markets_impact": [
        "بازار ارز",
        "بازار طلا و سکه",
        "بازار سرمایه (بورس و فرابورس)",
        "بازار اوراق بدهی",
        "بازار مسکن و مستغلات",
        "بازار انرژی (نفت، گاز، برق)",
        "بازار کالا (Commodity)",
        "بازار کشاورزی و محصولات غذایی",
        "بازار فناوری و استارتاپ‌ها",
        "بازار خدمات (بانکداری، بیمه، حمل‌ونقل)",
        "بازار کار و دستمزد",
        "بازار خودرو",
        "بازار جهانی (Global Markets)"
        ]
        بخش ۵: Detailed Market Impact Analysis
        برای هر یک از بازارهایی که در بخش ۴ انتخاب کردید، تحلیل کاملی در قالب زیر ارائه دهید:
        Market Name: [نام بازار انتخاب شده]
        •	Impact Type: [مثبت / منفی]
        •	Impact Intensity: [کم / متوسط / زیاد]
        •	Reasoning Analysis: به صورت دقیق و مستدل توضیح دهید که چرا این خبر چنین تأثیری (مثبت یا منفی) بر این بازار خاص دارد. به زنجیره علت و معلولی اتفاقات اشاره کنید.
        •	Strategy & Recommendations:
        o	(در صورت تأثیر منفی): چه راهکارهایی برای فعالان این بازار، سرمایه‌گذاران یا سیاست‌گذاران برای کاهش ریسک و مقابله با اثرات منفی این خبر وجود دارد؟
        o	(در صورت تأثیر مثبت): چگونه می‌توان از فرصت‌های ایجاد شده به بهترین شکل استفاده کرد و این تأثیر مثبت را تقویت نمود؟

        {
        "response_schema": {
            "type": "object",
            "properties": {
            "summary": {
                "type": "string",
                "description": "خلاصه دقیق و مختصر خبر",
                "nullable": true
                }
            },
            "related_news_sources": {
                "type": "array",
                "description": "۴ تا ۱۰ منبع مرتبط؛ برای هر منبع عنوان، نام منبع، تاریخ به فرمت شمسی (yyyy/mm/dd) و خلاصه کلیدی ذکر شود.",
                "items": {
                "type": "object",
                "properties": {
                    "original_title": {
                    "type": "string",
                    "description": "عنوان اصلی مطلب",
                    "nullable": true
                    },
                    "source_name": {
                    "type": "string",
                    "description": "نام خروجی خبری یا گزارش",
                    "nullable": true
                    },
                    "publication_date": {
                    "type": "string",
                    "description": "تاریخ انتشار به فرمت شمسی yyyy/mm/dd",
                    "nullable": true
                    },
                    "key_information_summary": {
                    "type": "string",
                    "description": "خلاصه یک یا دو جمله‌ای و ارتباط استراتژیک با خبر اصلی",
                    "nullable": true
                    }
                }
                }
            },
            "general_impact": {
                "type": "array",
                "description": "جنبه‌های عمومی جامعه که خبر بر آن‌ها اثر دارد — فقط موارد مرتبط را فهرست کنید.",
                "items": {
                "type": "string",
                "enum": [
                    "سیاست خارجی",
                    "بودجه و برنامه‌ریزی",
                    "نیروی کار و اشتغال",
                    "فرهنگ و جامعه",
                    "سلامت و بهداشت",
                    "آموزش و پژوهش",
                    "زیرساخت و توسعه",
                    "محیط زیست و منابع طبیعی",
                    "فناوری و نوآوری",
                    "امنیت و دفاع",
                    "حمل‌ونقل و لجستیک",
                    "عدالت اجتماعی و رفاه",
                    "مالیات و نظام مالی",
                    "تجارت داخلی و خارجی",
                    "قوانین و مقررات"
                ]
                },
                "nullable": true
            },
            "market_impact": {
                "type": "array",
                "description": "تحلیل تفصیلی برای بازارهای انتخاب شده.",
                "items": {
                "type": "object",
                "properties": {
                    "market_name": {
                    "type": "string",
                    "description": "",
                    "enum": [
                        "بازار ارز",
                        "بازار طلا و سکه",
                        "بازار سرمایه (بورس و فرابورس)",
                        "بازار اوراق بدهی",
                        "بازار مسکن و مستغلات",
                        "بازار انرژی (نفت، گاز، برق)",
                        "بازار کالا (Commodity)",
                        "بازار کشاورزی و محصولات غذایی",
                        "بازار فناوری و استارتاپ‌ها",
                        "بازار خدمات (بانکداری، بیمه، حمل‌ونقل)",
                        "بازار کار و دستمزد",
                        "بازار خودرو",
                        "بازار جهانی (Global Markets)"
                    ],
                    "nullable": false
                    },
                    "impact_type": {
                    "type": "string",
                    "description": "نوع اثر: مثبت یا منفی",
                    "enum": ["مثبت", "منفی"],
                    "nullable": false
                    },
                    "impact_intensity": {
                    "type": "string",
                    "description": "شدت تأثیر",
                    "enum": ["کم", "متوسط", "زیاد"],
                    "nullable": false
                    },
                    "reasoning_analysis": {
                    "type": "string",
                    "description": "توضیح مستدل و زنجیره علت‌و‌معلولی که منجر به این تأثیر شده است",
                    "nullable": false
                    },
                    "strategy_and_recommendations": {
                    "type": "string",
                    "description": "پیشنهادات راهبردی بسته به نوع تأثیر",
                    "nullable": false
                    }
                }
                },
                "nullable": true
            }
            },
            "required": [
            "summary",
            "related_news_sources",
            "general_impact",
            "market_impact"
            ]
        }
        }





    """  

    prompt = f"متن ورودی یا آدرس url آن {url}"
    tools = [
        {"url_context": {}},
        {"google_search": {}}
    ]

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config={
                "tools": tools,
                "system_instruction": [types.Part.from_text(text=system_instruction)],
                "temperature": 0.2,
                **({"thinking_config": types.ThinkingConfig(thinking_budget=0)} if model_id == "gemini-2.5-flash" else {})
            }
        )

        if hasattr(response, "text") and response.text:
            known_error_keywords = ["Overloaded", "RESOURCE_EXHAUSTED", "Service Unavailable", "429", "500", "Error"]
            if any(keyword.lower() in response.text.lower() for keyword in known_error_keywords):
                return {"error": response.text.strip(), "raw_response": response.text.strip()}

            match = re.search(r'(\{.*\}|\[.*\])', response.text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    return {"error": "JSONDecodeError", "raw_response": response.text.strip()}
            else:
                return {"error": "No JSON found", "raw_response": response.text.strip()}
        else:
            return {"error": "No response text from model", "raw_response": None}

    except Exception as e:
        return {"error": str(e), "raw_response": None}

    # --- گرفتن خطاهای API ---
    except (ResourceExhausted, ServiceUnavailable, DeadlineExceeded) as e:
        return {"error": str(e), "raw_response": None}

    except Exception as e:
        return {"error": str(e), "raw_response": None}


# ---------------- بخش اصلی ----------------
if run_button:
    if not api_key:
        st.error("🔑 لطفاً کلید API خود را در سایدبار وارد کنید.")
    elif not url_input:
        st.error("🌐 لطفاً آدرس خبر را وارد کنید.")
    else:
        with st.spinner("⏳ در حال تحلیل خبر..."):
            results = get_gemini_response(api_key, url_input, model_choice)

        # ذخیره در session_state
        if "error" in results:
            st.session_state["error"] = results.get("error")
            st.session_state["raw_response"] = results.get("raw_response")
            st.session_state["results"] = None
            
        else:
            st.session_state["results"] = sanitize_results(results)
            st.session_state["error"] = None
            st.session_state["raw_response"] = None

# ---------------- نمایش نتایج از session_state ----------------
#if st.session_state["error"]:
#    # فقط خطا را نشان بده
#    st.error("❌ خطا در دریافت پاسخ از مدل")
#    st.code(st.session_state["error"])
#    if st.session_state["raw_response"]:
#        st.subheader("📄 پاسخ خام مدل (برای بررسی)")
#        st.text(st.session_state["raw_response"])
if st.session_state["error"]:
    st.error("❌ خطا در دریافت پاسخ از مدل")

    # نمایش کامل بدون اسکرول
    st.markdown(f"<pre style='white-space: pre-wrap; word-wrap: break-word;'>{st.session_state['error']}</pre>", unsafe_allow_html=True)

    if st.session_state["raw_response"]:
        st.subheader("📄 پاسخ خام مدل (برای بررسی)")
        st.markdown(f"<pre style='white-space: pre-wrap; word-wrap: break-word;'>{st.session_state['raw_response']}</pre>", unsafe_allow_html=True)


elif st.session_state["results"]:
    results = st.session_state["results"]

    # --- بخش ۱: خلاصه خبر ---
    st.subheader("📌 خلاصه خبر")
    summary = results.get("summary", "")
    if summary:
        if isinstance(summary, list):
            for para in summary:
                st.markdown(para)
        else:
            st.markdown(summary)
    else:
        st.info("خلاصه‌ای تولید نشد.")
    st.markdown("---")

    # --- بخش ۲: اخبار و منابع مرتبط ---
    st.subheader("📰 اخبار و منابع مرتبط")
    sources = results.get("related_news_sources", [])
    if sources:
        for src in sources:
            with st.expander(src.get("original_title", "بدون عنوان")):
                st.markdown(f"- **منبع:** {src.get('source_name', '')}")
                st.markdown(f"- **تاریخ:** {src.get('publication_date', '')}")
                st.markdown(f"- **خلاصه نکات کلیدی:** {src.get('key_information_summary', '')}")
    else:
        st.info("منبع مرتبطی یافت نشد.")
    st.markdown("---")

    # --- بخش ۳: تأثیرات عمومی ---
    st.subheader("🌍 تأثیرات عمومی")
    general_impacts = results.get("general_impact", [])
    if general_impacts:
        st.markdown(
            """
            <style>
            .impact-card {
                background-color: #e3f2fd;
                padding: 12px;
                border-radius: 12px;
                text-align: center;
                font-weight: bold;
                margin: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        cols = st.columns(3)
        for i, impact in enumerate(general_impacts):
            with cols[i % 3]:
                st.markdown(f"<div class='impact-card'>{impact}</div>", unsafe_allow_html=True)
    else:
        st.info("تأثیر عمومی شناسایی نشد.")
    st.markdown("---")

    # --- بخش ۴: تحلیل تأثیر بر بازارها ---
    st.subheader("💹 تحلیل تأثیر بر بازارها")
    market_impacts = results.get("market_impact", [])
    if market_impacts:
        for market in market_impacts:
            with st.container():
                st.markdown(f"### 📈 {market.get('market_name', 'بازار ناشناخته')}")
                st.markdown(f"- **نوع اثر:** {market.get('impact_type', '')}")
                st.markdown(f"- **شدت اثر:** {market.get('impact_intensity', '')}")
                st.markdown(f"- **تحلیل منطقی:** {market.get('reasoning_analysis', '')}")
                st.markdown(f"- **توصیه‌ها و راهبردها:** {market.get('strategy_and_recommendations', '')}")
    else:
        st.info("هیچ تحلیلی برای بازارها ارائه نشد.")

    # --- نمایش JSON خام ---
    with st.expander("🗂 نمایش خروجی JSON خام"):
        st.json(results)
