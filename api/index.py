import os
import sys

# 상위 폴더의 모듈을 참조할 수 있도록 path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_dashboard import app

class VercelPathMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        # Vercel 내부 리라이트로 /api/index.py 또는 /api/index로 진입한 경우
        if path.startswith('/api/index.py') or path.startswith('/api/index'):
            matched = environ.get('HTTP_X_MATCHED_PATH', '')
            if matched and matched not in ('/api/index.py', '/api/index'):
                environ['PATH_INFO'] = matched
            else:
                environ['PATH_INFO'] = '/'
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
