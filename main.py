
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# =========================================================
# 1. 페이지 기본 설정
# =========================================================

st.set_page_config(
    page_title="KOBIS 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 일일 박스오피스")
st.caption("영화관입장권통합전산망(KOBIS) 공식 API")


# =========================================================
# 2. 한국 시간 기준으로 날짜 계산
# =========================================================
# 배포 서버가 한국이 아닌 다른 시간대에 있어도
# ZoneInfo를 이용하면 한국 시간을 정확하게 사용할 수 있습니다.

KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)

# 오늘은 아직 집계가 끝나지 않았으므로
# 달력에서 선택할 수 있는 가장 늦은 날짜는 어제입니다.
yesterday = now_kst.date() - timedelta(days=1)


# =========================================================
# 3. 조회 날짜 선택
# =========================================================

selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday,
)

# KOBIS API가 요구하는 날짜 형식인 YYYYMMDD로 변환합니다.
target_dt = selected_date.strftime("%Y%m%d")

st.caption(
    f"조회 날짜: **{selected_date.strftime('%Y년 %m월 %d일')}**"
)


# =========================================================
# 4. KOBIS API 호출 함수
# =========================================================
# 같은 날짜를 다시 조회하면 1시간 동안 저장된 결과를 사용합니다.
# 따라서 같은 날짜에 API를 반복해서 호출하지 않습니다.

@st.cache_data(ttl=3600)
def get_boxoffice(api_key, target_date):
    """KOBIS 일일 박스오피스 데이터를 가져옵니다."""

    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 발생하면 예외를 발생시킵니다.
        response.raise_for_status()

        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API에 요청하는 중 문제가 발생했습니다.\n\n"
                f"자세한 내용: {e}\n\n"
                "인터넷 연결이나 KOBIS API의 상태를 확인해 주세요."
            ),
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API의 응답을 읽을 수 없습니다.\n\n"
                "잠시 후 다시 시도해 주세요."
            ),
        }

    # -----------------------------------------------------
    # 5. faultInfo 확인
    # -----------------------------------------------------
    # KOBIS는 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 faultInfo가 있는지도 반드시 확인해야 합니다.

    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: "
                f"{fault_info.get('errorCode', '확인할 수 없음')}\n\n"
                f"오류 내용: "
                f"{fault_info.get('message', '확인할 수 없음')}\n\n"
                "다음을 확인해 주세요:\n"
                "• Streamlit Cloud의 Secrets에 KOBIS_KEY가 등록되어 있는지\n"
                "• KOBIS_KEY의 값이 정확한지\n"
                "• KOBIS Open API를 정상적으로 이용할 수 있는지"
            ),
        }

    # -----------------------------------------------------
    # 6. boxOfficeResult 확인
    # -----------------------------------------------------

    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "message": (
                "KOBIS API 응답에 박스오피스 결과가 없습니다.\n\n"
                "KOBIS API의 서비스 상태를 확인해 주세요."
            ),
        }

    # 영화 목록 가져오기
    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        [],
    )

    # -----------------------------------------------------
    # 7. 영화 목록이 비어 있는 경우
    # -----------------------------------------------------

    if not movie_list:
        return {
            "success": False,
            "empty": True,
            "message": "그날은 아직 집계 전입니다.",
        }

    return {
        "success": True,
        "empty": False,
        "data": movie_list,
    }


# =========================================================
# 8. Secrets에서 KOBIS 인증키 가져오기
# =========================================================
# 인증키를 main.py에 직접 쓰지 않습니다.
# Streamlit Cloud의 Secrets에 KOBIS_KEY를 등록해야 합니다.

try:
    api_key = st.secrets["KOBIS_KEY"]

except KeyError:
    st.error(
        "🔑 KOBIS_KEY를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 **Settings → Secrets**에서 "
        "`KOBIS_KEY`를 등록해 주세요."
    )
    st.stop()


# =========================================================
# 9. 선택한 날짜의 박스오피스 조회
# =========================================================

result = get_boxoffice(
    api_key,
    target_dt,
)


# API 호출 자체가 실패한 경우
if not result["success"]:

    # 영화 목록이 없는 경우에는 특별한 문구를 보여줍니다.
    if result.get("empty"):
        st.warning(
            f"📅 {selected_date.strftime('%Y년 %m월 %d일')} "
            "그날은 아직 집계 전입니다."
        )

    # 그 밖의 API 오류는 상세 안내를 보여줍니다.
    else:
        st.error(result["message"])

    st.stop()


# =========================================================
# 10. DataFrame으로 변환
# =========================================================

movie_list = result["data"]

df = pd.DataFrame(movie_list)


# =========================================================
# 11. 숫자 데이터를 실제 숫자로 변환
# =========================================================
# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 정렬, 계산, 그래프 등에 사용할 수 있도록 숫자로 변환합니다.

numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt",
]

for column in numeric_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0).astype(int)


# =========================================================
# 12. 순위순으로 정렬
# =========================================================

df = (
    df.sort_values("rank")
    .reset_index(drop=True)
)


# =========================================================
# 13. 영화명에 트로피 붙이기
# =========================================================
# 누적관객이 100만 명을 넘은 영화에는 🏆를 붙입니다.
#
# 100만 명 "초과"이므로 > 1,000,000을 사용합니다.

def make_movie_name(row):
    movie_name = str(row["movieNm"])

    if row["audiAcc"] > 1_000_000:
        return f"🏆 {movie_name}"

    return movie_name


df["display_movie_name"] = df.apply(
    make_movie_name,
    axis=1,
)


# =========================================================
# 14. 순위 증감 표시
# =========================================================
# rankInten은 전날과 비교한 순위 증감입니다.
#
# 양수 → 순위 상승 → 빨간색 위 화살표
# 음수 → 순위 하락 → 파란색 아래 화살표
# 0    → 변동 없음
#
# 예:
# +2 → 🔴⬆️ 2
# -1 → 🔵⬇️ 1

def make_rank_change(value):
    value = int(value)

    if value > 0:
        return f"🔴⬆️ {value}"

    if value < 0:
        return f"🔵⬇️ {abs(value)}"

    return "—"


df["rank_change"] = df["rankInten"].apply(
    make_rank_change
)


# =========================================================
# 15. 1위 영화
# =========================================================

first_movie = df.iloc[0]

st.subheader("🏆 1위 영화")

col1, col2, col3 = st.columns(3)


# 첫 번째 카드: 영화명
with col1:
    st.metric(
        label="영화",
        value=first_movie["display_movie_name"],
    )


# 두 번째 카드: 해당 날짜 관객수
with col2:
    st.metric(
        label="관객수",
        value=f"{first_movie['audiCnt']:,}명",
    )


# 세 번째 카드: 누적관객
with col3:
    st.metric(
        label="누적관객",
        value=f"{first_movie['audiAcc']:,}명",
    )


# =========================================================
# 16. 관객수 상위 5편 그래프
# =========================================================

st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False,
    )
    .head(5)
    .copy()
)

# 그래프에는 트로피가 붙은 영화명도 그대로 사용합니다.
chart_data = top5.set_index(
    "display_movie_name"
)[["audiCnt"]]

st.bar_chart(
    chart_data,
    x_label="영화",
    y_label="관객수",
)


# =========================================================
# 17. 전체 박스오피스 표
# =========================================================

st.subheader("🎞️ 전체 박스오피스")

display_df = df[
    [
        "rank",
        "rank_change",
        "display_movie_name",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
    ]
].copy()


# 화면에 표시할 한국어 컬럼 이름으로 바꿉니다.
display_df = display_df.rename(
    columns={
        "rank": "순위",
        "rank_change": "순위 변동",
        "display_movie_name": "영화명",
        "openDt": "개봉일",
        "audiCnt": "관객수",
        "audiAcc": "누적관객",
        "scrnCnt": "스크린수",
    }
)


# 숫자에는 천 단위 구분기호를 붙여서 보기 좋게 만듭니다.
# 데이터 자체는 이미 숫자이므로 정렬과 계산에는 문제가 없습니다.

st.dataframe(
    display_df.style.format(
        {
            "순위": "{:,.0f}",
            "관객수": "{:,.0f}",
            "누적관객": "{:,.0f}",
            "스크린수": "{:,.0f}",
        }
    ),
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# 18. 데이터 출처
# =========================================================

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) Open API"
)

