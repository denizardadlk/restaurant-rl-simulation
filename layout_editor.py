import http.server
import socketserver
import json
import os
import webbrowser
import threading
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LAYOUTS_DIR = os.path.join(BASE_DIR, "layouts")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DEFAULT_LAYOUT_PATH = os.path.join(CONFIG_DIR, "default_layout.json")

# Global active layout state
ACTIVE_LAYOUT_NAME = "yeni_layout"
ACTIVE_LAYOUT_DATA = None

class LayoutEditorHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/load_active_layout':
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            resp = {
                "status": "success",
                "name": ACTIVE_LAYOUT_NAME,
                "data": ACTIVE_LAYOUT_DATA
            }
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode('utf-8'))
        else:
            super().do_GET()

    def do_POST(self):
        global ACTIVE_LAYOUT_NAME, ACTIVE_LAYOUT_DATA
        if self.path == '/save_layout':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                os.makedirs(LAYOUTS_DIR, exist_ok=True)
                os.makedirs(CONFIG_DIR, exist_ok=True)
                
                data = json.loads(post_data.decode('utf-8'))
                
                # Get custom layout name from payload or fallback
                raw_name = data.get('name', ACTIVE_LAYOUT_NAME or 'custom_layout')
                clean_name = "".join(c for c in raw_name if c.isalnum() or c in ('_', '-')).strip()
                if not clean_name:
                    clean_name = "custom_layout"
                    
                filename = f"{clean_name}.json"
                target_path = os.path.join(LAYOUTS_DIR, filename)
                
                # Strip metadata key from payload before saving
                save_data = {k: v for k, v in data.items() if k != 'name'}
                
                # Save to layouts/<clean_name>.json
                with open(target_path, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, indent=2, ensure_ascii=False)
                    
                # Always sync to layouts/custom_layout.json and config/custom_layout.json for backward compatibility
                custom_layout_path = os.path.join(LAYOUTS_DIR, "custom_layout.json")
                config_custom_path = os.path.join(CONFIG_DIR, "custom_layout.json")
                with open(custom_layout_path, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, indent=2, ensure_ascii=False)
                with open(config_custom_path, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, indent=2, ensure_ascii=False)
                    
                ACTIVE_LAYOUT_NAME = clean_name
                ACTIVE_LAYOUT_DATA = save_data
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success", 
                    "message": f"Layout kaydedildi: layouts/{filename}",
                    "filename": filename,
                    "name": clean_name
                }, ensure_ascii=False).encode('utf-8'))
                print(f"[OK] Harita kaydedildi: layouts/{filename}")
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False).encode('utf-8'))
                print(f"[ERROR] Harita kaydedilemedi: {e}")
        else:
            self.send_error(404, "Not Found")

def open_browser():
    url = f"http://localhost:{PORT}/layout_editor.html"
    print(f"\n[INFO] Tarayıcı otomatik açılıyor: {url}")
    webbrowser.open(url)

def get_available_layouts():
    os.makedirs(LAYOUTS_DIR, exist_ok=True)
    files = [f for f in os.listdir(LAYOUTS_DIR) if f.endswith('.json')]
    files.sort()
    return files

def select_layout_cli():
    global ACTIVE_LAYOUT_NAME, ACTIVE_LAYOUT_DATA
    
    available_files = get_available_layouts()
    
    print("\n" + "=" * 60)
    print("🍽️ RESTORAN LAYOUT DÜZENLEYİCİ - HARİTA SEÇİMİ")
    print("=" * 60)
    print(" 0: [Yeni Layout Oluştur]")
    
    for idx, fname in enumerate(available_files, 1):
        print(f" {idx}: {fname}")
        
    print("=" * 60)
    
    choice = input(f"Lütfen bir numara girin (0-{len(available_files)}): ").strip()
    
    if choice.isdigit() and 1 <= int(choice) <= len(available_files):
        selected_file = available_files[int(choice) - 1]
        filepath = os.path.join(LAYOUTS_DIR, selected_file)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                ACTIVE_LAYOUT_DATA = json.load(f)
            ACTIVE_LAYOUT_NAME = os.path.splitext(selected_file)[0]
            print(f"[OK] '{selected_file}' düzenlemek üzere seçildi.")
        except Exception as e:
            print(f"[UYARI] Dosya okunamadı: {e}. Yeni layout başlatılıyor.")
            ACTIVE_LAYOUT_NAME = "yeni_layout"
            ACTIVE_LAYOUT_DATA = None
    else:
        print("[OK] Yeni layout oluşturuluyor.")
        ACTIVE_LAYOUT_NAME = "yeni_layout"
        ACTIVE_LAYOUT_DATA = None

def main():
    os.chdir(BASE_DIR)
    os.makedirs(LAYOUTS_DIR, exist_ok=True)
    
    # Run CLI Selection before starting server
    select_layout_cli()
    
    with socketserver.TCPServer(("", PORT), LayoutEditorHandler) as httpd:
        print("\n" + "=" * 60)
        print("🚀 SUNUCU BAŞLATILDI")
        print(f"Adres: http://localhost:{PORT}/layout_editor.html")
        print("Durdurmak için: Ctrl+C")
        print("=" * 60)
        
        # Tarayıcıda otomatik aç
        threading.Timer(0.8, open_browser).start()
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        httpd.server_close()
        print("\nSunucu durduruldu.")

if __name__ == "__main__":
    main()

