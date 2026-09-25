import os
import sys

# 상위 폴더의 모듈을 참조할 수 있도록 path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_dashboard import app

# Vercel Serverless Function entrypoint
# app 객체를 export합니다.
