import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('APP_PORT', 5100))
    debug = os.getenv('APP_DEBUG', 'true').lower() == 'true'
    print(f"\n{'='*50}")
    print(f"  Psychoposition API Server")
    print(f"  Running on: http://0.0.0.0:{port}")
    print(f"  Localhost : http://localhost:{port}/api")
    print(f"  Debug mode: {debug}")
    print(f"{'='*50}\n")
    app.run(
        host='0.0.0.0',   # 0.0.0.0 = bisa diakses dari localhost DAN IP jaringan
        port=port,
        debug=debug,
    )
