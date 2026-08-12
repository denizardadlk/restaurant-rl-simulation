import http.server
import socketserver
import json
import os
import webbrowser
import threading

PORT = 8080
CONFIG_DIR = "config"
SAVE_PATH = os.path.join(CONFIG_DIR, "custom_layout.json")

class LayoutEditorHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/save_layout':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                # Ensure directory exists
                os.makedirs(CONFIG_DIR, exist_ok=True)
                
                # Parse JSON to validate format
                data = json.loads(post_data.decode('utf-8'))
                
                # Save to config/custom_layout.json
                with open(SAVE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": "Saved successfully!"}).encode())
                print(f"[OK] Layout saved to {SAVE_PATH}")
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
                print(f"[ERROR] Failed to save layout: {e}")
        else:
            self.send_error(404, "Not Found")

def open_browser():
    url = f"http://localhost:{PORT}/layout_editor.html"
    print(f"[INFO] Tarayıcı otomatik açılıyor: {url}")
    webbrowser.open(url)

def main():
    # Make sure we serve from the project root
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    with socketserver.TCPServer(("", PORT), LayoutEditorHandler) as httpd:
        print(f"Layout Editor started at http://localhost:{PORT}/layout_editor.html")
        print("Press Ctrl+C to stop.")
        
        # Otomatik olarak varsayılan tarayıcıda aç
        threading.Timer(0.8, open_browser).start()
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        httpd.server_close()
        print("Server stopped.")

if __name__ == "__main__":
    main()

