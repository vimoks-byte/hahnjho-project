import os
import sys
import urllib.parse

# 상위 폴더의 모듈을 참조할 수 있도록 path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_dashboard import app

class VercelPathMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        query = environ.get('QUERY_STRING', '')
        if '__orig_path=' in query:
            parsed = urllib.parse.parse_qs(query)
            orig = parsed.get('__orig_path', [''])[0]
            if orig:
                # 쿼리스트링에서 __orig_path 제거하여 원래 쿼리 복원
                clean_params = {k: v for k, v in parsed.items() if k != '__orig_path'}
                environ['QUERY_STRING'] = urllib.parse.urlencode(clean_params, doseq=True)
                environ['PATH_INFO'] = orig if orig.startswith('/') else f'/{orig}'
        elif environ.get('PATH_INFO', '') in ('/api/index.py', '/api/index'):
            environ['PATH_INFO'] = '/'
                
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
